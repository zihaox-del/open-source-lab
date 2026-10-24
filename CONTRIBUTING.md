# Contributing

Small, focused contributions are welcome. Discuss larger features in an issue before implementation.

1. Use Python 3.11+ on Linux/macOS and a virtual environment.
2. Install `requirements.txt`. The optional browser dependency is separate.
3. Run `python -m unittest discover -s tests -v` and `python -m compileall -q websheet tests`.
4. Add deterministic, offline tests for new behavior; never commit API keys, real user data, databases or credentials.
5. Keep model suggestions separate from deterministic execution. Do not weaken same-origin, public-IP, local-only or explicit upload boundaries.
6. Document supported versus untested behavior. Browser-dependent tests must explicitly skip when not enabled; do not report mocks as real browser validation.
7. Submit a concise pull request with purpose, tests actually run, and limitations.

The project is MIT licensed. Contributions are accepted under the same license. Please be respectful and focus feedback on behavior and code.
