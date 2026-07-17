"""
oni test suite — runs fully offline (no model, no network) against the bundled fixture repo.

Verifies each stage in isolation plus the end-to-end pipeline, and that the clean-room licence
gate produces the right posture for permissive / copyleft / unknown targets.
"""
import os
import sys
import json

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from oni import fingerprint, graphmap, jewels, narrative as teardown, adopt, report, pipeline, acquire  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fixtures", "tinyrepo")
FIXTURE = os.path.abspath(FIXTURE)


@pytest.fixture(autouse=True)
def _no_llm(monkeypatch):
    """Force the heuristic path everywhere — tests must never touch a network model."""
    monkeypatch.setenv("ONI_NO_LLM", "1")


# --- acquire -------------------------------------------------------------------------------
def test_acquire_local_path():
    t = acquire.resolve(FIXTURE)
    assert t.root == FIXTURE and t.remote is False


def test_acquire_rejects_garbage():
    with pytest.raises(ValueError):
        acquire.resolve("this is not a repo or a path!!")


def test_acquire_parses_shorthand(monkeypatch):
    # don't actually clone — just verify the shorthand is understood (git absent → tarball path)
    monkeypatch.setattr(acquire, "_have_git", lambda: False)
    called = {}
    monkeypatch.setattr(acquire, "_download_tarball",
                        lambda o, r, ref, d: called.update(owner=o, repo=r) or d)
    t = acquire.resolve("Aider-AI/aider@main")
    assert called == {"owner": "Aider-AI", "repo": "aider"} and t.ref == "main"


# --- fingerprint ---------------------------------------------------------------------------
def test_fingerprint_basics():
    fp = fingerprint.fingerprint(FIXTURE)
    assert fp["primary_language"] == "Python"
    assert fp["total_files"] >= 5
    assert fp["license"]["spdx"] == "MIT" and fp["license"]["copyleft"] is False
    assert fp["signals"]["tests"] is True
    assert "example project" in (fp["readme"] or "")


def test_fingerprint_manifest_deps():
    fp = fingerprint.fingerprint(FIXTURE)
    deps = {d for m in fp["manifests"] for d in m["deps"]}
    assert "requests" in deps and "click" in deps


def test_detect_license_copyleft(tmp_path):
    (tmp_path / "LICENSE").write_text(
        "GNU AFFERO GENERAL PUBLIC LICENSE\nVersion 3, 19 November 2007\n")
    lic = fingerprint.detect_license(str(tmp_path))
    assert lic["spdx"] == "AGPL-3.0" and lic["copyleft"] is True


# --- graphmap / pagerank -------------------------------------------------------------------
def test_graphmap_ranks_engine_top():
    fp = fingerprint.fingerprint(FIXTURE)
    gmap = graphmap.build(fp)
    top_files = [f["path"] for f in gmap["files"][:2]]
    # engine.py is referenced by app.py and helpers.py → should rank at/near the top
    assert any("engine.py" in p for p in top_files)
    top_syms = [s["name"] for s in gmap["symbols"][:5]]
    assert "Engine" in top_syms


def test_pagerank_sums_to_one():
    nodes = ["a", "b", "c"]
    edges = {"a": {"b": 1.0}, "b": {"c": 1.0}, "c": {"a": 1.0}}
    from collections import defaultdict
    oe = defaultdict(lambda: defaultdict(float))
    for s, d in edges.items():
        for t, w in d.items():
            oe[s][t] = w
    r = graphmap._pagerank(nodes, oe, None)
    assert abs(sum(r.values()) - 1.0) < 1e-6
    assert all(v > 0 for v in r.values())


def test_query_personalization_biases_ranking():
    fp = fingerprint.fingerprint(FIXTURE)
    plain = graphmap.build(fp)
    biased = graphmap.build(fp, query="helpers describe double")
    # helpers.py should rank higher when the query points at it
    def rank_of(gmap, needle):
        for i, f in enumerate(gmap["files"]):
            if needle in f["path"]:
                return i
        return 999
    assert rank_of(biased, "helpers.py") <= rank_of(plain, "helpers.py")


# --- jewels --------------------------------------------------------------------------------
def test_jewels_have_excerpts():
    fp = fingerprint.fingerprint(FIXTURE)
    gmap = graphmap.build(fp)
    jw = jewels.select(gmap, n=6)
    assert jw and any(j["excerpt"] for j in jw)
    assert all("name" in j and "file" in j for j in jw)


def test_entrypoints_found():
    fp = fingerprint.fingerprint(FIXTURE)
    gmap = graphmap.build(fp)
    ep = jewels.entrypoints(fp, gmap)
    assert any("app.py" in e for e in ep) or any("main" in e for e in ep)


# --- teardown (heuristic) ------------------------------------------------------------------
def test_teardown_heuristic():
    fp = fingerprint.fingerprint(FIXTURE)
    gmap = graphmap.build(fp)
    jw = jewels.select(gmap)
    td = teardown.analyze(fp, gmap, jw, jewels.entrypoints(fp, gmap))
    assert td["_model"] is None            # no model configured
    assert td["what"] and td["how_it_works"]
    assert isinstance(td["patterns"], list)


