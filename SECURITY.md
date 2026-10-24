# Security policy

This is an early, local-only alpha, not a hardened hosted service. Never bind it to a public interface or run it for untrusted remote users. The app has no authentication or tenant isolation.

## Intended boundary

- Public static HTML only over HTTPS/443. All DNS answers must be public; the checked IP is pinned for the connection while TLS validates the original hostname. No redirect following, cookies, proxies or subresources.
- Browser-demo mode accepts only bundled synthetic `demo://catalog` pages, uses a fresh browser context, blocks service workers and every page network route, and sets offline mode. It is not an external browser automation adapter.
- Models suggest bounded selector data, never executable instructions. API keys stay in server-side environment variables. A separate explicit action acknowledges uploading a page summary to DeepSeek.
- SQLite data is plaintext. Export neutralizes spreadsheet formulas and illegal XML control characters, but you must still review files before sharing them.

## Reporting

Do not post API keys, private URLs, extracted private content or weaponized payloads in a public issue. If GitHub private vulnerability reporting is enabled for the repository, use its Security → Report a vulnerability control. If unavailable, open a minimal public issue requesting a private reporting channel, without disclosing exploit details. No security email or reporting SLA is claimed at this stage.

No independent audit has been performed. Supported fixes target the current main branch. Disclosure and fixes will be documented transparently; do not treat this policy as a guarantee of security.
