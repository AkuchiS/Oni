# Release preparation

`0.2.0rc1` is a candidate, not a claim of a published GitHub/PyPI release.

1. Run `python -m pytest -q`, `python -m build` and the offline evaluation.
2. Install the wheel in a new virtual environment with `pip install --no-deps <wheel>`.
   Run `oni --version`, the bundled fixture with `--offline --json`, and `python scripts/smoke_mcp.py <installed-oni-mcp> fixtures/tinyrepo` from the source checkout.
   This smoke script uses only the standard library; pytest is not needed in the wheel environment.
3. Check wheel metadata: no dependency may apply when the selected extra is empty.
   Optional development requirements are allowed. CI evaluates platform/Python markers.
4. Confirm CI passed on the exact commit across the matrix. A local pass does not turn the
   public GitHub badge green. Review the diff, release notes, distributions and licences.
5. Obtain maintainer approval for the exact commit, version, GitHub destination and artifacts.
   Confirm ownership of the `oni-re` PyPI project before any registry publication.
6. Tag and publish only the reviewed revision, then verify download/install from the public
   destination. Do not upload private analysis outputs or private operational notes.

No publication workflow or registry credentials are included. CI retains candidate distributions
as artifacts. Stable version selection follows review; do not publish an RC as an implicit stable release.

## Discoverability package

Suggested GitHub About text: **Offline source architecture analysis for developers and agents:
rank central code, inspect dependencies, and draft adoption plans. Zero runtime dependencies.**

Suggested topics: `static-analysis`, `code-analysis`, `reverse-engineering`, `developer-tools`,
`python`, `codebase-understanding`, `mcp`, `ai-agents`.

Use the README and its concrete example as the first landing page. Add a separate website only
when there is maintained content beyond that page. Validate each topic and claim against the
release. Do not use an unverified MCP registry listing or PyPI badge.

Measure successful installs, completed example runs, useful issues and external contributions.
Stars/forks are secondary interest signals; do not create artificial activity or noisy commits.
Publish demonstrations only with source permission, pinned revisions and reproducible commands.

The legacy licence metadata table is retained for Python 3.8 build compatibility. Current
setuptools emits a deprecation warning (deadline 2027-02-18); resolve the Python-version/build
backend policy before that date. An SPDX-string migration requires a newer backend that drops
Python 3.8 build support. This does not block the currently tested candidate build.
