"""
oni — a source-level reverse-engineering engine.

Point it at one repo (a GitHub `owner/repo`, a URL, or a local path) and it tears the
codebase down into the things worth knowing: what it is, how it's built, WHICH code the rest
of it depends on (the crown jewels), how it hangs together, and — the payoff — an
*adoption plan* that tells you which patterns to reimplement natively and how the target's
licence constrains that.

Design goals (in priority order):
  1. Stdlib-only. No third-party runtime deps. Runs on a laptop, offline, keyless.
  2. Structural analysis without a model; optional model failures fall back to heuristics.
     Acquisition failures are reported.
  3. Evidence before adoption. Reports contain source excerpts and heuristic licence signals.
     They help research; they do not establish clean-room separation or permission to reuse.

The pipeline is seven small, independently-testable stages:
    acquire → fingerprint → graphmap → jewels → teardown → adopt → report
"""

__version__ = "0.2.0rc1"

from .pipeline import teardown  # noqa: E402  (public one-call entrypoint)

__all__ = ["teardown", "__version__"]
