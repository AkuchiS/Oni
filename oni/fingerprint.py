"""
Stage 2 — fingerprint: cheap, structural facts about the repo.

Languages + LOC (linguist-lite cascade), the build/package manifests and what they declare
(name, description, deps, entrypoints, scripts), the LICENCE (+ SPDX guess and copyleft flag),
and presence signals (tests, CI, containerisation, docs). No model, no network.
"""
import os
import re
import json

from . import util

# --- licence detection ---------------------------------------------------------------------
# SPDX id → (human name, is_copyleft). Copyleft is the bit that changes how you may adopt.
_LICENSE_SIGNS = [
    ("AGPL-3.0", ("GNU Affero GPL v3", True), ("affero general public license",)),
    ("GPL-3.0", ("GNU GPL v3", True), ("gnu general public license", "version 3")),
    ("GPL-2.0", ("GNU GPL v2", True), ("gnu general public license", "version 2")),
    ("LGPL-3.0", ("GNU LGPL v3", True), ("lesser general public license",)),
    ("MPL-2.0", ("Mozilla Public License 2.0", True), ("mozilla public license",)),
    ("Apache-2.0", ("Apache License 2.0", False), ("apache license", "version 2.0")),
    ("MIT", ("MIT License", False), ("permission is hereby granted, free of charge",)),
    ("BSD-3-Clause", ("BSD 3-Clause", False), ("redistribution and use", "neither the name")),
    ("BSD-2-Clause", ("BSD 2-Clause", False), ("redistribution and use",)),
    ("ISC", ("ISC License", False), ("isc license", "permission to use, copy, modify")),
    ("Unlicense", ("The Unlicense", False), ("this is free and unencumbered software",)),
]
_LICENSE_FILES = ("license", "license.txt", "license.md", "licence", "copying", "copying.txt")


def detect_license(root):
    """Return {'spdx','name','copyleft','source'} — best effort from the LICENSE file text."""
    for name in os.listdir(root) if os.path.isdir(root) else []:
        if name.lower() in _LICENSE_FILES:
            text = util.read_text(os.path.join(root, name), limit=20000).lower()
            for spdx, (human, copyleft), needles in _LICENSE_SIGNS:
                if all(n in text for n in needles):
                    return {"spdx": spdx, "name": human, "copyleft": copyleft, "source": name}
            return {"spdx": "UNKNOWN", "name": "present but unrecognised", "copyleft": None, "source": name}
    return {"spdx": "NONE", "name": "no LICENSE file found", "copyleft": None, "source": None}


# --- manifest parsing ----------------------------------------------------------------------
def _parse_package_json(path):
    try:
        d = json.loads(util.read_text(path))
    except (ValueError, TypeError):
        return None
    deps = sorted(list((d.get("dependencies") or {}).keys()) +
                  list((d.get("peerDependencies") or {}).keys()))
    scripts = list((d.get("scripts") or {}).keys())
    entry = [v for v in (d.get("main"), d.get("module"), d.get("bin")) if isinstance(v, str)]
    return {"kind": "npm", "name": d.get("name"), "description": d.get("description"),
            "deps": deps, "scripts": scripts, "entrypoints": entry}


def _parse_pyproject(path):
    text = util.read_text(path)
    name = _toml_scalar(text, "name")
    desc = _toml_scalar(text, "description")
    # dependencies = ["a", "b>=1"] — grab the first array after a `dependencies` key
    deps = []
    m = re.search(r"(?ms)^\s*dependencies\s*=\s*\[(.*?)\]", text)
    if m:
        deps = [re.split(r"[<>=!~ \[]", s.strip().strip("'\""))[0]
                for s in re.findall(r"[\"']([^\"']+)[\"']", m.group(1))]
    scripts = re.findall(r"(?m)^\s*([\w-]+)\s*=\s*[\"'][\w.]+:[\w.]+[\"']", text)
    return {"kind": "python", "name": name, "description": desc,
            "deps": sorted(set(deps)), "scripts": scripts, "entrypoints": []}


def _toml_scalar(text, key):
    m = re.search(r"(?m)^\s*%s\s*=\s*[\"']([^\"']+)[\"']" % re.escape(key), text)
    return m.group(1) if m else None


def _parse_requirements(path):
    deps = []
    for ln in util.read_text(path).splitlines():
        ln = ln.strip()
        if ln and not ln.startswith(("#", "-")):
            deps.append(re.split(r"[<>=!~ ;\[]", ln)[0])
    return {"kind": "python", "name": None, "description": None,
            "deps": sorted(set(d for d in deps if d)), "scripts": [], "entrypoints": []}


