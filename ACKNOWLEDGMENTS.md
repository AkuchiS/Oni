# Acknowledgments

oni stands on ideas from a number of excellent open projects. It reimplements *techniques*,
not code — which is exactly the discipline oni asks its own users to apply.

- **[Aider](https://github.com/Aider-AI/aider)** (Apache-2.0) — the repo-map idea oni's crown-jewel
  engine is built on: model a codebase as a graph of files linked by symbol references, run PageRank
  to find the most important code, and personalize the ranking toward what you're looking for.
  oni reimplements this in pure stdlib (its own def/ref extraction + power-iteration PageRank).
- **[github-linguist](https://github.com/github-linguist/linguist)** (MIT) — the language-detection
  and vendored/generated-exclusion approach behind `fingerprint`.
- **[repomix](https://github.com/yamadashy/repomix)** (MIT), **[gitingest](https://github.com/cyclotruc/gitingest)** (MIT),
  **[code2prompt](https://github.com/mufeedvh/code2prompt)** (MIT),
  **[files-to-prompt](https://github.com/simonw/files-to-prompt)** (Apache-2.0) — repo-to-context
  packing conventions: summary headers, tree rendering, ignore handling, budget awareness.
- **[CodeBoarding](https://github.com/CodeBoarding/CodeBoarding)**, **pyreverse** (pylint),
  **[madge](https://github.com/pahen/madge)** — architecture-from-source signals (import/call graphs,
  directory-role clustering).
- The **clean-room design** doctrine (Compaq/IBM BIOS lineage) and the copyright principle that
  *ideas and algorithms are not protectable, expression is* — the basis for oni's adoption posture.

If oni helped you learn from a project, learn from it the way oni does: rebuild the idea, credit
the source, and respect its licence.
