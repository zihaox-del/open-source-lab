# Verification record · 2026-10-24

This record describes actual execution, not planned coverage.

## Passed locally

Environment: Linux sandbox, Python 3.12. Direct dependency versions match requirements.txt.

- `python -m unittest discover -s tests -v`: **21 discovered, 20 passed, 1 explicitly skipped**. The skipped test requires a real Chromium browser.
- `python -m compileall -q websheet tests`: passed.
- `python scripts/demo.py`: **30/30 synthetic pages succeeded, 0 failures, XLSX contains 30 data rows + header**.
- Frontend extracted JavaScript: `node --check` passed.
- Independent review exercised duplicate/resume behavior, hostile selectors, formula export and XML controls.

TestClient drives real application routes and SQLite in-process, without a listening network socket. Fetch security tests use controlled mocks, not live external traffic. DeepSeek tests use `httpx.MockTransport`; no key, paid API call or real model response was used.

## Passed in GitHub Actions

Commit: `0158cb5b27ce2b44f4fb3d1d31f7b1629f38ba34`.
[Verified run](https://github.com/zihaox-del/open-source-lab/actions/runs/40048939225).

- Linux / Python 3.11, 3.12 and 3.13: offline tests, compile checks and 30-page synthetic export demo passed.
- Separate Python 3.12 browser job installed official Playwright Chromium and set `WEBSHEET_BROWSER_TEST=1`: **21 tests passed, no skips**.
- The real Chromium test executed JavaScript and extracted the expected rendered text on all 30 bundled synthetic pages. Page network access remained blocked; no external website or paid model was accessed by tests.
- This verifies the renderer, not dashboard clicks, screenshots, accessibility or compatibility with arbitrary public sites.
- Local wheel packaging also succeeded with `python -m pip wheel --no-deps --no-build-isolation .`; no package was uploaded to a package index.

## Blocked or not verified

- **Local browser environment:** Chromium failed before navigation because the environment denied `socket()` in `process_singleton_posix.cc` (`Operation not permitted`). An ordinary writable HOME/XDG configuration removed a separate crashpad directory issue but did not remove the socket restriction. No security restriction was bypassed. No browser assertion or screenshot was completed locally. The renderer assertion subsequently passed in GitHub Actions as recorded above; dashboard visual QA remains outstanding.
- **Real public HTTPS extraction:** a read-only `example.com` attempt could not resolve DNS in this sandbox. A permitted escalation path failed in the environment wrapper before execution. Public-network extraction is therefore unverified here.
- **CI scope:** the linked remote run passed. CI uses synthetic pages and mocked model responses, not live public extraction or paid API calls.
- **Platforms:** Linux/Python 3.11–3.13 passed remotely; only Python 3.12 was tested locally. macOS remains untested. Native Windows is unsupported.
- **Visual QA:** dashboard HTML/CSS and interaction code were reviewed, but a browser screenshot/layout/accessibility check remains outstanding.

## Next acceptance checks in a browser-capable environment

1. Install pinned requirements and official Chromium; start `python -m websheet` on loopback.
2. Run the 30-page static synthetic demo. Preview and confirm; ensure 30 success rows and both downloads.
3. Edit a selector after preview: confirmation must reset and batch creation stay disabled.
4. Reload while a task is pending: restore the same task ID and resume only pending rows; completed rows must remain unchanged.
5. Exercise browser-demo through the dashboard with `#rendered`. The lower-level opt-in Chromium test already passed in CI; dashboard interaction still needs acceptance.
6. Confirm browser-demo rejects external URLs, then test an authorized public static HTTPS sample without credentials or private data.
7. Inspect desktop/mobile layout, long errors, network failure recovery, double clicks and keyboard navigation.

Do not remove these limitations until the corresponding checks have actually passed.
