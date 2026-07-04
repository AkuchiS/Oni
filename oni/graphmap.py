"""
Stage 3 — graphmap: build a symbol graph and rank importance by centrality.

This is oni's crown-jewel engine, a stdlib reimplementation of Aider's repo-map idea:

  · nodes are FILES.
  · every identifier a file REFERENCES that is DEFINED in another file adds a directed edge
    referencer → definer, weighted by how many times it's referenced (up-weighted for
    "interesting" identifiers — snake_case / CamelCase, not language noise).
  · PageRank over that graph (power iteration, damping 0.85) → file importance. A `query`
    biases the teleport (personalization) vector so "point at authentication" surfaces the
    auth machinery, not just the globally-central files.
  · each file's rank is then spread across its outbound edges, crediting the DEFINED symbols
    it leans on → a rank *per symbol*. Sort those and you have the crown jewels.

Definitions come from Python's `ast` (accurate) and regex heuristics for other languages.
References are just the identifier tokens in a file intersected with the global definition set —
cheap, language-agnostic, and good enough for centrality.
"""
import ast
import re
from collections import defaultdict, Counter

from . import util

_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

# per-language definition patterns (name is always group 1). Python is handled by ast.
_DEF_PATTERNS = {
    "JavaScript": [r"\bfunction\s+([A-Za-z_]\w*)", r"\bclass\s+([A-Za-z_]\w*)",
                   r"\b(?:const|let|var)\s+([A-Za-z_]\w*)\s*=\s*(?:async\s*)?(?:function|\([^)]*\)\s*=>)",
                   r"\bexport\s+(?:default\s+)?(?:async\s+)?function\s+([A-Za-z_]\w*)"],
    "Go": [r"\bfunc\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)", r"\btype\s+([A-Za-z_]\w*)\s+(?:struct|interface)"],
    "Rust": [r"\bfn\s+([A-Za-z_]\w*)", r"\bstruct\s+([A-Za-z_]\w*)", r"\btrait\s+([A-Za-z_]\w*)",
             r"\benum\s+([A-Za-z_]\w*)", r"\bmacro_rules!\s+([A-Za-z_]\w*)"],
    "Ruby": [r"\bdef\s+([A-Za-z_]\w*)", r"\bclass\s+([A-Za-z_]\w*)", r"\bmodule\s+([A-Za-z_]\w*)"],
    "Java": [r"\b(?:class|interface|enum)\s+([A-Za-z_]\w*)",
             r"\b(?:public|private|protected|static|\s)+[\w<>\[\]]+\s+([A-Za-z_]\w*)\s*\("],
    "PHP": [r"\bfunction\s+([A-Za-z_]\w*)", r"\bclass\s+([A-Za-z_]\w*)", r"\btrait\s+([A-Za-z_]\w*)"],
    "C#": [r"\b(?:class|interface|struct|enum)\s+([A-Za-z_]\w*)"],
    "C++": [r"\b(?:class|struct)\s+([A-Za-z_]\w*)", r"\b[\w:<>\*&]+\s+([A-Za-z_]\w*)\s*\([^;]*\)\s*\{"],
    "C": [r"\b[\w\*]+\s+([A-Za-z_]\w*)\s*\([^;]*\)\s*\{", r"\bstruct\s+([A-Za-z_]\w*)"],
}
_DEF_PATTERNS["TypeScript"] = _DEF_PATTERNS["JavaScript"] + [r"\b(?:interface|type|enum)\s+([A-Za-z_]\w*)"]
_DEF_PATTERNS["Kotlin"] = [r"\bfun\s+([A-Za-z_]\w*)", r"\b(?:class|object|interface)\s+([A-Za-z_]\w*)"]
_DEF_PATTERNS["Objective-C"] = _DEF_PATTERNS["C"]
_DEF_PATTERNS["C++"] += _DEF_PATTERNS["C"]

# identifiers that carry no design signal — never treat as a symbol edge
_NOISE = {
    "self", "this", "cls", "super", "true", "false", "null", "none", "nil", "void", "var",
    "let", "const", "func", "def", "class", "return", "if", "else", "for", "while", "import",
    "from", "as", "in", "is", "and", "or", "not", "new", "try", "catch", "except", "with",
    "int", "str", "string", "bool", "float", "list", "dict", "map", "set", "len", "print",
    "type", "object", "value", "key", "name", "data", "result", "error", "err", "ok", "get",
    "set", "add", "run", "main", "init", "test", "args", "kwargs", "params", "options", "opts",
}


def _py_defs(text):
    """(name -> (lineno, kind)) via ast; falls back to regex on syntax error."""
    defs = {}
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return _regex_defs(text, _DEF_PATTERNS.get("Python", []))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defs.setdefault(node.name, (node.lineno, "function"))
        elif isinstance(node, ast.ClassDef):
            defs[node.name] = (node.lineno, "class")
    return defs


def _regex_defs(text, patterns):
    defs = {}
    for pat in patterns:
        for m in re.finditer(pat, text):
            name = m.group(1)
            if name and name not in defs:
                line = text.count("\n", 0, m.start()) + 1
                kind = "class" if "class" in m.group(0).lower() or "struct" in m.group(0).lower() else "function"
                defs[name] = (line, kind)
    return defs


def _defs_for(lang, text):
    if lang == "Python":
        return _py_defs(text)
    pats = _DEF_PATTERNS.get(lang)
    return _regex_defs(text, pats) if pats else {}


