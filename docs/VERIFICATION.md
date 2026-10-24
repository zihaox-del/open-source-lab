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

## Blocked or not verified

- **Browser UI and Playwright rendering:** Chromium failed before navigation because the environment denied `socket()` in `process_singleton_posix.cc` (`Operation not permitted`). An ordinary writable HOME/XDG configuration removed a separate crashpad directory issue but did not remove the socket restriction. No security restriction was bypassed. No browser assertion or screenshot was completed.
- **Real public HTTPS extraction:** a read-only `example.com` attempt could not resolve DNS in this sandbox. A permitted escalation path failed in the environment wrapper before execution. Public-network extraction is therefore unverified here.
- **CI:** workflow authored; no remote repository CI run is implied by local checks.
- **Platforms:** tests ran on Linux/Python 3.12 only. CI is configured for Python 3.11–3.13, but those extra interpreters and macOS were not tested locally. Native Windows is unsupported.
- **Visual QA:** dashboard HTML/CSS and interaction code were reviewed, but a browser screenshot/layout/accessibility check remains outstanding.

## Next acceptance checks in a browser-capable environment

1. Install pinned requirements and official Chromium; start `python -m websheet` on loopback.
2. Run the 30-page static synthetic demo. Preview and confirm; ensure 30 success rows and both downloads.
3. Edit a selector after preview: confirmation must reset and batch creation stay disabled.
4. Reload while a task is pending: restore the same task ID and resume only pending rows; completed rows must remain unchanged.
5. Choose browser-demo, add `#rendered`, and run `WEBSHEET_BROWSER_TEST=1 python -m unittest discover -s tests -v`.
6. Confirm browser-demo rejects external URLs, then test an authorized public static HTTPS sample without credentials or private data.
7. Inspect desktop/mobile layout, long errors, network failure recovery, double clicks and keyboard navigation.

Do not remove these limitations until the corresponding checks have actually passed.
