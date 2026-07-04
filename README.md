<h1 align="center">oni 👹</h1>

<p align="center"><b>A clean-room, source-level reverse-engineering engine.</b><br>
Point it at one repo. It tears the codebase down to the things worth knowing —<br>
what it is, how it works, <i>which</i> files are the crown jewels, and a plan for<br>
rebuilding the good ideas natively without copying a line.</p>

<p align="center">
<code>pure stdlib</code> · <code>zero deps</code> · <code>offline & keyless</code> · <code>LLM optional</code>
</p>

---

## Why

Every team ends up reverse-engineering other people's code — to learn a pattern, to size up a
rival, to decide *is there anything here worth having?* Done by hand it's a slow crawl: clone,
grep, guess which files matter, read the wrong ones first, and eventually reconstruct the shape.

**oni turns that crawl into one command.** It finds the important code for you (centrality, not
guesswork), explains the mechanism, and — the part most tools skip — tells you how the target's
**licence** governs what you're allowed to do with what you just learned.

```bash
oni Aider-AI/aider
oni ./path/to/local/repo --query "how does the planner work"
oni https://github.com/psf/requests --no-llm --out ./teardowns
```

## What you get

A `TEARDOWN.md` (and matching `teardown.json`) with:

| Section | What it tells you |
|---|---|
| **Adoption posture** | The licence, and *exactly* how you may reuse this — shown first, on purpose. |
| **Snapshot** | Languages, size, licence, and signals (tests / CI / Docker / docs). |
| **What it is / How it works** | A tight, specific narrative — real modules and symbols, no filler. |
| **Architecture** | Top-level areas ranked by centrality + the detected entrypoints. |
| **Crown jewels** | The highest-centrality symbols, each with a short verbatim excerpt. Study these first. |
| **Patterns · Strengths · Weaknesses** | The reusable ideas, what it does well, where it's weak. |
| **Adoption plan** | Per pattern: *what to build natively*, effort (S/M/L), and why — a clean-room spec, never a copy. |

## The crown-jewel engine

Finding "the important files" is the hard part, and oni does it the way
[Aider](https://github.com/Aider-AI/aider) does — reimplemented in pure stdlib:

1. **Model the repo as a graph.** Nodes are files. For every identifier a file *references* that's
   *defined* in another file, add an edge (referencer → definer), weighted by reference count and
   up-weighted for meaningful `snake_case` / `CamelCase` names.
2. **Run PageRank** over that graph (power iteration, damping 0.85). Files that define
   widely-used symbols float to the top. A `--query` biases the teleport vector so *"point at
   authentication"* surfaces the auth machinery, not just the globally-central files.
3. **Spread each file's rank across its symbols** → a ranking *per symbol*. Those are your crown
   jewels: the code the rest of the codebase leans on.

No embeddings, no external service, no index server — just `ast`, regex, and ~30 lines of PageRank.

## Clean-room by design

oni exists to help you **learn from** code, not launder it. So it never copies a target into your
tree, keeps excerpts short (intent, not implementation), and leads every report with the licence:

- **Permissive** (MIT / Apache / BSD / ISC) → reuse patterns freely; keep an attribution note.
- **Copyleft** (GPL / AGPL / LGPL / MPL) → **clean-room only**: study behaviour, write a spec,
  reimplement from the spec. AGPL is flagged as network-triggering. A close rewrite of copyleft
  source can itself be a derivative work — oni says so, loudly.
- **Unknown / none** → treated as all-rights-reserved until a human confirms.

The adoption plan only ever proposes *native reimplementations*.

## Install

```bash
./install.sh                 # pipx / pip --user / zero-install shim, in that order
# or
pip install -e .             # then `oni` is on your PATH
# or just
python3 -m oni <target>      # no install at all
```

Requires Python 3.8+. Nothing else.

## Using a model (optional)

Every stage has a heuristic fallback, so oni is fully useful with **no model at all**. Give it one
and the narrative + adoption plan get sharper. Configuration is by environment — it drops onto any
OpenAI-compatible endpoint (OpenAI, OpenRouter, Ollama, vLLM, LM Studio, …):

```bash
export ONI_API_KEY=sk-...            # omit for a local/Ollama endpoint
export ONI_MODEL=gpt-4o-mini         # or any model your endpoint serves
export ONI_ENDPOINT=https://api.openai.com/v1   # or http://localhost:11434/v1, etc.
oni some/repo
```

Force the offline path any time with `--no-llm`.

## As a library

```python
import oni

result = oni.teardown("Aider-AI/aider", query="repo map", n_jewels=15)
print(result["jewels"][0]["name"])           # highest-centrality symbol
print(result["posture"]["banner"])           # how you may adopt it
for a in result["adoption"]["adopt"]:
    print(a["pattern"], "→", a["build"], f"({a['effort']})")
```

## CLI reference

```
oni <target> [options]

  <target>            local path | GitHub URL | owner/repo[@ref]
  -o, --out DIR       write TEARDOWN.md + teardown.json to DIR
  -q, --query TEXT    bias the crown-jewel ranking toward a concept
  -n, --jewels N      how many crown jewels to surface (default 12)
  -c, --context TEXT  your own context, so the adoption plan maps ideas onto it
  --no-llm            skip the model; structural teardown only
  --json              print JSON instead of Markdown
  --cache-dir DIR     clone remotes here (kept) instead of a tempdir
```

## How it stays honest

- **Fail-soft everywhere.** No git → downloads the tarball. No model → heuristic teardown. No
  network → works on a local checkout. A dead stage degrades; it doesn't abort the run.
- **Deterministic.** Same repo in, same ranking out — sorted walks, no randomness.
- **Read-only.** oni never modifies the target, and never writes into your project unless you pass `--out`.

## Tests

```bash
pip install pytest && pytest -q      # runs fully offline against a bundled fixture repo
```

## Credits

See [ACKNOWLEDGMENTS.md](ACKNOWLEDGMENTS.md). The crown-jewel ranking is Aider's repo-map idea;
language detection follows github-linguist; the clean-room posture follows established
reverse-engineering doctrine.

## Licence

MIT — see [LICENSE](LICENSE). Use oni to learn from code responsibly.
