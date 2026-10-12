"""Stage 6: draft an adoption proposal from structural evidence.

Licence classification is a heuristic review signal, not permission to reuse.
Source-reading reports do not establish clean-room separation.
"""
import json

from . import llm

_PERMISSIVE = {"MIT", "Apache-2.0", "BSD-3-Clause", "BSD-2-Clause", "ISC", "Unlicense", "0BSD"}
_COPYLEFT = {"GPL-3.0", "GPL-2.0", "AGPL-3.0", "LGPL-3.0", "LGPL-2.1", "MPL-2.0"}


def posture(license_info):
    """Return {'class','banner','rule'} describing how the target's licence constrains adoption."""
    spdx = (license_info or {}).get("spdx", "NONE")
    if spdx in _PERMISSIVE:
        return {"class": "permissive", "spdx": spdx,
                "banner": "PERMISSIVE signal (%s) — review the original terms, notices and file-level exceptions." % spdx,
                "rule": "Draft an independent implementation plan. Before any reuse, verify applicable licence conditions and required notices; this detection is a heuristic, not permission."}
    if spdx in _COPYLEFT:
        net = " Review AGPL network-service obligations where applicable." if spdx == "AGPL-3.0" else ""
        return {"class": "copyleft", "spdx": spdx,
                "banner": "COPYLEFT signal (%s) — licence-specific review required.%s" % (spdx, net),
                "rule": "Do not treat this report or a rewrite as automatic clearance. Review the applicable obligations before reusing source or distributing derived work. A source-reading report cannot establish clean-room separation."}
    return {"class": "unknown", "spdx": spdx,
            "banner": "LICENCE %s — permission to reuse has not been established." % spdx,
            "rule": "Confirm the actual terms with the rights holder or appropriate reviewer before adopting code."}



_SYSTEM = ("You turn a teardown into a draft ADOPTION PLAN: which patterns are worth "
           "rebuilding natively, what to build, and how big it is. You NEVER suggest copying "
           "code — only reimplementing ideas. Respect the licence review signal. Do not claim legal clearance or clean-room separation.")

_INSTR = """Given the teardown and the licence rule, output STRICT JSON:
{
 "summary": "1-2 sentences: is this worth learning from, and the single biggest idea to steal",
 "adopt": [
   {"pattern": "the idea", "build": "what WE build natively to get it", "effort": "S|M|L", "why": "the payoff"}
 ],
 "skip": ["ideas NOT worth adopting, and why (one phrase each)"]
}
Only propose native reimplementations. Return ONLY the JSON object."""


def plan(fp, teardown, pos, target_context=None, use_llm=True):
    """Return the adoption plan dict. Model-assisted with a heuristic fallback."""
    if use_llm and llm.available():
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
        adopt.append({"pattern": p, "build": "draft an independent implementation specification; validate behaviour and licence requirements",
                      "effort": "M", "why": "captured from structure; confirm value with a model pass"})
    return {"summary": "Structural adoption plan (no model). %s" % pos["banner"],
            "adopt": adopt, "skip": []}
