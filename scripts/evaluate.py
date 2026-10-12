"""Run one supplied local source case repeatedly, offline. Never clone or execute it."""
import argparse
import hashlib
import json
import platform
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from oni import __version__, pipeline

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("target")
parser.add_argument("--revision", required=True, help="source revision/fixture identifier, recorded verbatim")
parser.add_argument("--runs", type=int, default=5)
args = parser.parse_args()
if not 1 <= args.runs <= 20:
    parser.error("runs must be between 1 and 20")
timings, rankings = [], []
for _ in range(args.runs):
    start = time.perf_counter()
    result = pipeline.teardown(args.target, offline=True)
    timings.append(time.perf_counter() - start)
    rankings.append([f["path"] for f in result["map"]["files"][:10]])
    if result["teardown"]["_model"] is not None:
        raise RuntimeError("offline analysis unexpectedly used a model")
repeatable = all(rank == rankings[0] for rank in rankings)
if not repeatable:
    raise RuntimeError("ranking changed between repeated runs")
print(json.dumps({
    "oni_version": __version__, "python": platform.python_version(),
    "platform": platform.system() + " " + platform.machine(),
    "target": result["target"], "source_revision": args.revision,
    "runs": args.runs, "offline": True,
    "files": result["fingerprint"]["total_files"], "loc": result["fingerprint"]["total_loc"],
    "top_files": rankings[0], "repeatable_top10": repeatable,
    "ranking_sha256": hashlib.sha256(json.dumps(rankings[0]).encode()).hexdigest(),
    "seconds": timings, "median_seconds": statistics.median(timings),
    "interpretation": "Local structural smoke measurement, not comparative performance or ranking accuracy.",
}, indent=2))
