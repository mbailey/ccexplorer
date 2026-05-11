"""Command-line entry point for ``cce``.

v0.0.1 ships one subcommand:

* ``cce build`` -- walk ``~/.claude/projects/``, aggregate, render HTML,
  open in the default browser.

Future subcommands (planned, not implemented):

* ``cce get-cost-and-usage`` -- AWS-Cost-Explorer-style flagship query
* ``cce get-dimension-values`` -- enumerate values for a dimension
* ``cce serve`` -- live local server backed by the JSONL store
* ``cce advise`` -- Trusted-Advisor-style recommendations
"""
from __future__ import annotations

import argparse
import sys
import webbrowser
from pathlib import Path

from ccexplorer import __version__
from ccexplorer.data import DEFAULT_PROJECTS_ROOT, aggregate, iter_session_files
from ccexplorer.web import write_html

DEFAULT_OUTPUT = Path("/tmp/cce.html")


def cmd_build(args: argparse.Namespace) -> int:
    root = Path(args.projects_root).expanduser()
    if not root.exists():
        print(
            f"error: projects root does not exist: {root}\n"
            "Hint: this should point at the directory Claude Code writes "
            "session JSONL files into (default: ~/.claude/projects).",
            file=sys.stderr,
        )
        return 2

    rows = aggregate(iter_session_files(root), verbose=not args.quiet)
    if not rows:
        print(f"warning: no cost-bearing sessions found under {root}", file=sys.stderr)

    output = Path(args.output).expanduser()
    write_html(rows, output)
    if not args.quiet:
        total = sum(r.cost for r in rows)
        print(f"wrote {output}  --  ${total:,.2f} across {len(rows)} rows")

    if args.open:
        webbrowser.open(output.resolve().as_uri())

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cce",
        description=(
            "Local-first Cost Explorer for Claude Code sessions. "
            "Reads ~/.claude/projects, aggregates by tool/project/session/model, "
            "and renders an interactive HTML report."
        ),
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    sub = parser.add_subparsers(dest="command")

    build = sub.add_parser(
        "build",
        help="aggregate session JSONL and write an HTML report",
        description=(
            "Walk the Claude Code projects directory, aggregate token usage, "
            "and write a single self-contained HTML report. Opens the report "
            "in the default browser unless --no-open is given."
        ),
    )
    build.add_argument(
        "--projects-root",
        default=str(DEFAULT_PROJECTS_ROOT),
        help="root directory containing <project>/<session>.jsonl trees "
             "(default: %(default)s)",
    )
    build.add_argument(
        "-o", "--output",
        default=str(DEFAULT_OUTPUT),
        help="path to write the HTML report (default: %(default)s)",
    )
    build.add_argument(
        "--no-open", dest="open", action="store_false",
        help="don't open the report in a browser after writing",
    )
    build.add_argument(
        "-q", "--quiet", action="store_true",
        help="suppress progress output",
    )
    build.set_defaults(func=cmd_build, open=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        # Default behaviour with no args: build with all defaults.
        args = parser.parse_args(["build"])
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
