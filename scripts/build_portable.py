"""Build an OS-native, directory-based distribution. Run in a clean virtualenv."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata as metadata
import json
import platform
import shutil
import subprocess
import sys
import sysconfig
import ssl
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = "WebSheet-Agent"


def collect_notices(destination: Path) -> None:
    """Preserve installed distributions' original notices, not guessed licenses."""
    destination.mkdir(parents=True)
    inventory = []
    for dist in sorted(metadata.distributions(), key=lambda item: item.metadata['Name'].lower()):
        name = dist.metadata['Name']
        directory = destination / f"{name}-{dist.version}"
        directory.mkdir(exist_ok=True)
        (directory / 'METADATA.txt').write_text(dist.read_text('METADATA') or str(dist.metadata), encoding='utf-8')
        copied = []
        for entry in dist.files or []:
            if not any(part.lower().startswith(('license', 'licence', 'copying', 'notice', 'authors')) for part in entry.parts):
                continue
            source = Path(dist.locate_file(entry))
            if not source.is_file():
                continue
            # Flatten parent traversal from wheel RECORD while preserving a unique name.
            safe = '__'.join(part for part in entry.parts if part not in ('.', '..'))
            shutil.copyfile(source, directory / safe)
            copied.append(safe)
        inventory.append({'name': name, 'version': dist.version, 'license_files': copied})
    (destination / 'build-environment.json').write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding='utf-8')
    stdlib = Path(sysconfig.get_path('stdlib'))
    candidates = [Path(sys.base_prefix) / 'LICENSE.txt', stdlib / 'LICENSE.txt', stdlib.parent / 'LICENSE.txt', stdlib / 'LICENSE']
    python_license = next((path for path in candidates if path.is_file()), None)
    if python_license is None:
        raise RuntimeError('Python LICENSE.txt was not found. Use an official Python installation before distributing.')
    shutil.copyfile(python_license, destination / 'PYTHON-LICENSE.txt')
    (destination / 'runtime.txt').write_text(f'Python {sys.version}\nPlatform: {platform.platform()}\n', encoding='utf-8')


def collect_native_notices(destination: Path, bundle: Path) -> None:
    """Fetch unmodified official notices tied to the actual native runtime versions."""
    from lxml import etree
    xml = '.'.join(map(str, etree.LIBXML_VERSION))
    xslt = '.'.join(map(str, etree.LIBXSLT_VERSION))
    openssl = '.'.join(map(str, ssl.OPENSSL_VERSION_INFO[:3]))
    if ssl.OPENSSL_VERSION_INFO[0] < 3:
        raise RuntimeError('This notice collector requires OpenSSL 3 or later')
    lxml = metadata.version('lxml')
    sources = {
        'OpenSSL-LICENSE.txt': f'https://raw.githubusercontent.com/openssl/openssl/openssl-{openssl}/LICENSE.txt',
        'libxml2-Copyright.txt': f'https://raw.githubusercontent.com/GNOME/libxml2/v{xml}/Copyright',
        'libxml2-dict.c.txt': f'https://raw.githubusercontent.com/GNOME/libxml2/v{xml}/dict.c',
        'libxml2-list.c.txt': f'https://raw.githubusercontent.com/GNOME/libxml2/v{xml}/list.c',
        'libxslt-Copyright.txt': f'https://raw.githubusercontent.com/GNOME/libxslt/v{xslt}/Copyright',
        'lxml-ElementTree.txt': f'https://raw.githubusercontent.com/lxml/lxml/lxml-{lxml}/doc/licenses/elementtree.txt',
        'lxml-BSD.txt': f'https://raw.githubusercontent.com/lxml/lxml/lxml-{lxml}/doc/licenses/BSD.txt',
    }
    records = []
    for name, url in sources.items():
        with urllib.request.urlopen(url, timeout=30) as response:
            data = response.read(2_000_001)
        if not 100 <= len(data) <= 2_000_000 or b'<html' in data[:300].lower():
            raise RuntimeError(f'Invalid upstream license response: {url}')
        (destination / name).write_bytes(data)
        records.append({'file': name, 'url': url, 'sha256': hashlib.sha256(data).hexdigest()})
    (destination / 'native-sources.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
    native = sorted(str(path.relative_to(bundle)) for path in bundle.rglob('*')
                    if path.is_file() and (path.suffix.lower() in ('.dll', '.pyd', '.dylib') or '.so' in path.name))
    (destination / 'native-files.json').write_text(json.dumps(native, indent=2), encoding='utf-8')
    if sys.platform.startswith('linux'):
        # Ubuntu CI and Debian-based builders supply complete distribution notices,
        # including GCC's runtime exception, alongside the shared runtime libraries.
        system = destination / 'system-runtime'
        system.mkdir()
        for package in ('libgcc-s1', 'libc6', 'libssl3', 'libssl3t64', 'libffi8', 'libbz2-1.0',
                        'liblzma5', 'libexpat1', 'libsqlite3-0', 'zlib1g'):
            notice = Path('/usr/share/doc') / package / 'copyright'
            if notice.is_file():
                shutil.copyfile(notice, system / f'{package}-copyright.txt')
        for notice in Path('/usr/share/common-licenses').glob('*'):
            if notice.is_file():
                shutil.copyfile(notice, system / notice.name)
        if any('libgcc_s' in item for item in native) and not (system / 'libgcc-s1-copyright.txt').exists():
            raise RuntimeError('Bundled libgcc runtime requires its distribution copyright and exception notices')



def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist')
    args = parser.parse_args()
    output = args.output.resolve()
    work = ROOT / 'build' / 'portable'
    work.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    entry = work / 'entry.py'
    entry.write_text('from websheet.launcher import main\n\nif __name__ == "__main__":\n    raise SystemExit(main())\n', encoding='utf-8')
    subprocess.run([
        sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir', '--console',
        '--name', NAME, '--distpath', str(output), '--workpath', str(work / 'pyinstaller'),
        '--specpath', str(work), '--paths', str(ROOT),
        '--add-data', f'{ROOT / "websheet" / "static"}:websheet/static',
        '--collect-submodules', 'uvicorn', '--collect-data', 'certifi',
        '--exclude-module', 'playwright', '--exclude-module', 'tkinter',
        str(entry),
    ], cwd=ROOT, check=True)
    bundle = output / NAME
    shutil.copyfile(ROOT / 'LICENSE', bundle / 'LICENSE.txt')
    shutil.copyfile(ROOT / 'docs' / 'PORTABLE_README.txt', bundle / 'START_HERE.txt')
    shutil.copyfile(ROOT / 'THIRD_PARTY_NOTICES.md', bundle / 'THIRD_PARTY_NOTICES.md')
    collect_notices(bundle / 'licenses')
    collect_native_notices(bundle / 'licenses', bundle)
    archive_name = f'websheet-agent-{platform.system().lower()}-{platform.machine().lower()}'
    archive = Path(shutil.make_archive(str(output / archive_name), 'zip', root_dir=output, base_dir=NAME))
    with archive.open('rb') as source:
        digest = hashlib.file_digest(source, 'sha256').hexdigest()
    archive.with_suffix('.zip.sha256').write_text(f'{digest}  {archive.name}\n', encoding='ascii')
    print(f'Built {archive}\nSHA256 {digest}\nNot release-qualified until the packaged smoke test passes.')


if __name__ == '__main__':
    main()
