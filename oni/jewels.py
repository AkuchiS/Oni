"""
Stage 4 — jewels: turn the ranked symbols into studyable "crown jewels".

Each jewel is the highest-centrality defined symbols plus a short verbatim excerpt (its
signature and the first lines / docstring) so a reader — human or model — can see the actual
mechanism, not just a name. Excerpts are deliberately short: enough to understand intent,
never a wholesale copy of the file (that would defeat the clean-room posture).
"""
from . import util

_EXCERPT_LINES = 14         # signature + a little body — intent, not implementation


def _excerpt(text, line):
    """A short, safe excerpt starting at `line` (1-indexed)."""
    lines = text.splitlines()
    if line <= 0 or line > len(lines):
        return ""
    start = line - 1
    chunk = lines[start:start + _EXCERPT_LINES]
    # trim trailing blank lines
    while chunk and not chunk[-1].strip():
        chunk.pop()
    return "\n".join(chunk)


def select(gmap, n=12):
    """Return the top-n crown jewels with excerpts, de-duplicated by (name, file)."""
    file_text = gmap.get("_file_text", {})
    out, seen = [], set()
    for s in gmap["symbols"]:
        key = (s["name"], s["file"])
        if key in seen:
            continue
        seen.add(key)
        excerpt = _excerpt(file_text.get(s["file"], ""), s["line"])
        out.append({
            "name": s["name"],
            "kind": s["kind"],
            "file": s["file"],
            "line": s["line"],
            "referrers": s["referrers"],
            "score": round(s["score"], 6),
            "excerpt": excerpt,
        })
        if len(out) >= n:
            break
    _qualify(out)
    return out


def _qualify(jewels):
    """Give every jewel a `display` name, qualifying only the ambiguous ones.

    Two different symbols can share a name (roost has `load` in both config.py and health.py).
    Both are legitimate jewels, but rendering each as bare "load" reads as a duplicate/bug —
    "the most-referenced symbols are load, load, registry". Qualify a clashing name with its
    module (config.load / health.load); leave unambiguous names alone so the common case stays clean.
    """
    counts = {}
    for j in jewels:
        counts[j["name"]] = counts.get(j["name"], 0) + 1
    for j in jewels:
        if counts[j["name"]] > 1:
            mod = util.module_of(j["file"])
            j["display"] = "%s.%s" % (mod, j["name"]) if mod else j["name"]
        else:
            j["display"] = j["name"]


def entrypoints(fp, gmap):
    """Best-guess entrypoints: manifest-declared, then convention (main/cli/app/index/server)."""
    found = []
    for m in fp.get("manifests", []):
        for e in m.get("entrypoints", []):
            found.append(e)
        for s in m.get("scripts", []):
            found.append("script:" + s)
    conv = ("main.py", "__main__.py", "cli.py", "app.py", "server.py", "index.js",
            "main.go", "main.rs", "app.js", "index.ts", "manage.py")
    for f in gmap.get("files", []):
        base = f["path"].split("/")[-1].lower()
        if base in conv:
            found.append(f["path"])
    # de-dup, keep order
    out, seen = [], set()
    for f in found:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out[:10]
