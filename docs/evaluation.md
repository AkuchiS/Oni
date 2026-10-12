# Reproducible source-analysis examples

Measured on 2026-10-12 with Oni `0.2.0rc1`, Python 3.12.3, Linux x86_64.
Each case ran five times in one process, with offline analysis and no target execution.
The repeated top-ten file ranking was identical for every run of each case.
A separate regression test compares duplicate-symbol rankings in fresh processes with three
different hash seeds; these timing measurements alone do not establish cross-process determinism.

| Case | Files seen | Source LOC counted | Median elapsed | Highest-ranked files |
|---|---:|---:|---:|---|
| Bundled tinyrepo | 8 | 42 | 0.0027 s | `core/engine.py`, `app.py`, `core/helpers.py` |
| Oni baseline `5cb7a372` | 32 | 1,737 | 0.0289 s | `oni/llm.py`, `oni/util.py`, `oni/acquire.py` |
| Requests `v2.32.5` | 118 | 13,627 | 0.0674 s | `src/requests/models.py`, `src/requests/sessions.py`, `src/requests/cookies.py` |

These are small local smoke measurements, **not** a REA comparison, a cold-start benchmark,
a scalability claim, or proof that the ranking captures architectural importance.
Oni's source filters affect file/LOC counts. Timing excludes acquisition and process startup;
filesystem cache and hardware influence it. Raw measurements record the platform and all runs:
[tinyrepo](examples/tinyrepo-measurement.json), [Oni](examples/oni-measurement.json),
[Requests](examples/requests-measurement.json).

## Case 1: a known dependency graph

The bundled fixture has three non-empty source modules and an empty package initializer. `app.py` and `core/helpers.py` both refer to the
engine. Oni ranks `core/engine.py` first. This is a small controlled signal that centrality
works on a known graph. [Read the complete generated report](examples/tinyrepo.md).

```sh
python3 scripts/evaluate.py fixtures/tinyrepo --revision bundled-tinyrepo-5cb7a372
python3 -m oni fixtures/tinyrepo --offline
```

## Case 2: Oni analyzing its earlier source

Analyze the original public revision independently of this candidate's new files:

```sh
git clone https://github.com/AkuchiS/Oni.git /tmp/oni-baseline
git -C /tmp/oni-baseline checkout --detach 5cb7a37253b70224148417a837bd752b4553eb7f
python3 scripts/evaluate.py /tmp/oni-baseline --revision 5cb7a37253b70224148417a837bd752b4553eb7f
```

Shared helpers and the optional LLM adapter rank above the pipeline. That illustrates the
meaning of the measure: source references can make utility modules central even when a specific
execution path, such as offline mode, never calls them. Read the pipeline to establish control flow.

## Case 3: Requests, a recognizable public library

```sh
git clone --depth 1 --branch v2.32.5 https://github.com/psf/requests.git /tmp/requests-case
git -C /tmp/requests-case rev-parse HEAD
python3 scripts/evaluate.py /tmp/requests-case --revision b25c87d7cb8d6a18a37fa12442b5f883f9e41741
```

Verify that HEAD matches the recorded revision before comparing measurements. Models, sessions
and cookies lead the structural ranking. This gives a reader concrete places to investigate;
it does not establish correctness, request behaviour or security. The case analyzes source only
and does not install or execute Requests. Upstream: [Requests at the measured revision](https://github.com/psf/requests/tree/b25c87d7cb8d6a18a37fa12442b5f883f9e41741).

Git acquisition above uses the network; the following evaluation is offline. Use fresh destination
paths, and do not overwrite existing work. `--revision` records the supplied identifier; the script
does not independently authenticate provenance. This page's revisions were checked with Git.

## Next useful evidence

Add reviewed cases in other languages, large-repository resource measurements, and an annotated
set of architecture-relevant files before claiming broad ranking quality. Capture a screen demo
from these same commands after the release is approved, so the recording matches a public version.
