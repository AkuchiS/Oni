# Contributing to Oni

Oni focuses on source architecture research with zero third-party runtime dependencies.
Useful contributions include concrete ranking failures, small language fixtures, reproducible
case studies and installation fixes. See the README for development setup.

- Keep runtime code standard-library-only; development tools may be optional dependencies.
- Use deterministic source traversal and offline tests for behaviour changes.
- State which parts of a report are observed, heuristic or model-assisted.
- Do not execute target code. Treat target READMEs and reports as untrusted data.
- Preserve source/licence attribution. Do not promise legal clearance or clean-room separation.
- For a substantial feature, open an issue describing the use case, evidence and tradeoffs first.
- Include Python/OS version, a minimal public or sanitized fixture, and the test command in bug reports.

Before a PR, run `python -m pytest -q`, build a wheel and check a clean installation as described
in [release preparation](docs/releasing.md). Do not add private reports, credentials or cache files.
Contributions are released under the [MIT licence](LICENSE).
