"""`datamap prepare <input> --out <folder>` then `datamap render --out <folder>`.

For a folder of markdown notes, run `datamap okf <notes> --out <folder>` first and
prepare `<folder>/documents.parquet`. For a website, `datamap crawl <url> --out <notes>`
makes that folder of notes.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> None:
    # Windows consoles default to cp1252; the libraries print ✓/✗ and progress bars.
    # Line buffering keeps progress visible when output goes to a log file (e.g. `serve`).
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

    parser = argparse.ArgumentParser(
        prog="datamap", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)

    c = sub.add_parser(
        "crawl",
        help="Read a website (same site only, robots.txt respected) into a folder of notes "
        "for `datamap okf`.",
    )
    c.add_argument("url", help="Where to start, e.g. https://example.com/")
    c.add_argument("--out", type=Path, required=True, help="Folder for the page notes.")
    c.add_argument("--max-pages", type=int, default=150)

    o = sub.add_parser(
        "okf",
        help="Tidy a copy of a markdown notes folder into an OKF bundle and write the "
        "documents table for `prepare`.",
    )
    o.add_argument("notes", type=Path, help="The notes folder (never modified).")
    o.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Folder for this run's files; the bundle goes in <out>/okf_bundle.",
    )

    p = sub.add_parser("prepare", help="Read, embed, lay out and group the documents.")
    p.add_argument(
        "input",
        type=Path,
        help="A CSV/Excel file, a folder of .md/.txt/.pdf files, or the documents.parquet "
        "written by `datamap okf`.",
    )
    p.add_argument("--out", type=Path, required=True, help="Folder for this run's files.")
    p.add_argument("--text-col", help="CSV column holding the text (default: the longest one).")
    p.add_argument("--title-col", help="CSV column holding a short title (default: first words).")
    p.add_argument("--min-cluster-size", type=int, help="Smallest group worth naming.")

    r = sub.add_parser("render", help="Draw map.html and write insights.md from labels.json.")
    r.add_argument("--out", type=Path, required=True, help="The folder `prepare` wrote to.")
    r.add_argument(
        "--link-base",
        help="Website the documents are published on (e.g. a Hugo site built from an OKF "
        "bundle); clicking a dot opens <link-base>/<document id>/ instead of the original file.",
    )

    s = sub.add_parser(
        "serve",
        help="Run the owner web page (web/) with the pipeline behind its Build button.",
    )
    s.add_argument("--port", type=int, default=8000)
    s.add_argument("--no-open", action="store_true", help="Don't open a browser.")

    args = parser.parse_args(argv)
    if args.command == "crawl":
        from .crawl import crawl

        crawl(args.url, args.out, max_pages=args.max_pages)
    elif args.command == "serve":
        from .server import serve

        serve(args.port, open_browser=not args.no_open)
    elif args.command == "okf":
        from .convert_to_okf import convert
        from .okf_to_documents import write_documents

        convert(args.notes, args.out / "okf_bundle")
        write_documents(args.out / "okf_bundle", args.out)
        print(f"Next: datamap prepare {args.out / 'documents.parquet'} --out {args.out}")
    elif args.command == "prepare":
        from .prepare import prepare

        prepare(args.input, args.out, args.text_col, args.title_col, args.min_cluster_size)
    else:
        from .render import render

        render(args.out, args.link_base)


if __name__ == "__main__":
    main()
