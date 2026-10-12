<p align="center"><img src="https://raw.githubusercontent.com/AkuchiS/Oni/main/assets/logo.svg" width="128" alt="Oni source architecture analysis"></p>

# Oni — offline source architecture analysis

Map a repository, find the code it depends on most, and draft an adoption plan.
Oni turns source code into a Markdown report and structured JSON using Python's standard library.
Use it for codebase onboarding, architecture research, and comparing implementation patterns.

[![CI](https://github.com/AkuchiS/Oni/actions/workflows/ci.yml/badge.svg)](https://github.com/AkuchiS/Oni/actions/workflows/ci.yml)
[![MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/AkuchiS/Oni/blob/main/LICENSE)
![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)

[Example report](https://github.com/AkuchiS/Oni/blob/main/docs/examples/tinyrepo.md) · [Agent integration](https://github.com/AkuchiS/Oni/blob/main/docs/agents.md) ·
[Reproducible evaluation](https://github.com/AkuchiS/Oni/blob/main/docs/evaluation.md) · [Changelog](https://github.com/AkuchiS/Oni/blob/main/CHANGELOG.md) · [Contributing](https://github.com/AkuchiS/Oni/blob/main/CONTRIBUTING.md)

## Try it on the bundled example

Requires Python 3.8+. Run these commands from this checkout; no package installation,
model, account, or network is needed for the analysis:

```sh
python3 -m oni ./fixtures/tinyrepo --offline
python3 -m oni ./fixtures/tinyrepo --offline --json
```

The report includes detected languages and licence, an architecture map, central symbols with
file/line references and short source excerpts, and a draft adoption plan.
The bundled example identifies `core/engine.py` among the two highest-ranked source files.

For an installed command, use an isolated environment:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/oni ./fixtures/tinyrepo --offline
```

On Windows, use `.venv\Scripts\python -m pip install .` and `.venv\Scripts\oni`.
On macOS/Linux, `./install.sh` creates a user-owned virtual environment and prints its command path.
Installation may download build tools. The analysis itself has no third-party runtime dependencies.
Do not assume the `oni-re` name is already published on PyPI; this checkout is the supported source.

## Use your own repository

```sh
oni /absolute/path/to/repo --offline --query "authentication"
oni /absolute/path/to/repo --offline --out ./teardowns
oni psf/requests --no-llm --out ./teardowns
```

`--offline` requires a local directory and disables acquisition and model requests.
`--no-llm` explicitly disables the model (also the default): GitHub targets still need the network.
Local analysis does not import or execute the target's code. It skips source symlinks,
common generated/vendor folders and files over 1 MB. It does not implement `.gitignore`
or automatically redact secrets. Use a reviewed source checkout, not a home directory.

## How the map works

1. Detect language, source size, manifests, licence text and repository signals.
2. Build a graph from symbol definitions and identifier references between source files.
3. Rank that graph with PageRank. `--query` biases ranking toward matching concepts.
4. Surface central symbols, entrypoints, source excerpts and an adoption draft.

Python uses `ast`; other supported languages use approximate regex extraction.
Centrality measures dependency patterns, not correctness or business importance. Widely used
helpers can rank highly. Dynamic imports and generated code can be missed. Test presence is
not test coverage, and a heuristic narrative does not prove runtime behaviour.

## Research and clean-room boundaries

Oni can support the research phase of an independent implementation. Reports contain source
excerpts, so reading one does **not** establish clean-room separation. Licence detection is a
heuristic; per-file terms, notices and other obligations still need review. An adoption plan is
a proposal, not legal clearance or an automatically verified specification.

## For agents

Run the CLI with `--offline --json`, or launch the local MCP server with an explicit allowed root:

```sh
oni-mcp --root /absolute/path/to/research-checkouts
```

The MCP tool only reads local source. It provides no shell execution, cloning, model requests
or report-file writes. See [agent configuration and usage](https://github.com/AkuchiS/Oni/blob/main/docs/agents.md).

## Optional model assistance

By default, Oni generates structural heuristics even when model credentials exist.
Use `--llm` (or library `use_llm=True`) to opt into model calls. `--offline` and `--no-llm`
always override that opt-in.
The selected provider receives a brief containing repository metadata, source excerpts, and
any supplied adopter context. Only enable this for material you may send to that provider.
Configure `ONI_ENDPOINT`, `ONI_MODEL`, and, when required, `ONI_API_KEY` in your environment.
An explicit `ONI_ENDPOINT` uses only `ONI_API_KEY`, never a generic OpenAI key. Without an
Oni endpoint/key, the generic pair is `OPENAI_BASE_URL` (or `OPENAI_API_BASE`) and
`OPENAI_API_KEY`; `OPENAI_MODEL` is the model fallback. An Oni key without an Oni endpoint
uses `https://api.openai.com/v1`. `ONI_NO_LLM` disables calls regardless of flags.
Credentials require HTTPS; keyless HTTP is accepted only for loopback hosts. Redirects are not
followed. Loopback requests bypass ambient HTTP proxies. Model responses over 1 MiB or with
an invalid response shape fall back to heuristics. Oni prints the destination hostname to stderr before a model request.

## CLI and library

```text
oni TARGET [--offline | --no-llm | --llm] [--json] [--out DIR]
           [--query TEXT] [--jewels N] [--context TEXT] [--cache-dir DIR]
```

```python
import oni
from oni import report
result = oni.teardown("/absolute/path/to/repo", offline=True, n_jewels=8)
print(report.to_json(result))
```

`--cache-dir` retains each acquisition in a new `oni-*` subdirectory. Existing cached checkouts
are not replaced. Use a dedicated cache and remove old acquisitions when you no longer need them.
Acquisition errors fail the command; unavailable model responses fall back to heuristics.
Reports written with `--out` can overwrite reports for the same target name.

## Oni and REA

[REA](https://github.com/morluto/rea) targets broader agent-assisted reverse engineering,
including binaries, applications and runtime behaviour. Oni focuses on available source:
small installation, offline structural evidence, dependency centrality and adoption research.
Oni does not decompile binaries, inspect running applications or replace REA's tool integrations.
Choose the tool for the evidence you need; no comparative speed or quality claim is established.

## Develop and contribute

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]" build packaging
.venv/bin/python -m pytest -q
.venv/bin/python -m build
```

The CI matrix is configured for Python 3.8–3.14 on Linux, Windows and macOS where available, checks base
wheel dependencies, and installs the built wheel outside the source checkout.
See [CONTRIBUTING.md](https://github.com/AkuchiS/Oni/blob/main/CONTRIBUTING.md), [SECURITY.md](https://github.com/AkuchiS/Oni/blob/main/SECURITY.md), and [release preparation](https://github.com/AkuchiS/Oni/blob/main/docs/releasing.md).

MIT — [licence](https://github.com/AkuchiS/Oni/blob/main/LICENSE). Ranking inspiration and attribution: [ACKNOWLEDGMENTS.md](https://github.com/AkuchiS/Oni/blob/main/ACKNOWLEDGMENTS.md).
