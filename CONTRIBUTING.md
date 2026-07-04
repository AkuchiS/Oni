# Contributing to oni

Thanks for wanting to help. oni is small on purpose — a focused, dependency-free tool — so a few
principles keep it that way.

## The rules that matter

1. **Standard library only.** No runtime dependencies, ever. If a feature seems to need a package, it
   almost certainly doesn't — `ast`, `re`, `urllib`, `json`, `xml`, and `subprocess` go a long way.
   (`pytest` is fine as a *dev*-only extra.)
2. **Deterministic.** Same repo in → same teardown out. No randomness in ranking or output ordering;
   sort your walks.
3. **Fail-soft.** A missing tool, model, or network should *degrade* a run, never abort it. Every stage
   has a heuristic fallback — keep it that way.
4. **Read-only, clean-room.** oni never modifies a target and never encourages copying source. Keep
   excerpts short (intent, not implementation), and keep the licence-posture logic honest.

## Getting set up

```bash
git clone https://github.com/AkuchiS/oni && cd oni
pip install -e ".[dev]"
pytest -q            # fully offline, against the bundled fixture repo
```

## Sending a change

- Open an issue first for anything larger than a bug fix, so we can agree on the shape.
- Keep PRs focused; add or update a test in `tests/` for behaviour changes.
- Match the surrounding style. No new dependencies (see rule 1).

By contributing you agree your work is released under the project's [MIT licence](LICENSE).
