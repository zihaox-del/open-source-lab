# v0.4.0 qualification · 2026-10-24

Qualified source: `47461007effbcc21f83cac405b86003bd41720c8`.

- [Tests and real Chromium](https://github.com/zihaox-del/open-source-lab/actions/runs/40056806191): 86 tests passed, no skips in Chromium job 120761466231. Python 3.11–3.13 offline jobs each passed 78 with 8 explicit browser skips.
- The same run's bounded public-practice job passed three fixed ToScrape book pages using production pinned HTTPS transport, at most four requests including robots. This is invited external fixture evidence, not customer adoption.
- [Native Windows and Linux](https://github.com/zihaox-del/open-source-lab/actions/runs/40056806202): both builds passed actual extracted-ZIP executable smoke with isolated PATH/data/cwd, exact source version and HTML equality, successful three-page review, 30 synthetic rows, CSV/XLSX downloads, occupied-port and second-instance rejection, graceful shutdown and restart.
- Initial CI caught a versioned-health contract regression in launcher/smoke. Both now check the exact current-version health response; an integration regression uses the actual API response and rejects old versions.
- Initial retry fixture incorrectly left another `span`, so a bare-tag rule legitimately matched a different value. The corrected failure fixture removes that tag, and a regression derives the real generated selector and proves extraction fails before repair. Expected two-success/one-failure checks were retained. Semantic-mismatch examples remain, not hidden by the fixture correction.
- Actual desktop comparison and 390px retry-result screenshots were visually inspected: readable controls, explicit semantic-counterexample value and parent link, without obscured confirmation controls in these captured states. Synthetic `REPAIRED-96` is only a rule-repair marker, not a validated price. No all-viewport or accessibility certification.
- Review selects actual first/middle/last URLs, deduplicated and at most three. It does not verify meaning or guarantee unsampled rows. Bare-tag as well as positional selectors can uniquely match semantically wrong values.
- Failed-only drafts require a completed parent with failures. Review receipts bind URL/field/engine/parent configuration, rechecked transactionally. Original rows/exports remain unchanged. Legacy SQLite data and request identities remain compatible.

Local browser startup remains blocked by sandbox socket restrictions; no local DOM pass is claimed. No live paid model, keys, private user data, macOS binary or universal accessibility claim.

Historical records below describe older versions and are not substitutes for the v0.4 evidence above.

# Verification record · 2026-10-24

This record describes actual execution, not planned coverage.

## v0.3.1 static reliability: remotely verified

Qualified v0.3.1 source: `fd2aa4af726f12958d5215dab3b895bb470efc6d`.
[Tests/browser/public fixture](https://github.com/zihaox-del/open-source-lab/actions/runs/40054296216) and [native Windows/Linux packages](https://github.com/zihaox-del/open-source-lab/actions/runs/40054296200) both passed.

- Real Chromium: **74 tests passed, zero skips**, including the new fifth dashboard flow. Python 3.11–3.13 offline jobs: 68 passed, 6 browser tests explicitly skipped. Windows and Linux actual ZIP-extracted executable smoke tests passed for this source, not just an older binary.
- Local Python 3.12: 74 discovered tests, 68 passed, 6 browser tests explicitly skipped. Compile, JavaScript syntax check and 30-page offline XLSX demo passed.
- 14 new offline regression tests cover real `fetch` control flow with mocked HTTP bytes/headers: UTF-8 Chinese, GB18030/GBK, Windows-1252, HTTP-over-meta precedence, BOM/meta/UTF-8 fallback, XHTML declaration, malformed/unsupported encoding and invalid bytes. They do not prove arbitrary-site compatibility or detect every incorrect-but-decodable charset declaration.
- Candidate tests cover complete inline headings, explicit inline hidden ancestors, navigation starvation, the 100-result/5,000-element inspection limits, API metadata, same-origin base resolution, fragment deduplication, cross-origin base rejection and exact link-limit behavior. Selector uniqueness still does not prove semantic correctness: an explicit index-drift counterexample returns the wrong value and is retained as a regression demonstrating the limitation.
- Added a fifth dashboard flow for visible actionable candidate/link truncation hints, nested-heading preview and clearing the warning on a new sample. It uses an explicitly synthetic HTML response, not a live website.
- Opt-in local real-Chromium execution was attempted and failed at browser startup with `socket() failed: Operation not permitted`; both renderer and dashboard setup errored. The new dashboard test has NOT passed locally. The newly linked v0.3.1 remote run subsequently passed; that does not turn the local launch failure into a local pass. Earlier sections below remain historical evidence for their own source versions.
- No new paid model call, private data, redirect/compression support, failure-retry UI or multi-page preview was added. Portable packaging sources and OS-specific locking were unchanged.

### Bounded external practice fixture

The separate opt-in public-fixture job passed all three fixed `books.toscrape.com` pages through the production public-DNS-pinned HTTPS fetcher and extraction code. Exact results matched the previously reviewed titles, prices and UPCs in `tests/fixtures/public_cases.json`. [Observed job](https://github.com/zihaox-del/open-source-lab/actions/runs/40054296216/job/120753721579).

The [official sandbox](https://toscrape.com/) explicitly invites developer scraping tests. Each run is capped at one robots preflight plus three detail requests, at least two seconds apart; there are no retries, cookies, proxies, JavaScript or crawling. The robots step stops on disallow/unexpected/compressed/oversized content; 404 means no published robots file, combined with the separate explicit invitation. Any expectation drift fails for manual review, never silent rebaselining. Local DNS remained blocked; this observed pass was on GitHub's runner.

This closes a limited external-transport fixture gap, not customer adoption, real-world product value or arbitrary-site correctness. The three expected prices are sandbox data, not commercial prices. Positional rules can still return semantically wrong values after page changes; the explicit counterexample test remains and multi-page semantic preview is still deferred.

## Historical v0.3 verified source and workflows

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

- Public extraction supports authorized static HTTPS pages only. A previous local example.com attempt could not resolve DNS. Most CI checks use synthetic pages/mocks; the v0.3.1 job above additionally covers three invited public practice pages, not arbitrary sites or customer websites.
- Public JavaScript pages, logins, CAPTCHA bypass and hosted multi-user service are unsupported. Optional browser-demo is source-only and restricted to bundled synthetic content.
- Paid DeepSeek responses/billing, macOS, WSL and all Windows/Linux device variants are unverified. The Windows runner pass is not evidence for every Windows version.
- There is no independent penetration test, full accessibility audit, code signing or automatic updating. Dependencies are pinned directly, not a complete transitive reproducibility lock.
- Earlier v0.1/v0.2 browser and Python results remain historical; they are not used as substitutes for the v0.3 runs above.

Do not remove a limitation until its corresponding check has actually passed.
