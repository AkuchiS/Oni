"""
Stage 5 — teardown: the narrative. What is this, how does it actually work, what's clever,
where is it weak.

With a model configured, oni feeds it a compact, structured brief (fingerprint + architecture
skeleton + crown-jewel excerpts) and asks for a disciplined teardown. With no model, it emits a
solid heuristic teardown built purely from the structural signals — never a dead end.
"""
import json

from . import llm

_SYSTEM = (
    "You are a senior reverse engineer producing a precise technical teardown of a codebase for a "
    "team that will REIMPLEMENT the good ideas natively (clean-room), never copy the code. Be "
    "concrete and specific to THIS code — name real modules and symbols. No filler, no marketing."
)

_INSTR = """Produce a teardown as STRICT JSON with these keys:
{
 "what": "1-2 sentences: what this project is and the problem it solves",
 "how_it_works": "3-6 sentences on the actual mechanism / control flow, referencing the real modules and crown-jewel symbols",
 "patterns": ["the notable, reusable design patterns / algorithms / techniques — each a short concrete phrase"],
 "strengths": ["what it genuinely does well"],
 "weaknesses": ["real limitations, risks, or smells"]
}
Return ONLY the JSON object."""


def _brief(fp, gmap, jewels, ep):
    lines = []
    lines.append("PROJECT: %s" % (fp.get("readme") or "(no README blurb)"))
    lines.append("PRIMARY LANGUAGE: %s" % fp.get("primary_language"))
    langs = ", ".join("%s(%d loc)" % (k, v["loc"]) for k, v in list(fp["languages"].items())[:6])
    lines.append("LANGUAGES: %s" % langs)
    lic = fp["license"]
    lines.append("LICENSE: %s (copyleft=%s)" % (lic["spdx"], lic["copyleft"]))
    deps = sorted({d for m in fp["manifests"] for d in m.get("deps", [])})
    if deps:
        lines.append("KEY DEPENDENCIES: %s" % ", ".join(deps[:20]))
    if ep:
        lines.append("ENTRYPOINTS: %s" % ", ".join(ep))
    lines.append("\nARCHITECTURE (top dirs by centrality):")
    for c in gmap["clusters"][:8]:
        lines.append("  - %s/ : %d files" % (c["dir"], c["files"]))
    lines.append("\nCROWN-JEWEL SYMBOLS (highest centrality — what the codebase depends on most):")
    for j in jewels:
        lines.append("  # %s  (%s %s:%d, %d referrers)" % (j["name"], j["kind"], j["file"], j["line"], j["referrers"]))
        if j["excerpt"]:
            lines.append("    " + j["excerpt"].replace("\n", "\n    ")[:600])
    return "\n".join(lines)


def analyze(fp, gmap, jewels, ep):
    """Return the teardown dict. Uses the model if available; else a heuristic build."""
    brief = _brief(fp, gmap, jewels, ep)
    if llm.available():
        raw = llm.complete(_INSTR + "\n\n=== CODEBASE BRIEF ===\n" + brief, system=_SYSTEM)
        parsed = _parse_json(raw)
        if parsed:
            parsed["_model"] = llm.model()
            return parsed
    return _heuristic(fp, gmap, jewels, ep)


def _parse_json(raw):
    if not raw:
        return None
    try:
        s = raw[raw.index("{"): raw.rindex("}") + 1]
        d = json.loads(s)
        if isinstance(d, dict) and "what" in d:
            for k in ("patterns", "strengths", "weaknesses"):
                if isinstance(d.get(k), str):
                    d[k] = [d[k]]
                d[k] = [x for x in (d.get(k) or []) if isinstance(x, str)]
            return d
    except (ValueError, TypeError):
        return None
    return None


def _heuristic(fp, gmap, jewels, ep):
    """A useful teardown with no model: read the structure and say what it implies."""
    prim = fp.get("primary_language") or "code"
    what = fp.get("readme") or ("A %s project (%d files, %s LOC)." % (
        prim, fp["total_files"], fp["total_loc"]))
    top_dirs = ", ".join("%s/" % c["dir"] for c in gmap["clusters"][:4] if c["dir"] != "(root)")
    jn = ", ".join(j.get("display") or j["name"] for j in jewels[:6])
    how = ("Written primarily in %s. The centre of gravity is %s; the most-referenced symbols are "
           "%s — the code the rest of it leans on." % (prim, top_dirs or "the root package", jn or "(none found)"))
    patterns = []
    sig = fp["signals"]
    if sig["tests"]:
        patterns.append("has a test suite (behaviour is specified — good for clean-room extraction)")
    if sig["ci"]:
        patterns.append("CI pipeline present")
    if sig["docker"]:
        patterns.append("containerised (Docker) deployment")
    deps = sorted({d for m in fp["manifests"] for d in m.get("deps", [])})
    if deps:
        patterns.append("leans on: " + ", ".join(deps[:8]))
    if not patterns:
        patterns = ["structural analysis only — configure a model (ONI_MODEL) for a deeper read"]
    strengths, weaknesses = [], []
    if sig["tests"]:
        strengths.append("test coverage exists")
    if sig["docs"]:
        strengths.append("documented")
    if not sig["tests"]:
        weaknesses.append("no obvious tests — behaviour must be inferred from source")
    if fp["license"]["spdx"] in ("NONE", "UNKNOWN"):
        weaknesses.append("licence unclear — adoption posture cannot be auto-determined")
    return {"what": what, "how_it_works": how, "patterns": patterns,
            "strengths": strengths or ["(configure a model for a qualitative read)"],
            "weaknesses": weaknesses or ["(configure a model for a qualitative read)"],
            "_model": None}
