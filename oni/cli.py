"""
oni command line.

    oni <target> [options]

    <target>   a local path, a GitHub URL, or owner/repo[@ref]

Examples:
    oni Aider-AI/aider
    oni ./some/local/repo --query "repo map ranking"
    oni https://github.com/psf/requests --no-llm --out ./teardowns
"""
import os
import sys
import argparse

from . import __version__, pipeline, report


def build_parser():
    p = argparse.ArgumentParser(
        prog="oni",
        description="Reverse-engineer a repo down to the patterns worth rebuilding (clean-room).",
    )
    p.add_argument("target", nargs="?", help="local path | GitHub URL | owner/repo[@ref]")
    p.add_argument("-o", "--out", default=None, help="write TEARDOWN.md + teardown.json to this dir")
    p.add_argument("-q", "--query", default=None,
                   help="bias the crown-jewel ranking toward a concept (e.g. 'authentication')")
    p.add_argument("-n", "--jewels", type=int, default=12, help="how many crown jewels to surface")
    p.add_argument("-c", "--context", default=None,
                   help="your own context so the adoption plan maps ideas onto it")
    p.add_argument("--no-llm", action="store_true", help="skip the model; structural teardown only")
    p.add_argument("--json", action="store_true", help="print JSON to stdout instead of Markdown")
    p.add_argument("--cache-dir", default=None, help="clone remotes here (kept) instead of a tempdir")
    p.add_argument("-V", "--version", action="version", version="oni " + __version__)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    if not args.target:
        build_parser().print_help()
        return 2
    if args.no_llm:
        os.environ["ONI_NO_LLM"] = "1"

    def progress(stage):
        sys.stderr.write("  oni: %s…\n" % stage)
        sys.stderr.flush()

    try:
        result = pipeline.teardown(
            args.target, out=args.out, query=args.query, n_jewels=args.jewels,
            context=args.context, cache_dir=args.cache_dir, on_progress=progress,
        )
    except (ValueError, RuntimeError) as e:
        sys.stderr.write("oni: %s\n" % e)
        return 1

    if args.json:
        print(report.to_json(result))
    else:
        print(report.to_markdown(result))
    if result.get("_files"):
        sys.stderr.write("\n  wrote %s\n  wrote %s\n" % (result["_files"]["markdown"], result["_files"]["json"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