def test_teardown_json_parse_guard():
    assert teardown._parse_json("garbage") is None
    good = '{"what":"x","how_it_works":"y","patterns":"p","strengths":[],"weaknesses":[]}'
    d = teardown._parse_json("prefix " + good + " suffix")
    assert d["patterns"] == ["p"]          # string coerced to list


# --- adopt / posture (the clean-room gate) -------------------------------------------------
def test_posture_permissive():
    p = adopt.posture({"spdx": "MIT"})
    assert p["class"] == "permissive"


def test_posture_copyleft_agpl_warns_network():
    p = adopt.posture({"spdx": "AGPL-3.0"})
    assert p["class"] == "copyleft" and "NETWORK" in p["banner"].upper()


def test_posture_unknown_is_conservative():
    p = adopt.posture({"spdx": "NONE"})
    assert p["class"] == "unknown"


def test_adopt_heuristic_plan():
    fp = fingerprint.fingerprint(FIXTURE)
    gmap = graphmap.build(fp)
    jw = jewels.select(gmap)
    td = teardown.analyze(fp, gmap, jw, [])
    pos = adopt.posture(fp["license"])
    ad = adopt.plan(fp, td, pos)
    assert "adopt" in ad and isinstance(ad["adopt"], list)


# --- end to end ----------------------------------------------------------------------------
def test_end_to_end(tmp_path):
    res = pipeline.teardown(FIXTURE, out=str(tmp_path), n_jewels=8)
    assert res["target"] == "tinyrepo"
    assert res["posture"]["class"] == "permissive"
    md = report.to_markdown(res)
    assert "# oni teardown" in md and "Crown jewels" in md and "Adoption plan" in md
    # files written
    assert os.path.exists(res["_files"]["markdown"])
    parsed = json.loads(report.to_json(res))
    assert parsed["target"] == "tinyrepo"
    # internal graph blobs must not leak into the serialised view
    assert "_file_text" not in parsed["map"]


def test_progress_callback_fires():
    seen = []
    pipeline.teardown(FIXTURE, on_progress=seen.append)
    assert "fingerprint" in seen and "adopt" in seen


# --- regression: the three defects found auditing oni against a real repo (2026-07-17) ---------
# Each of these shipped in v0.1.0 and was found only by pointing oni at a real project, not by the
# suite. They are pinned here so they cannot come back quietly.

from oni import jewels as _jewels
from oni import util as _util


def test_test_files_are_not_crown_jewels():
    """A helper defined in a test suite is not the code a project leans on.
    (oni ranked `failing` from tests/test_roost.py as roost's #4 crown jewel.)"""
    for p in ("tests/test_roost.py", "test/foo.py", "spec/thing_spec.rb", "src/x.test.js",
              "conftest.py", "pkg/__tests__/a.js", "fixtures/tinyrepo/app.py"):
        assert _util.is_test_path(p), p
    for p in ("roost/config.py", "oni/graphmap.py", "src/contest.py", "app/latest.py",
              "lib/protest/main.py"):
        assert not _util.is_test_path(p), p


def test_module_of_labels_a_symbol_by_its_file():
    assert _util.module_of("roost/config.py") == "config"
    assert _util.module_of("a/b/health.py") == "health"
    assert _util.module_of("roost/__init__.py") == "roost"      # package name, not "__init__"
    assert _util.module_of("") == ""


def test_duplicate_jewel_names_are_qualified_by_module():
    """Two real symbols can share a name; rendering both as bare "load" read as a bug:
    'the most-referenced symbols are load, load, registry'."""
    js = [{"name": "load", "file": "roost/config.py"},
          {"name": "load", "file": "roost/health.py"},
          {"name": "registry", "file": "roost/providers.py"}]
    _jewels._qualify(js)
    assert js[0]["display"] == "config.load"
    assert js[1]["display"] == "health.load"
    assert js[2]["display"] == "registry"          # unambiguous names stay clean
    assert len({j["display"] for j in js}) == 3


def test_readme_blurb_never_returns_raw_html():
    """A README opening with a centred logo/badge block must not become the "What it is" line.
    (roost's teardown reported: '<img src="docs/roost-logo.svg" alt="roost" width="440"')."""
    import tempfile
    from oni import fingerprint
    body = (
        '<div align="center">\n'
        '<img src="docs/roost-logo.svg" alt="roost" width="440">\n'
        '<h1 align="center">roost</h1>\n'
        '</div>\n\n'
        '[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)\n\n'
        'All your models under one roof: a small local gateway that routes each prompt '
        'to the model that is actually good at it.\n'
    )
    with tempfile.TemporaryDirectory() as d:
        open(os.path.join(d, "README.md"), "w", encoding="utf-8").write(body)
        blurb = fingerprint._readme_blurb(d)
    assert blurb, "should still find the real prose paragraph"
    assert "<" not in blurb and ">" not in blurb, blurb
    assert "img" not in blurb.lower() and "src=" not in blurb, blurb
    assert "shields.io" not in blurb, blurb
    assert blurb.startswith("All your models under one roof")


def test_crown_jewels_promise_matches_what_centrality_actually_finds():
    """The report must not promise 'the mechanism' when PageRank-over-references returns the
    most-depended-on code (which legitimately includes helpers). A claim outrunning the code is
    the exact shape of the roost incident."""
    from oni import report
    src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "oni", "report.py"), encoding="utf-8").read()
    assert "the mechanism lives here" not in src
    assert "study these first" not in src.lower()
