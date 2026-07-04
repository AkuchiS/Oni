"""
The one-call entrypoint that runs all seven stages and returns the full result dict.

    acquire → fingerprint → graphmap → jewels → teardown → adopt → report

Every stage is fail-soft; a stage that can't run degrades rather than aborting the run.
"""
import os

from . import acquire, fingerprint as fp_mod, graphmap, jewels as jewels_mod, narrative as td_mod, adopt as adopt_mod


def teardown(target, out=None, query=None, n_jewels=12, context=None, cache_dir=None, on_progress=None):
    """Reverse-engineer `target` (path | URL | owner/repo) → result dict (+ files if `out`).

    query    : bias the crown-jewel ranking toward a concept ("authentication", "planner").
    context  : the adopter's own context, so the adoption plan maps ideas onto it.
    on_progress(stage) : optional callback for UIs.
    """
    def step(name):
        if on_progress:
            try:
                on_progress(name)
            except Exception:
                pass

    step("acquire")
    tgt = acquire.resolve(target, cache_dir=cache_dir)
    try:
        step("fingerprint")
        fp = fp_mod.fingerprint(tgt.root)

        step("graphmap")
        gmap = graphmap.build(fp, query=query)

        step("jewels")
        jw = jewels_mod.select(gmap, n=n_jewels)
        ep = jewels_mod.entrypoints(fp, gmap)

        step("teardown")
        td = td_mod.analyze(fp, gmap, jw, ep)

        step("adopt")
        pos = adopt_mod.posture(fp["license"])
        ad = adopt_mod.plan(fp, td, pos, target_context=context)

        result = {
            "target": tgt.slug,
            "source": tgt.source,
            "ref": tgt.ref,
            "fingerprint": fp,
            "map": gmap,
            "jewels": jw,
            "entrypoints": ep,
            "teardown": td,
            "posture": pos,
            "adoption": ad,
        }

        if out:
            step("report")
            _emit(result, out)
        return result
    finally:
        if tgt.remote:
            tgt.cleanup()


def _emit(result, out):
    from . import report
    os.makedirs(out, exist_ok=True)
    slug = result["target"].replace("/", "__")
    md = os.path.join(out, "%s.TEARDOWN.md" % slug)
    js = os.path.join(out, "%s.teardown.json" % slug)
    with open(md, "w", encoding="utf-8") as f:
        f.write(report.to_markdown(result))
    with open(js, "w", encoding="utf-8") as f:
        f.write(report.to_json(result))
    result["_files"] = {"markdown": md, "json": js}
