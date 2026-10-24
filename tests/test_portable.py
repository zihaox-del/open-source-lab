"""Portable startup and real cross-process lock tests (Windows and POSIX)."""
import json
import io
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from websheet.launcher import main, open_when_ready, reserve_socket, self_check
from websheet.locking import try_lock
from websheet.paths import default_db_path
from websheet.store import Store
from websheet.core import Column, fetch

ROOT = Path(__file__).resolve().parents[1]


class PortableTests(unittest.TestCase):
    def test_default_data_is_outside_working_directory(self):
        with patch.dict(os.environ, {}, clear=True):
            path = default_db_path()
        self.assertTrue(path.is_absolute())
        self.assertEqual(path.name, 'websheet.sqlite3')
        self.assertEqual(path.parent.name, 'WebSheetAgent')
        self.assertNotEqual(path.parent, ROOT / 'data')

    def test_relative_platform_data_environment_does_not_write_into_bundle(self):
        with patch.dict(os.environ, {'LOCALAPPDATA': 'relative', 'XDG_DATA_HOME': 'relative'}, clear=True):
            self.assertTrue(default_db_path().is_absolute())

    def test_explicit_data_override_is_preserved(self):
        with patch.dict(os.environ, {'WEBSHEET_DB': '~/custom.sqlite3'}):
            self.assertEqual(default_db_path(), Path.home() / 'custom.sqlite3')

    def test_same_process_lock_and_reacquisition(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'test.lock'
            lock = try_lock(path)
            self.assertIsNotNone(lock)
            self.assertIsNone(try_lock(path))
            lock.close()
            with try_lock(path):
                self.assertIsNone(try_lock(path))

    def test_cross_process_lock_prevents_false_recovery_and_releases_on_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'test.sqlite3'
            store = Store(path)
            job = store.create(['demo://catalog/1'], [Column(name='name', selector='h1')], True)
            script = '''import sys
from websheet.store import Store
store = Store(sys.argv[1])
lock = store._claim(sys.argv[2])
print('LOCKED', flush=True)
sys.stdin.read()
'''
            process = subprocess.Popen([sys.executable, '-u', '-c', script, str(path), job['id']],
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       cwd=ROOT, text=True)
            try:
                self.assertEqual(process.stdout.readline().strip(), 'LOCKED')
                self.assertEqual(Store(path).get(job['id'])['status'], 'running')
                self.assertIsNone(store._lock())
                process.terminate()
                process.wait(timeout=10)
                self.assertEqual(Store(path).get(job['id'])['status'], 'interrupted')
                self.assertEqual(Store(path).run(job['id'])['completed'], 1)
            finally:
                if process.poll() is None:
                    process.kill()
                process.communicate(timeout=10)

    def test_busy_port_never_opens_browser_or_initializes_store(self):
        with reserve_socket(0) as occupied:
            occupied.listen()
            port = occupied.getsockname()[1]
            with patch('websheet.app.create_app') as app, patch('websheet.launcher.webbrowser.open') as browser:
                self.assertEqual(main(['--port', str(port)]), 1)
                app.assert_not_called()
                browser.assert_not_called()

    def test_browser_only_opens_after_own_server_health(self):
        server = type('Server', (), {'started': False})()
        stop = threading.Event()
        with patch('websheet.launcher.webbrowser.open') as browser, patch('websheet.launcher.urllib.request.build_opener') as opener:
            thread = threading.Thread(target=open_when_ready, args=(server, 'http://127.0.0.1:8765', stop))
            thread.start()
            time.sleep(.15)
            opener.return_value.open.assert_not_called()
            browser.assert_not_called()
            stop.set()
            thread.join(timeout=2)
            self.assertFalse(thread.is_alive())

    def test_browser_opens_once_after_successful_health(self):
        server = type('Server', (), {'started': True})()
        stop = threading.Event()
        with patch('websheet.launcher.webbrowser.open') as browser, patch('websheet.launcher.urllib.request.build_opener') as opener:
            opener.return_value.open.return_value = io.StringIO(json.dumps({'status': 'ok', 'app': 'websheet-agent'}))
            thread = threading.Thread(target=open_when_ready, args=(server, 'http://127.0.0.1:8765', stop))
            thread.start()
            thread.join(timeout=3)
            stop.set()
            self.assertFalse(thread.is_alive())
            browser.assert_called_once_with('http://127.0.0.1:8765')

    def test_shutdown_finishes_current_row_and_preserves_pending_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / 'test.sqlite3')
            job = store.create(['demo://catalog/1', 'demo://catalog/2'], [Column(name='name', selector='h1')], True)
            entered, release = threading.Event(), threading.Event()
            def read(url):
                entered.set()
                release.wait(5)
                return fetch(url)
            store.start(job['id'], read)
            self.assertTrue(entered.wait(2))
            stopped = threading.Thread(target=store.shutdown)
            stopped.start()
            self.assertTrue(store._stopping.wait(2))
            release.set()
            stopped.join(timeout=5)
            self.assertFalse(stopped.is_alive())
            result = Store(store.path).get(job['id'])
            self.assertEqual((result['status'], result['completed']), ('paused', 1))
            self.assertEqual(Store(store.path).run(job['id'])['completed'], 2)

    def test_offline_self_check(self):
        with patch('socket.create_connection', side_effect=AssertionError('Network forbidden')):
            self.assertEqual(self_check(), 0)
