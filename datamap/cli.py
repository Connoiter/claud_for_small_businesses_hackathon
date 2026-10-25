"""`datamap prepare <input> --out <folder>` then `datamap render --out <folder>`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> None:
    # Windows consoles default to cp1252; the libraries print ✓/✗ and progress bars.
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(prog="datamap", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("prepare", help="Read, embed, lay out and group the documents.")
    p.add_argument("input", type=Path, help="A CSV/Excel file, or a folder of .md/.txt/.pdf files.")
    p.add_argument("--out", type=Path, required=True, help="Folder for this run's files.")
    p.add_argument("--text-col", help="CSV column holding the text (default: the longest one).")
    p.add_argument("--title-col", help="CSV column holding a short title (default: first words).")
    p.add_argument("--min-cluster-size", type=int, help="Smallest group worth naming.")

    r = sub.add_parser("render", help="Draw map.html and write insights.md from labels.json.")
    r.add_argument("--out", type=Path, required=True, help="The folder `prepare` wrote to.")
    r.add_argument(
        "--link-base",
        help="Website the documents are published on (e.g. a Hugo site built from an OKF "
        "bundle); clicking a dot opens <link-base>/<file path>/.",
    )

    args = parser.parse_args(argv)
    if args.command == "prepare":
        from .prepare import prepare

        prepare(args.input, args.out, args.text_col, args.title_col, args.min_cluster_size)
    else:
        from .render import render

        render(args.out, args.link_base)


if __name__ == "__main__":
    main()
