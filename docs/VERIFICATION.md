# Verification record · 2026-10-24

This record describes actual execution, not planned coverage.

## v0.3 verified source and workflows

Qualified source: `aee7e1ea1ddfa846b40c5f1715d7e9d41be26e23`.

- [Tests and real Chromium](https://github.com/zihaox-del/open-source-lab/actions/runs/40052433129): success.
- [Windows/Linux portable builds](https://github.com/zihaox-del/open-source-lab/actions/runs/40052433273): success.
- Python 3.11–3.13 Linux offline matrix: 59 discovered, 54 passed, 5 browser tests explicitly skipped; compile and 30-page synthetic export demo passed.
- Python 3.12 real Chromium: **59 tests passed, no skips**. One renderer test executes bundled JavaScript on 30 pages. Four dashboard tests run the actual localhost app and real DOM interactions, not substituted API/browser results.
- Dashboard coverage includes single-URL entry, parsed text selection, automatic one-row preview, explicit confirmation, revision guards, repeated clicks, refresh/background work, cancellation, pause/resume, history/Back/Forward, actual CSV/XLSX contents, network/read errors, no candidates, partial failures and stale asynchronous responses.
- Five packaging-notice regressions cover full OpenSSL patch versions, Windows externals manifests and fail-closed native-library notice mapping.

Local Linux/Python 3.12 also passed 54 tests with 5 explicit browser skips, compile checks and the 30-page demo. Chromium cannot create a local process socket in this sandbox, so remote passes are not described as local passes. DeepSeek uses mock transports only; no real key or paid model call was used.

## Actual portable executable acceptance

Both `windows-latest` / x64 and Ubuntu 22.04 / x86_64 built their native directory bundle and ZIP, then ran the executable extracted from that exact ZIP. The smoke runner removed Python from PATH and used an unrelated working directory and isolated user-data directory.

Verified: offline self-check; localhost health and real HTML; preview; 30/30 synthetic rows; CSV/XLSX with 30 data rows plus header; rejection of unrelated occupied ports and duplicate launch; graceful stop; restart with saved history; no database written into the application bundle or working directory. The Windows suite also exercised actual cross-process locking. The first Windows CI exposed test-fixture issues (unclosed legacy SQLite handle and missing USERPROFILE); these were corrected without weakening application locking or cleanup assertions.

Both build jobs published only after the exact-package smoke passed. Downloaded archives were checked against the Actions artifact digest and the inner ZIP's accompanying SHA256. Inner application ZIPs for the qualified source:

- `websheet-agent-windows-amd64.zip`: 21,529,295 bytes; SHA256 `41fd8e2afec88be85413de8a0c0fbf0aeaa0773661889b974483a4d01d4bfc3c`.
- `websheet-agent-linux-x86_64.zip`: 36,163,892 bytes; SHA256 `332a5f7259a34da84c086c5d20e19c50af93a4d05d86fecf88e6baa4505fc810`.

These hashes identify those specific build artifacts, not a reproducibility guarantee for future rebuilds. Actions artifacts expire after 14 days and normally require GitHub login. No GitHub Release or signed installer is claimed. Windows and Linux packages are unsigned; do not disable operating-system protection or bypass warnings. macOS has no portable build.

## Native-notice inspection

The downloaded Windows archive includes Python/Microsoft redistributable conditions, package licenses, actual OpenSSL 3.0.16 license, Expat, zlib, XZ and SQLite notices. `windows-externals.json` records CPython 3.12.10's official build manifest, runtime Expat 2.7.1, zlib 1.3.1 and SQLite 3.49.1. XZ 5.2.5 is tied to that build manifest because the Python `_lzma` API does not expose its runtime version.

The Linux archive no longer includes unused readline/libtinfo. Its actual top-level native libraries map to retained distribution copyright files, including libuuid1 and libgcc's runtime exception. Unknown top-level system libraries or missing notices fail the build. Original dependency notices remain their own licenses; this inventory is not a legal-completeness certification or independent security audit.

Both actual archives contain the reviewed UI source (Windows checkout line endings normalized for comparison), no application database, `.env` file, API key file, Playwright or Chromium payload. API keys were neither supplied nor needed in this work.

## Screenshot review

[Dashboard evidence run](https://github.com/zihaox-del/open-source-lab/actions/runs/40051806596) produced eight synthetic-only images from the same runtime/UI source. Actual pixels were reviewed for desktop input/selection/completion and 390px selection/completion/partial-failure states. Chinese text and main calls to action were readable; no blocking overlap or clipping was observed. Narrow result tables scroll horizontally, including columns beyond the initial viewport. Screenshots are captured after completion transitions settle, with capture animations disabled.

This is acceptance of those captured synthetic states, not all viewports, real-site structures, keyboard/screen-reader behavior or a complete accessibility audit. Tests confine browser traffic to localhost; the synthetic fetch delay only makes pause/progress observable.

## Remaining limitations

- Public extraction supports authorized static HTTPS pages only. A previous local example.com attempt could not resolve DNS. CI validates synthetic pages/mocks, not arbitrary public sites or live website compatibility.
- Public JavaScript pages, logins, CAPTCHA bypass and hosted multi-user service are unsupported. Optional browser-demo is source-only and restricted to bundled synthetic content.
- Paid DeepSeek responses/billing, macOS, WSL and all Windows/Linux device variants are unverified. The Windows runner pass is not evidence for every Windows version.
- There is no independent penetration test, full accessibility audit, code signing or automatic updating. Dependencies are pinned directly, not a complete transitive reproducibility lock.
- Earlier v0.1/v0.2 browser and Python results remain historical; they are not used as substitutes for the v0.3 runs above.

Do not remove a limitation until its corresponding check has actually passed.