def _interesting(ident):
    """Aider's up-weight: multi-word identifiers (snake/Camel) carry more design signal."""
    if len(ident) <= 2 or ident.lower() in _NOISE:
        return 0.0
    has_camel = bool(re.search(r"[a-z][A-Z]", ident))
    has_snake = "_" in ident.strip("_")
    return 1.5 if (has_camel or has_snake) else 1.0


def build(fp, query=None, max_files=4000):
    """Build the graph from a fingerprint dict. Returns a map dict with ranked files & symbols."""
    root = fp["root"]
    files = []          # rel paths (code files only)
    file_defs = {}      # rel -> {name: (lineno, kind)}
    file_text = {}      # rel -> source (kept for excerpts; capped)
    file_lang = {}
    def_index = defaultdict(set)   # symbol -> set(rel files that define it)

    for ap, rel in util.walk_source(root):
        lang = util.lang_of(rel)
        if lang not in util.CODE_LANGS:
            continue
        if len(files) >= max_files:
            break
        text = util.read_text(ap)
        defs = _defs_for(lang, text)
        if not defs:
            continue
        files.append(rel)
        file_defs[rel] = defs
        file_lang[rel] = lang
        file_text[rel] = text
        for name in defs:
            def_index[name].add(rel)

    # --- edges: referencer -> definer, weighted ---
    out_edges = defaultdict(lambda: defaultdict(float))       # src -> {dst: weight}
    ident_edges = defaultdict(lambda: defaultdict(float))     # (src) -> {(symbol,dst): weight}
    for rel in files:
        idents = Counter(_IDENT.findall(file_text[rel]))
        own = file_defs[rel]
        for ident, cnt in idents.items():
            definers = def_index.get(ident)
            if not definers:
                continue
            w = _interesting(ident) * cnt
            if w <= 0:
                continue
            for dst in definers:
                if dst == rel:
                    continue                       # ignore self-references
                out_edges[rel][dst] += w
                ident_edges[rel][(ident, dst)] += w

    ranks = _pagerank(files, out_edges, _personalize(files, file_defs, query))

    # --- spread file rank across outbound edges → per-symbol rank ---
    sym_rank = defaultdict(float)                  # (symbol, dst) -> score
    for src in files:
        r = ranks.get(src, 0.0)
        tot = sum(ident_edges[src].values()) or 1.0
        for (sym, dst), w in ident_edges[src].items():
            sym_rank[(sym, dst)] += r * (w / tot)

    symbols = []
    for (sym, dst), score in sym_rank.items():
        lineno, kind = file_defs[dst].get(sym, (0, "symbol"))
        refs = sum(1 for s in files if (sym, dst) in ident_edges[s])
        symbols.append({"name": sym, "file": dst, "line": lineno, "kind": kind,
                        "score": score, "referrers": refs})
    symbols.sort(key=lambda s: -s["score"])

    ranked_files = sorted(files, key=lambda f: -ranks.get(f, 0.0))
    return {
        "files": [{"path": f, "lang": file_lang[f], "rank": ranks.get(f, 0.0),
                   "defs": len(file_defs[f])} for f in ranked_files],
        "symbols": symbols,
        "clusters": _clusters(ranked_files, ranks),
        "_file_text": file_text,       # kept in-memory for the jewels stage; not serialised
        "_file_defs": file_defs,
    }


def _personalize(files, file_defs, query):
    """Teleport bias toward files whose path or defined symbols match the query tokens."""
    if not query:
        return None
    qtokens = {t.lower() for t in _IDENT.findall(query) if len(t) > 2}
    if not qtokens:
        return None
    p = {}
    for rel in files:
        score = sum(1 for t in qtokens if t in rel.lower())
        score += sum(1 for name in file_defs[rel] for t in qtokens if t in name.lower())
        if score:
            p[rel] = float(score)
    return p or None


def _pagerank(nodes, out_edges, personalization, damping=0.85, iters=60, tol=1e-7):
    n = len(nodes)
    if n == 0:
        return {}
    if personalization:
        tot = sum(personalization.values()) or 1.0
        pvec = {k: personalization.get(k, 0.0) / tot for k in nodes}
    else:
        pvec = {k: 1.0 / n for k in nodes}
    outsum = {k: sum(out_edges[k].values()) for k in nodes}
    dangling = [k for k in nodes if outsum[k] <= 0]
    rank = {k: 1.0 / n for k in nodes}
    for _ in range(iters):
        dmass = damping * sum(rank[k] for k in dangling)
        new = {k: (1.0 - damping) * pvec[k] + dmass * pvec[k] for k in nodes}
        for src in nodes:
            s = outsum[src]
            if s <= 0:
                continue
            base = damping * rank[src] / s
            for dst, w in out_edges[src].items():
                new[dst] += base * w
        delta = sum(abs(new[k] - rank[k]) for k in nodes)
        rank = new
        if delta < tol:
            break
    return rank


def _clusters(ranked_files, ranks):
    """Group files by top-level directory and score each cluster — the architecture skeleton."""
    agg = defaultdict(lambda: {"files": 0, "rank": 0.0})
    for f in ranked_files:
        top = f.split("/")[0] if "/" in f else "(root)"
        agg[top]["files"] += 1
        agg[top]["rank"] += ranks.get(f, 0.0)
    out = [{"dir": k, "files": v["files"], "rank": v["rank"]} for k, v in agg.items()]
    out.sort(key=lambda c: -c["rank"])
    return out
