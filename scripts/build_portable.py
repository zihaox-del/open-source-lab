"""Build an OS-native, directory-based distribution. Run in a clean virtualenv."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata as metadata
import json
import platform
import re
import shutil
import subprocess
import sys
import sysconfig
import ssl
import urllib.request
import xml.etree.ElementTree as ET
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
    (destination / 'runtime.txt').write_text(f'Python {sys.version}\nPlatform: {platform.platform()}\nOpenSSL: {ssl.OPENSSL_VERSION}\n', encoding='utf-8')


def openssl_release(version_text: str) -> str:
    # OPENSSL_VERSION_INFO is legacy-encoded: 3.0.16 may be (3, 0, 0, 16, 0).
    # The public version string carries the actual release tag, including patch.
    match = re.match(r'^OpenSSL (\d+\.\d+\.\d+)(?:\s|$)', version_text)
    if not match or int(match.group(1).split('.')[0]) < 3:
        raise RuntimeError('Expected a stable OpenSSL 3+ release for exact license attribution')
    return match.group(1)


LINUX_NOTICES = {
    'libgcc_s.so': ('libgcc-s1',),
    'libstdc++.so': ('libstdc++6',),
    'libc.so': ('libc6',),
    'libm.so': ('libc6',),
    'libpthread.so': ('libc6',),
    'libdl.so': ('libc6',),
    'librt.so': ('libc6',),
    'libssl.so': ('libssl3', 'libssl3t64'),
    'libcrypto.so': ('libssl3', 'libssl3t64'),
    'libffi.so': ('libffi8', 'libffi7'),
    'libbz2.so': ('libbz2-1.0',),
    'liblzma.so': ('liblzma5',),
    'libexpat.so': ('libexpat1',),
    'libsqlite3.so': ('libsqlite3-0',),
    'libz.so': ('zlib1g',),
    'libuuid.so': ('libuuid1', 'util-linux'),
}


def collect_linux_notices(destination: Path, native: list[str], doc_root=Path('/usr/share/doc'),
                          common_root=Path('/usr/share/common-licenses')) -> None:
    """Fail closed on unreviewed bundled system libraries or missing notices."""
    system = destination / 'system-runtime'
    system.mkdir()
    records = []
    for item in native:
        path = Path(item)
        name = path.name
        # Package extensions have wheel notices; CPython has PYTHON-LICENSE.txt.
        if path.parent.as_posix() != '_internal' or not name.startswith('lib') or '.so' not in name:
            continue
        if name.startswith('libpython'):
            continue
        packages = next((value for prefix, value in LINUX_NOTICES.items() if name.startswith(prefix)), None)
        if packages is None:
            raise RuntimeError(f'Unreviewed bundled Linux system library: {name}')
        found = next(((package, doc_root / package / 'copyright') for package in packages
                      if (doc_root / package / 'copyright').is_file()), None)
        if found is None:
            raise RuntimeError(f'Missing distribution copyright for bundled library: {name}')
        package, notice = found
        filename = f'{package}-copyright.txt'
        shutil.copyfile(notice, system / filename)
        records.append({'binary': item, 'package': package, 'notice': filename})
    for notice in common_root.glob('*'):
        if notice.is_file():
            shutil.copyfile(notice, system / notice.name)
    (system / 'bundled-libraries.json').write_text(json.dumps(records, indent=2), encoding='utf-8')


def download_notice(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=30) as response:
        data = response.read(2_000_001)
    if not 100 <= len(data) <= 2_000_000 or b'<html' in data[:300].lower():
        raise RuntimeError(f'Invalid upstream license response: {url}')
    return data


def windows_external_sources(destination: Path) -> dict[str, str]:
    """Use the exact official CPython release's external-library build manifest."""
    import sqlite3
    import zlib
    import pyexpat
    release = platform.python_version()
    base = f'https://raw.githubusercontent.com/python/cpython/v{release}'
    props_url = base + '/PCbuild/python.props'
    props = download_notice(props_url)
    (destination / 'CPython-Windows-python.props').write_bytes(props)
    tree = ET.fromstring(props)
    def dependency(element, prefix):
        node = tree.find(f'.//{{http://schemas.microsoft.com/developer/msbuild/2003}}{element}')
        match = re.search(re.escape(prefix) + r'-(\d+(?:\.\d+)+)', node.text if node is not None else '')
        if not match:
            raise RuntimeError(f'Cannot identify official CPython external: {element}')
        return match.group(1)
    versions = {name: dependency(element, name) for name, element in
                [('xz', 'lzmaDir'), ('zlib', 'zlibDir'), ('sqlite', 'sqlite3Dir')]}
    if versions['zlib'] != zlib.ZLIB_RUNTIME_VERSION or versions['sqlite'].removesuffix('.0') != sqlite3.sqlite_version:
        raise RuntimeError('Windows runtime libraries differ from official CPython release; review notices manually')
    evidence = {'python': release, 'manifest_url': props_url, 'manifest_sha256': hashlib.sha256(props).hexdigest(),
                'expected_build_externals': versions, 'runtime_expat': pyexpat.EXPAT_VERSION,
                'runtime_zlib': zlib.ZLIB_RUNTIME_VERSION, 'runtime_sqlite': sqlite3.sqlite_version,
                'xz_version_basis': 'Official CPython build manifest; _lzma exposes no runtime version API'}
    (destination / 'windows-externals.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    deps = 'https://raw.githubusercontent.com/python/cpython-source-deps'
    return {
        'Expat-COPYING.txt': base + '/Modules/expat/COPYING',
        'zlib-LICENSE.txt': f"{deps}/zlib-{versions['zlib']}/LICENSE",
        'XZ-COPYING.txt': f"{deps}/xz-{versions['xz']}/COPYING",
        'XZ-COPYING.LGPLv2.1.txt': f"{deps}/xz-{versions['xz']}/COPYING.LGPLv2.1",
        'XZ-COPYING.GPLv2.txt': f"{deps}/xz-{versions['xz']}/COPYING.GPLv2",
        'XZ-COPYING.GPLv3.txt': f"{deps}/xz-{versions['xz']}/COPYING.GPLv3",
        'SQLite-LICENSE.md': f'https://raw.githubusercontent.com/sqlite/sqlite/version-{sqlite3.sqlite_version}/LICENSE.md',
    }


def collect_native_notices(destination: Path, bundle: Path) -> None:
    """Fetch unmodified official notices tied to the actual native runtime versions."""
    from lxml import etree
    xml = '.'.join(map(str, etree.LIBXML_VERSION))
    xslt = '.'.join(map(str, etree.LIBXSLT_VERSION))
    openssl = openssl_release(ssl.OPENSSL_VERSION)
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
    if sys.platform == 'win32':
        sources.update(windows_external_sources(destination))
    records = []
    for name, url in sources.items():
        data = download_notice(url)
        (destination / name).write_bytes(data)
        records.append({'file': name, 'url': url, 'sha256': hashlib.sha256(data).hexdigest()})
    (destination / 'native-sources.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
    native = sorted(str(path.relative_to(bundle)) for path in bundle.rglob('*')
                    if path.is_file() and (path.suffix.lower() in ('.dll', '.pyd', '.dylib') or '.so' in path.name))
    (destination / 'native-files.json').write_text(json.dumps(native, indent=2), encoding='utf-8')
    if sys.platform.startswith('linux'):
        collect_linux_notices(destination, native)



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
        '--exclude-module', 'readline',
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
