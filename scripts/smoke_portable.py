"""Exercise the actual ZIP-extracted executable without Python on its PATH."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import tempfile
import time
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def request(base, path, body=None):
    data = None if body is None else json.dumps(body).encode('utf-8')
    req = urllib.request.Request(base + path, data=data, headers={'Content-Type': 'application/json'})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=10) as response:
        result = response.read()
        return json.loads(result) if 'application/json' in response.headers.get('Content-Type', '') else result


def stop(process):
    if process.poll() is None:
        process.send_signal(signal.CTRL_BREAK_EVENT if os.name == 'nt' else signal.SIGINT)
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            raise AssertionError('Packaged server did not shut down gracefully')
    if process.returncode != 0:
        raise AssertionError(f'Unexpected server exit status: {process.returncode}')


def start(exe, env, cwd, port, log):
    process = subprocess.Popen([str(exe), '--no-browser', '--port', str(port)], env=env, cwd=cwd,
                               stdout=log, stderr=subprocess.STDOUT,
                               creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0)
    base = f'http://127.0.0.1:{port}'
    deadline = time.monotonic() + 40
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError(f'Packaged process exited during startup: {process.returncode}')
        try:
            if request(base, '/api/health') == {'status': 'ok', 'app': 'websheet-agent'}:
                return process, base
        except (OSError, ValueError):
            pass
        time.sleep(.1)
    process.kill()
    process.wait()
    raise AssertionError('Packaged process never became healthy')


def verify(archive, root):
    expected = archive.with_suffix('.zip.sha256').read_text(encoding='ascii').split()[0]
    with archive.open('rb') as source:
        assert hashlib.file_digest(source, 'sha256').hexdigest() == expected, 'Archive SHA256 mismatch'
    with zipfile.ZipFile(archive) as packed:
        for member in packed.namelist():
            parts = Path(member).parts
            assert '..' not in parts and not Path(member).is_absolute(), 'Unsafe ZIP member'
            assert not any(part.lower() in ('playwright', 'chromium', 'data') or part.startswith('.env')
                           or part.lower().endswith(('.sqlite', '.sqlite3', '.db')) for part in parts), f'Unexpected private/browser data: {member}'
        packed.extractall(root / 'extracted')
    bundle = root / 'extracted' / 'WebSheet-Agent'
    exe = bundle / ('WebSheet-Agent.exe' if os.name == 'nt' else 'WebSheet-Agent')
    if os.name != 'nt':
        exe.chmod(exe.stat().st_mode | 0o111)
    assert (bundle / '_internal' / 'websheet' / 'static' / 'index.html').is_file(), 'Missing static UI'
    assert (bundle / 'licenses' / 'PYTHON-LICENSE.txt').stat().st_size > 1000
    assert (bundle / 'licenses' / 'build-environment.json').is_file()
    cwd = root / 'unrelated working directory'
    cwd.mkdir()
    user_data = root / 'isolated user data'
    env = os.environ.copy()
    for name in ('WEBSHEET_DB', 'PYTHONPATH', 'PYTHONHOME', 'VIRTUAL_ENV', 'DEEPSEEK_API_KEY'):
        env.pop(name, None)
    env.update(LOCALAPPDATA=str(user_data), XDG_DATA_HOME=str(user_data), HOME=str(root / 'home'))
    # Retain only Windows OS utilities; neither branch exposes the installed Python.
    env['PATH'] = str(Path(env.get('SystemRoot', 'C:/Windows')) / 'System32') if os.name == 'nt' else ''
    env['PYTHONIOENCODING'] = 'utf-8'
    checked = subprocess.run([str(exe), '--self-check'], cwd=cwd, env=env, capture_output=True, timeout=40)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert b'OFFLINE SELF-CHECK OK' in checked.stdout
    with socket.socket() as free:
        free.bind(('127.0.0.1', 0))
        port = free.getsockname()[1]
    with socket.socket() as occupied:
        if os.name == 'nt':
            occupied.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        occupied.bind(('127.0.0.1', 0))
        occupied.listen(1)
        rejected = subprocess.run([str(exe), '--no-browser', '--port', str(occupied.getsockname()[1])],
                                  env=env, cwd=cwd, capture_output=True, timeout=15)
        assert rejected.returncode != 0, 'Launch did not reject an unrelated occupied port'
    process = None
    log_path = root / 'server.log'
    try:
        with log_path.open('wb') as log:
            process, base = start(exe, env, cwd, port, log)
            assert b'<html' in request(base, '/').lower(), 'Missing dashboard HTML'
            demo = request(base, '/api/demo')
            preview = request(base, '/api/preview', {'url': demo['sample_url'], 'fields': demo['fields']})
            assert preview['row'], 'Empty demo preview'
            job = request(base, '/api/jobs', {'urls': demo['urls'], 'fields': demo['fields'], 'reviewed': True})
            job_id = job['id']
            request(base, f'/api/jobs/{job_id}/run', {})
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                result = request(base, f'/api/jobs/{job_id}')
                if result['status'] == 'complete':
                    break
                time.sleep(.1)
            assert result['completed'] == 30 and result['failed'] == 0, result
            exported = request(base, f'/api/jobs/{job_id}/export?format=csv')
            rows = list(csv.reader(io.StringIO(exported.decode('utf-8-sig'))))
            assert len(rows) == 31 and 'source_url' in rows[0]
            exported = request(base, f'/api/jobs/{job_id}/export?format=xlsx')
            with zipfile.ZipFile(io.BytesIO(exported)) as workbook:
                assert 'xl/worksheets/sheet1.xml' in workbook.namelist()
                assert workbook.read('xl/worksheets/sheet1.xml').count(b'<row ') == 31
            rejected = subprocess.run([str(exe), '--no-browser', '--port', str(port)],
                                      env=env, cwd=cwd, capture_output=True, timeout=15)
            assert rejected.returncode != 0, 'Second launch silently reused an occupied port'
            assert request(base, '/api/health')['status'] == 'ok', 'Second launch disturbed first server'
            stop(process)
            process = None
            assert (user_data / 'WebSheetAgent' / 'websheet.sqlite3').is_file(), 'Database not in user data directory'
            process, base = start(exe, env, cwd, port, log)
            persisted = request(base, f'/api/jobs/{job_id}')
            assert persisted['completed'] == 30 and persisted['status'] == 'complete', 'Restart lost saved rows'
            stop(process)
            process = None
            assert not list(cwd.rglob('*.sqlite3')), 'Application wrote data to working directory'
            assert not list(bundle.rglob('*.sqlite3')), 'Application wrote data into installed bundle'
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait()
        print(log_path.read_text(encoding='utf-8', errors='replace') if log_path.exists() else 'No server log')
    print('PACKAGED SMOKE OK: extracted ZIP, isolated PATH/data, health, UI, preview, 30 rows, CSV/XLSX, port rejection, shutdown, restart.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path)
    args = parser.parse_args()
    archives = [args.archive] if args.archive else sorted((ROOT / 'dist').glob('websheet-agent-*.zip'))
    if len(archives) != 1:
        parser.error('Provide --archive or leave exactly one portable ZIP in dist/')
    with tempfile.TemporaryDirectory(prefix='websheet portable smoke ') as directory:
        verify(archives[0].resolve(), Path(directory))


if __name__ == '__main__':
    main()
