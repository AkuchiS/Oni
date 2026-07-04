"""
oni — a source-level reverse-engineering engine.

Point it at one repo (a GitHub `owner/repo`, a URL, or a local path) and it tears the
codebase down into the things worth knowing: what it is, how it's built, WHICH files are
the crown jewels, how the important mechanism actually works, and — the payoff — an
*adoption plan* that tells you which patterns to reimplement natively and how the target's
licence constrains that.

Design goals (in priority order):
  1. Stdlib-only. No third-party runtime deps. Runs on a laptop, offline, keyless.
  2. Fail-soft. Every stage degrades gracefully; no model, no git, no network → still useful.
  3. Clean-room by construction. oni extracts ARCHITECTURE and IDEAS, never copies code into
     your tree. Its output is a native-reimplementation spec, and it flags copyleft targets
     loudly so you study behaviour and rebuild — you don't paste.

The pipeline is seven small, independently-testable stages:
    acquire → fingerprint → graphmap → jewels → teardown → adopt → report
"""

__version__ = "0.1.0"

from .pipeline import teardown  # noqa: E402  (public one-call entrypoint)

__all__ = ["teardown", "__version__"]
