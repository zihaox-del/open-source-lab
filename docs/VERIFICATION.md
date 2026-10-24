# Verification record · 2026-10-24

This record describes actual execution, not planned coverage.

## v0.2 verified in GitHub Actions

Source commit: `cc480bae1628ef2371b1a528573657153dc68b65`.
[Verified run](https://github.com/zihaox-del/open-source-lab/actions/runs/40049894178).

- Linux / Python 3.11, 3.12 and 3.13: offline tests passed (43 discovered, 39 passed, 4 explicit browser skips), compilation passed and the synthetic export demo completed 30/30 pages with zero failures.
- A separate Python 3.12 job installed official Playwright Chromium and enabled `WEBSHEET_BROWSER_TEST=1`: **all 43 tests passed, no skips**.
- Real Chromium executed bundled JavaScript on 30 synthetic pages. Three additional dashboard tests served the actual FastAPI app on localhost and exercised real DOM interaction: no-CSS selection, preview/confirmation, repeated start, refresh during background work, draft cancellation, pause/resume, persistent history, history switching during a run, browser Back/Forward and actual CSV/XLSX download contents.
- Tests did not substitute API responses or browser results. Synthetic fetches use a 60 ms delay to make progress and pause observable; non-demo fetches are rejected, key-like environment variables are removed and dashboard browser requests are restricted to localhost.
- Guided extraction and durability tests cover text-only candidates, bounded selectors, same-origin link discovery/deduplication/caps, malformed URLs, concurrent starts/creates, idempotency, migrations, row-boundary pause/resume, crash recovery and worker-owned browser cleanup.

## Desktop screenshot review

The run produced `synthetic-dashboard-evidence` (artifact ID `12542693927`, three-day retention). Its ZIP was downloaded and SHA-256 verified as `8fe092f391d5313225554b16810694a65ee13951251d50f8f28b3567c2b80143`.

The actual 1440-pixel-wide desktop synthetic-result screenshot was visually reviewed: Chinese labels are readable, no obvious overlap/clipping was observed, and completed rows, history and download controls are coherent. This is acceptance of that captured state, not every viewport or interaction state. The first screenshot caught the 0.3-second progress-bar transition mid-frame despite 30/30 completion; the screenshot test now waits for the bar to reach full width and disables animations for capture.

## Local checks

Linux sandbox / Python 3.12, direct dependency versions matching requirements.txt:

- 43 tests discovered, 39 passed, 4 explicitly skipped. Local Chromium launch failed before navigation because socket creation is denied; no local browser pass is claimed.
- `python -m compileall -q websheet tests`, extracted frontend `node --check`, `python scripts/demo.py` and `python -m websheet.preflight` passed.
- The synthetic demo exported 30 data rows plus a header to XLSX. API checks use TestClient and SQLite in-process.
- DeepSeek checks use `httpx.MockTransport`; no real key, paid call or real model response was used.
- v0.1 wheel packaging passed locally with `python -m pip wheel --no-deps --no-build-isolation .`; no package-index upload occurred. This is not a claim of v0.2 installer acceptance.

## Remaining limitations and acceptance work

- **Live websites:** a previous read-only example.com attempt could not resolve DNS in the local environment. CI uses synthetic pages and controlled mocks, not live public extraction. Arbitrary website compatibility is unverified.
- **Public dynamic pages:** unsupported. Browser-demo only renders bundled synthetic content with page network access blocked. Logins, CAPTCHA bypass and remote multi-user hosting remain out of scope.
- **Visual/accessibility coverage:** one desktop result state was reviewed. Mobile/narrow layouts, keyboard/screen-reader accessibility, long-error states and broader visual regression coverage remain unverified.
- **Platforms:** Linux/Python 3.11–3.13 passed remotely; Python 3.12 passed locally. macOS and WSL remain unverified; native Windows is unsupported.
- **AI:** no live DeepSeek call or billing flow was tested. Sending a page summary remains an explicit user action; model output still requires preview and confirmation.
- **Security:** no independent penetration audit or general-purpose public-browser isolation certification has been performed.

## Earlier baseline

The v0.1 renderer and Python matrix passed at `0158cb5b27ce2b44f4fb3d1d31f7b1629f38ba34` ([run](https://github.com/zihaox-del/open-source-lab/actions/runs/40048939225)): 21 tests with no skips in its Chromium job. That baseline did not verify the dashboard workflows subsequently covered above.

Do not remove remaining limitations until the corresponding checks have actually passed.
