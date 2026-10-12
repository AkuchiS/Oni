# Changelog

## 0.2.0rc1 — unreleased

- Require explicit opt-in for model calls; pair endpoint credentials and reject redirects.
- Validate remote repository names and use fresh acquisition directories without deleting old caches.
- Detect GitHub workflows instead of skipping the entire `.github` directory.
- Add Windows path/reparse-point guards and deterministic ranking tie breaks.
- Parse explicit remote prefixes before local path detection; use `./` for literal local names beginning with a remote prefix.
- Add explicit offline CLI/library analysis without process-wide environment changes.
- Add a local stdio MCP server restricted to configured source roots.
- Reject archive links/special files and skip source symlinks.
- Fix optional development dependencies being counted as wheel runtime dependencies in CI.
- Exercise clean wheel installation and expand the Python test matrix.
- Replace shell-profile installer fallback with an isolated virtual environment.
- Add reproducible reports, evaluation instructions and community/release documentation.
- Clarify source excerpts, provider data flow, ranking limits and licence-review boundaries.

## 0.1.0 — existing source baseline

Initial source-analysis pipeline and later ranking/README regression fixes.
This entry records source history; it does not assert that a package or release was published.
