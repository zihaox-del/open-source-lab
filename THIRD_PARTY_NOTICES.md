# Third-party notices for portable distributions

WebSheet Agent is distributed under the MIT license in `LICENSE.txt` (source: `LICENSE`).
The portable distribution includes a Python interpreter, native libraries, and third-party
Python packages. Those components remain under their own licenses; the project's MIT
license does not replace them.

The build script copies original license/notice files and package metadata from its build
environment into `licenses/`. `licenses/PYTHON-LICENSE.txt` contains the Python license
and bundled-library notices provided by that Python installation. Package-specific notices
(including alternate LICENCE spellings and certifi's certificate data license)
are preserved when supplied by the installed wheels. Additional official OpenSSL,
libxml2/libxslt, and lxml ElementTree/BSD notices are downloaded from version-matched
upstream tags during the build. Their URLs and SHA256 values are recorded in
`native-sources.json`; native runtime files are listed in `native-files.json`.
These source files are copied as text only and are never executed. The metadata files identify the
upstream projects and their declared licenses. `build-environment.json` records versions;
it is a build-environment inventory, not a claim that every listed package is in the binary.
Build-only tools can therefore appear in this inventory.

PyInstaller's bootloader distribution exception permits distributing built applications
under their own terms. Its original license and exception are copied with the PyInstaller
metadata. Upstream: https://pyinstaller.org/ ; https://github.com/pyinstaller/pyinstaller

Core direct dependencies are FastAPI, Uvicorn, Pydantic, HTTPX, lxml, and openpyxl,
along with their runtime dependencies. Playwright and Chromium are intentionally excluded
from the portable distribution. No remote model, browser binary, or API credential is
required for the local synthetic demo.

Maintainers should build in a clean environment, retain this notice directory in release
ZIPs, and review native-library and package licensing whenever dependencies or build
platforms change. Metadata alone is not a substitute for missing upstream license text.

Linux bundles deliberately exclude the unused readline module. The build rejects
unreviewed top-level system shared libraries and requires the distribution copyright
for each included library, including util-linux/libuuid when present. The exact binary
to notice mapping is in `system-runtime/bundled-libraries.json`; full referenced common
license texts are retained. This inventory is evidence, not a legal-completeness guarantee.

Windows bundles also retain Expat's notice from the exact CPython release, zlib and
XZ/liblzma notices from its official external-source manifest, and SQLite's official
public-domain/source-license information. `windows-externals.json` records this evidence;
zlib and SQLite versions are checked against runtime values. XZ version attribution is
based on the official CPython build manifest because `_lzma` exposes no runtime version API.
OpenSSL notice URLs use the full public release version, not the legacy numeric tuple.
