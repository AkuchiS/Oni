"""
Stage 6 — adopt: the payoff. Turn the teardown into a clean-room adoption plan.

For each pattern worth having, oni proposes a NATIVE reimplementation (what to build, roughly
how big, why) — never a copy. And it applies the licence gate up front, because how you may
adopt depends entirely on the target's licence:

  · permissive (MIT / Apache / BSD / ISC)  → reuse patterns freely; keep an attribution/NOTICE.
    Apache-2.0 additionally carries a patent grant + NOTICE-file obligation if you vendor.
  · copyleft  (GPL / AGPL / LGPL / MPL)     → CLEAN-ROOM ONLY. Study behaviour, write a spec,
    reimplement from the spec. Do not paste code or mirror file/structure; a close rewrite of
    GPL/AGPL source can itself be a derivative work. AGPL adds a network-use trigger.
  · unknown / none                          → treat as all-rights-reserved: do not adopt code;
    a pattern learned may still be reimplemented, but flag the ambiguity for a human.

The plan is a proposal for a human to act on — oni never copies anything into your tree.
"""
import json

from . import llm

_PERMISSIVE = {"MIT", "Apache-2.0", "BSD-3-Clause", "BSD-2-Clause", "ISC", "Unlicense", "0BSD"}
_COPYLEFT = {"GPL-3.0", "GPL-2.0", "AGPL-3.0", "LGPL-3.0", "LGPL-2.1", "MPL-2.0"}


def posture(license_info):
    """Return {'class','banner','rule'} describing how the target's licence constrains adoption."""
    spdx = (license_info or {}).get("spdx", "NONE")
    if spdx in _PERMISSIVE:
        attr = " Apache-2.0: preserve NOTICE + note the patent grant if you vendor any file." if spdx == "Apache-2.0" else ""
        return {"class": "permissive", "spdx": spdx,
                "banner": "PERMISSIVE (%s) — patterns reusable; keep an attribution note.%s" % (spdx, attr),
                "rule": "Reuse ideas freely. Add %s to your ACKNOWLEDGMENTS. Verbatim vendoring is allowed with attribution." % spdx}
    if spdx in _COPYLEFT:
        net = " AGPL also triggers on NETWORK use — a hosted service counts as distribution." if spdx == "AGPL-3.0" else ""
        return {"class": "copyleft", "spdx": spdx,
                "banner": "⚠ COPYLEFT (%s) — CLEAN-ROOM ONLY. Do not copy code or mirror structure.%s" % (spdx, net),
                "rule": "Study behaviour, write a functional spec, reimplement from the spec. No verbatim code, no structural clone — a close rewrite can be a derivative work."}
    return {"class": "unknown", "spdx": spdx,
            "banner": "⚠ LICENCE %s — treat as all-rights-reserved until a human confirms." % spdx,
            "rule": "Do not vendor code. A pattern may be reimplemented independently, but confirm the licence with a human before adopting anything."}


_SYSTEM = ("You turn a teardown into a clean-room ADOPTION PLAN: which patterns are worth "
           "rebuilding natively, what to build, and how big it is. You NEVER suggest copying "
           "code — only reimplementing ideas. Respect the licence rule you're given.")

_INSTR = """Given the teardown and the licence rule, output STRICT JSON:
{
 "summary": "1-2 sentences: is this worth learning from, and the single biggest idea to steal",
 "adopt": [
   {"pattern": "the idea", "build": "what WE build natively to get it", "effort": "S|M|L", "why": "the payoff"}
 ],
 "skip": ["ideas NOT worth adopting, and why (one phrase each)"]
}
Only propose native reimplementations. Return ONLY the JSON object."""


def plan(fp, teardown, pos, target_context=None):
    """Return the adoption plan dict. Model-assisted with a heuristic fallback."""
    if llm.available():
        brief = json.dumps({
            "what": teardown.get("what"),
            "how_it_works": teardown.get("how_it_works"),
            "patterns": teardown.get("patterns"),
            "strengths": teardown.get("strengths"),
            "weaknesses": teardown.get("weaknesses"),
            "license_rule": pos["rule"],
        }, indent=2)
        ctx = ("\n\nADOPTER CONTEXT (map ideas onto this if relevant): " + target_context) if target_context else ""
        raw = llm.complete(_INSTR + "\n\n=== TEARDOWN ===\n" + brief + ctx, system=_SYSTEM)
        parsed = _parse(raw)
        if parsed:
            return parsed
    return _heuristic(teardown, pos)


def _parse(raw):
    if not raw:
        return None
    try:
        d = json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
        if isinstance(d, dict) and "adopt" in d:
            d["adopt"] = [a for a in (d.get("adopt") or []) if isinstance(a, dict) and a.get("pattern")]
            d["skip"] = [s for s in (d.get("skip") or []) if isinstance(s, str)]
            d.setdefault("summary", "")
            return d
    except (ValueError, TypeError):
        return None
    return None


def _heuristic(teardown, pos):
    adopt = []
    for p in (teardown.get("patterns") or [])[:6]:
        adopt.append({"pattern": p, "build": "reimplement natively — see the crown-jewel excerpts for the mechanism",
                      "effort": "M", "why": "captured from structure; confirm value with a model pass"})
    return {"summary": "Structural adoption plan (no model). %s" % pos["banner"],
            "adopt": adopt, "skip": []}
