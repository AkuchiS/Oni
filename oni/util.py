"""
Shared helpers: filesystem walking, ignore handling, language detection, and cheap LOC.

Everything here is stdlib and deterministic. The language map is a pragmatic subset of
github-linguist's extension table — enough to fingerprint the vast majority of repos without
shipping linguist's full YAML.
"""
import os
import re

# --- extension → language (linguist-lite) --------------------------------------------------
LANGS = {
    ".py": "Python", ".pyi": "Python",
    ".js": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript", ".jsx": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript",
    ".go": "Go", ".rs": "Rust", ".rb": "Ruby", ".php": "PHP",
    ".java": "Java", ".kt": "Kotlin", ".kts": "Kotlin", ".scala": "Scala",
    ".c": "C", ".h": "C", ".cc": "C++", ".cpp": "C++", ".cxx": "C++", ".hpp": "C++",
    ".cs": "C#", ".swift": "Swift", ".m": "Objective-C", ".mm": "Objective-C++",
    ".sh": "Shell", ".bash": "Shell", ".zsh": "Shell",
    ".sql": "SQL", ".lua": "Lua", ".dart": "Dart", ".ex": "Elixir", ".exs": "Elixir",
    ".clj": "Clojure", ".hs": "Haskell", ".ml": "OCaml", ".r": "R", ".jl": "Julia",
    ".vue": "Vue", ".svelte": "Svelte",
    ".html": "HTML", ".css": "CSS", ".scss": "SCSS", ".less": "Less",
    ".json": "JSON", ".yaml": "YAML", ".yml": "YAML", ".toml": "TOML",
    ".md": "Markdown", ".rst": "reStructuredText",
    ".proto": "Protobuf", ".graphql": "GraphQL", ".tf": "Terraform",
}
# languages that carry real logic (used to decide the "primary" language and where to look for jewels)
CODE_LANGS = {
    "Python", "JavaScript", "TypeScript", "Go", "Rust", "Ruby", "PHP", "Java", "Kotlin",
    "Scala", "C", "C++", "C#", "Swift", "Objective-C", "Objective-C++", "Shell", "Lua",
    "Dart", "Elixir", "Clojure", "Haskell", "OCaml", "R", "Julia", "Vue", "Svelte",
}

# directories that are never the target's own source — skip wholesale
SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "vendor", "venv", ".venv", "env",
    "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".tox",
    "dist", "build", "target", "out", ".next", ".nuxt", ".svelte-kit",
    "site-packages", ".idea", ".vscode", ".gradle", ".terraform", "bower_components",
    "coverage", ".cache", "Pods", "DerivedData", ".dart_tool",
}
# individual files that are noise for RE purposes
SKIP_FILE_SUFFIX = (
    ".min.js", ".min.css", ".map", ".lock", ".log", ".png", ".jpg", ".jpeg", ".gif",
    ".svg", ".ico", ".pdf", ".zip", ".gz", ".tar", ".whl", ".so", ".dylib", ".dll",
    ".woff", ".woff2", ".ttf", ".eot", ".mp4", ".mp3", ".wav", ".bin", ".pyc",
)
MAX_FILE_BYTES = 1_000_000   # skip individual files larger than 1 MB (generated/data blobs)


def lang_of(path):
    """Language name for a path, or None if unknown/uninteresting."""
    _, ext = os.path.splitext(path)
    return LANGS.get(ext.lower())


def is_skippable(name):
    n = name.lower()
    return n.endswith(SKIP_FILE_SUFFIX)


def module_of(rel_path):
    """The module name for a source path — 'roost/config.py' -> 'config'.

    Used to tell same-named symbols apart (config.load vs health.load). For a package
    __init__, the package name is the useful label, not '__init__'.
    """
    base = os.path.basename(rel_path or "")
    stem = os.path.splitext(base)[0]
    if stem == "__init__":
        parent = os.path.basename(os.path.dirname(rel_path or ""))
        return parent or stem
    return stem


_TEST_PATH = re.compile(
    r"(^|/)(tests?|testing|spec|specs|__tests__|e2e|fixtures?)(/|$)"      # a test/fixture directory
    r"|(^|/)(test_[^/]+|[^/]+_test|[^/]+\.test|[^/]+\.spec)\.[A-Za-z0-9]+$"  # test_x.py / x_test.go / x.test.js
    r"|(^|/)conftest\.py$",
    re.I)


def is_test_path(rel_path):
    """Is this a test/fixture file rather than the codebase's own source?

    Crown jewels are meant to be the code the project leans on; a helper defined inside its
    test suite is not that (oni ranked `failing` from tests/test_roost.py as the #4 jewel of
    roost). Tests are excluded from the graph entirely: their symbols aren't jewels, and their
    call patterns shouldn't drive what counts as important in the source either.
    """
    return bool(_TEST_PATH.search((rel_path or "").replace(os.sep, "/")))


def walk_source(root):
    """Yield (abs_path, rel_path) for every non-skipped file under root.

    Prunes SKIP_DIRS in-place so we never descend into vendored trees. Order is stable
    (sorted) so runs are reproducible.
    """
    root = os.path.abspath(root)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".git"))
        for fn in sorted(filenames):
            if is_skippable(fn):
                continue
            ap = os.path.join(dirpath, fn)
            try:
                if os.path.getsize(ap) > MAX_FILE_BYTES:
                    continue
            except OSError:
                continue
            yield ap, os.path.relpath(ap, root)


def read_text(path, limit=MAX_FILE_BYTES):
    """Read a file as text, tolerant of encoding. Returns '' on any failure."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read(limit)
    except (OSError, ValueError):
        return ""


def count_loc(text):
    """Non-blank lines. Cheap and good enough for a size signal."""
    return sum(1 for ln in text.splitlines() if ln.strip())


def human_bytes(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return "%.0f%s" % (n, unit) if unit == "B" else "%.1f%s" % (n, unit)
        n /= 1024.0
