"""Offline regression checks for portable runtime attribution and fail-closed gates."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('build_portable', Path(__file__).resolve().parents[1] / 'scripts/build_portable.py')
build = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build)


class PackagingNoticeTests(unittest.TestCase):
    def test_openssl_actual_patch_not_legacy_tuple(self):
        for text, expected in [('OpenSSL 3.0.16 11 Feb 2025', '3.0.16'),
                               ('OpenSSL 3.5.4 30 Sep 2025', '3.5.4'), ('OpenSSL 3.0.0', '3.0.0')]:
            self.assertEqual(build.openssl_release(text), expected)
        # 3.0.16 is encoded as (3, 0, 0, 16, 0); slicing would incorrectly say 3.0.0.
        self.assertNotEqual(build.openssl_release('OpenSSL 3.0.16 11 Feb 2025'), '.'.join(map(str, (3, 0, 0, 16, 0)[:3])))

    def test_unrecognized_or_prerelease_openssl_fails_closed(self):
        for text in ['LibreSSL 3.0.16', 'OpenSSL 1.1.1w', 'OpenSSL 3.0.0-dev', 'unknown']:
            with self.assertRaises(RuntimeError):
                build.openssl_release(text)

    def test_linux_uuid_has_specific_notice_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs = root / 'docs' / 'libuuid1'
            docs.mkdir(parents=True)
            (docs / 'copyright').write_text('Synthetic util-linux UUID notice')
            output = root / 'out'
            output.mkdir()
            build.collect_linux_notices(output, ['_internal/libuuid.so.1'], root / 'docs', root / 'common')
            self.assertTrue((output / 'system-runtime/libuuid1-copyright.txt').is_file())
            rows = json.loads((output / 'system-runtime/bundled-libraries.json').read_text())
            self.assertEqual(rows[0]['binary'], '_internal/libuuid.so.1')
            self.assertEqual(rows[0]['package'], 'libuuid1')

    def test_unknown_readline_or_missing_notice_blocks_archive(self):
        for library in ['libreadline.so.8', 'libtinfo.so.6', 'libunknown.so.1', 'libuuid.so.1']:
            with self.subTest(library=library), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                with self.assertRaises(RuntimeError):
                    build.collect_linux_notices(root, [f'_internal/{library}'], root / 'absent', root / 'common')

    def test_windows_external_manifest_preserves_exact_versions(self):
        props = b'''<Project xmlns="http://schemas.microsoft.com/developer/msbuild/2003"><PropertyGroup>
        <lzmaDir>$(ExternalsDir)xz-5.2.5</lzmaDir><zlibDir>$(ExternalsDir)zlib-1.3.1</zlibDir>
        <sqlite3Dir>$(ExternalsDir)sqlite-3.49.1.0</sqlite3Dir></PropertyGroup></Project>'''
        with tempfile.TemporaryDirectory() as tmp, patch.object(build, 'download_notice', return_value=props), \
             patch.object(build.platform, 'python_version', return_value='3.12.10'), \
             patch('sqlite3.sqlite_version', '3.49.1'), patch('zlib.ZLIB_RUNTIME_VERSION', '1.3.1'):
            sources = build.windows_external_sources(Path(tmp))
            self.assertIn('v3.12.10/Modules/expat/COPYING', sources['Expat-COPYING.txt'])
            self.assertIn('xz-5.2.5/COPYING', sources['XZ-COPYING.txt'])
            self.assertIn('version-3.49.1/LICENSE.md', sources['SQLite-LICENSE.md'])
            self.assertTrue((Path(tmp) / 'windows-externals.json').is_file())