def _parse_go_mod(path):
    text = util.read_text(path)
    mod = re.search(r"(?m)^module\s+(\S+)", text)
    deps = re.findall(r"(?m)^\s+([\w./-]+)\s+v[\d.]", text)
    return {"kind": "go", "name": mod.group(1) if mod else None, "description": None,
            "deps": sorted(set(deps)), "scripts": [], "entrypoints": []}


def _parse_cargo(path):
    text = util.read_text(path)
    deps = []
    m = re.search(r"(?ms)^\[dependencies\](.*?)(?:^\[|\Z)", text)
    if m:
        deps = re.findall(r"(?m)^([\w-]+)\s*=", m.group(1))
    return {"kind": "cargo", "name": _toml_scalar(text, "name"),
            "description": _toml_scalar(text, "description"),
            "deps": sorted(set(deps)), "scripts": [], "entrypoints": []}


_MANIFESTS = {
    "package.json": _parse_package_json,
    "pyproject.toml": _parse_pyproject,
    "setup.py": lambda p: {"kind": "python", "name": None, "description": None,
                           "deps": [], "scripts": [], "entrypoints": ["setup.py"]},
    "requirements.txt": _parse_requirements,
    "go.mod": _parse_go_mod,
    "Cargo.toml": _parse_cargo,
}


def _find_manifests(root):
    """Parse recognised manifests found at (or one level below) the repo root."""
    out = []
    roots = [root] + [os.path.join(root, d) for d in os.listdir(root)
                      if os.path.isdir(os.path.join(root, d)) and d not in util.SKIP_DIRS] \
        if os.path.isdir(root) else [root]
    seen = set()
    for base in roots[:12]:
        for fn, parser in _MANIFESTS.items():
            p = os.path.join(base, fn)
            if os.path.isfile(p) and p not in seen:
                seen.add(p)
                try:
                    got = parser(p)
                    if got:
                        got["path"] = os.path.relpath(p, root)
                        out.append(got)
                except Exception:
                    pass
    return out


def _readme_blurb(root):
    for name in ("README.md", "README.rst", "README.txt", "README", "readme.md"):
        p = os.path.join(root, name)
        if os.path.isfile(p):
            text = util.read_text(p, limit=4000)
            # first non-heading, non-badge paragraph
            for para in re.split(r"\n\s*\n", text):
                clean = re.sub(r"[#>*_`\[\]!]", "", para).strip()
                clean = re.sub(r"https?://\S+", "", clean).strip()
                if len(clean) > 40 and "shields.io" not in para and "badge" not in para.lower():
                    return re.sub(r"\s+", " ", clean)[:400]
    return None


def fingerprint(root):
    """Walk once; return the structural profile used by every later stage."""
    root = os.path.abspath(root)
    langs = {}          # language -> {'files','loc'}
    total_files = total_bytes = 0
    has_tests = has_ci = has_docker = has_docs = False
    py_pkg_dirs = set()

    for ap, rel in util.walk_source(root):
        total_files += 1
        try:
            total_bytes += os.path.getsize(ap)
        except OSError:
            pass
        low = rel.lower()
        if "/test" in "/" + low or low.startswith("test") or low.endswith(("_test.go", ".test.js", ".spec.ts")):
            has_tests = True
        if ".github/workflows" in low or low.endswith((".gitlab-ci.yml",)) or "jenkinsfile" in low:
            has_ci = True
        if "dockerfile" in os.path.basename(low) or low.endswith("docker-compose.yml"):
            has_docker = True
        if low.startswith("docs/") or low == "readme.md":
            has_docs = True

        lang = util.lang_of(rel)
        if not lang:
            continue
        loc = util.count_loc(util.read_text(ap))
        rec = langs.setdefault(lang, {"files": 0, "loc": 0})
        rec["files"] += 1
        rec["loc"] += loc

    # primary language = most LOC among real code languages
    code = {k: v for k, v in langs.items() if k in util.CODE_LANGS}
    primary = max(code, key=lambda k: code[k]["loc"]) if code else (
        max(langs, key=lambda k: langs[k]["loc"]) if langs else None)

    return {
        "root": root,
        "primary_language": primary,
        "languages": dict(sorted(langs.items(), key=lambda kv: -kv[1]["loc"])),
        "total_files": total_files,
        "total_bytes": total_bytes,
        "total_loc": sum(v["loc"] for v in langs.values()),
        "license": detect_license(root),
        "manifests": _find_manifests(root),
        "readme": _readme_blurb(root),
        "signals": {"tests": has_tests, "ci": has_ci, "docker": has_docker, "docs": has_docs},
    }
