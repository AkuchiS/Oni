"""
The one-call entrypoint that runs all seven stages and returns the full result dict.

    acquire → fingerprint → graphmap → jewels → teardown → adopt → report

Unavailable model responses fall back to heuristics; acquisition failures are reported.
"""
import os

from . import acquire, fingerprint as fp_mod, graphmap, jewels as jewels_mod, narrative as td_mod, adopt as adopt_mod


def teardown(target, out=None, query=None, n_jewels=12, context=None, cache_dir=None, on_progress=None, offline=False, no_llm=False, use_llm=False):
    """Reverse-engineer `target` (path | URL | owner/repo) → result dict (+ files if `out`).

    query    : bias the crown-jewel ranking toward a concept ("authentication", "planner").
    context  : the adopter's own context, so the adoption plan maps ideas onto it.
    on_progress(stage) : optional callback for UIs.
    offline  : require a local directory and disable model requests.
    use_llm  : explicitly opt into the configured model transport (default False).
    no_llm   : disable model requests for this call (remote acquisition still allowed).
    """
    def step(name):
        if on_progress:
            try:
                on_progress(name)
            except Exception:
                pass

    step("acquire")
    tgt = acquire.resolve(target, cache_dir=cache_dir, offline=offline)
    try:
        step("fingerprint")
        fp = fp_mod.fingerprint(tgt.root)

        step("graphmap")
        gmap = graphmap.build(fp, query=query)

        step("jewels")
        jw = jewels_mod.select(gmap, n=n_jewels)
        ep = jewels_mod.entrypoints(fp, gmap)

        step("teardown")
        td = td_mod.analyze(fp, gmap, jw, ep, use_llm=use_llm and not (offline or no_llm))

        step("adopt")
        pos = adopt_mod.posture(fp["license"])
        ad = adopt_mod.plan(fp, td, pos, target_context=context, use_llm=use_llm and not (offline or no_llm))

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
