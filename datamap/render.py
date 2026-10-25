"""Labels -> a single-file interactive map (map.html) and a report for the owner (insights.md)."""

from __future__ import annotations

import html
import json
import re
from datetime import date
from urllib.parse import quote
from pathlib import Path

import numpy as np
import pandas as pd

from .ingest import rating_column
from .prepare import NOISE, typical_examples

NOISE_LABEL = "Fits no group"
LOW_RATING = 3.0


def render(out: Path, link_base: str | None = None) -> None:
    df = pd.read_parquet(out / "points.parquet")
    vectors = np.load(out / "embeddings.npy")
    labels = load_labels(out / "labels.json", df)

    print("Drawing the map ...")
    write_map(df, labels, out / "map.html", link_base)
    write_insights(df, vectors, labels, out / "insights.md")
    print(f"Wrote {out / 'map.html'} and {out / 'insights.md'}")


def load_labels(path: Path, df: pd.DataFrame) -> dict:
    labels = json.loads(path.read_text(encoding="utf-8"))
    clusters = labels.get("clusters", {})
    expected = {str(c) for c in df["cluster"].unique() if c != NOISE}
    missing = sorted(expected - clusters.keys(), key=int)
    if missing:
        raise SystemExit(f"labels.json has no entry for group(s) {', '.join(missing)}.")
    blank = sorted((c for c in expected if not clusters[c].get("label", "").strip()), key=int)
    if blank:
        raise SystemExit(f"labels.json has an empty label for group(s) {', '.join(blank)}.")
    return labels


def write_map(df: pd.DataFrame, labels: dict, path: Path, link_base: str | None = None) -> None:
    import datamapplot

    names = labels["clusters"]
    layer = np.array(
        [NOISE_LABEL if c == NOISE else names[str(c)]["label"] for c in df["cluster"]],
        dtype=object,
    )
    rating = rating_column(df)
    extra = pd.DataFrame(
        {
            "snippet": [html.escape(_shorten(t, 360)) for t in df["text"]],
            "doc_title": [html.escape(str(t)) for t in df["title"]],
            "meta": [html.escape(_meta_line(row, rating)) for _, row in df.iterrows()],
        }
    )
    template = (
        '<div style="max-width:380px">'
        '<div style="font-weight:600;margin-bottom:4px">{doc_title}</div>'
        '<div style="font-size:12px;color:#777;margin-bottom:6px">{meta}</div>'
        '<div style="font-size:13px;line-height:1.35">{snippet}</div>'
        "</div>"
    )
    kwargs = {}
    if link_base and "source_file" in df.columns and df["source_file"].nunique() == len(df):
        extra["url"] = [page_url(link_base, f) for f in df["source_file"]]
        kwargs["on_click"] = "window.open(`{url}`, '_blank')"
    dates = _dates(df)
    if dates is not None:
        kwargs.update(histogram_data=dates, histogram_group_datetime_by="month")

    plot = datamapplot.create_interactive_plot(
        df[["x", "y"]].to_numpy(),
        layer,
        hover_text=df["text"].map(lambda t: _shorten(t, 120)).tolist(),
        title=labels.get("title", "Datamap"),
        sub_title=f"{len(df)} documents grouped by meaning. Hover a dot to read it; search above.",
        noise_label=NOISE_LABEL,
        extra_point_data=extra,
        hover_text_html_template=template,
        enable_search=True,
        point_radius_min_pixels=4,
        point_radius_max_pixels=14,
        offline_mode=True,
        **kwargs,
    )
    plot.save(str(path))


def write_insights(df: pd.DataFrame, vectors: np.ndarray, labels: dict, path: Path) -> None:
    rating = rating_column(df)
    names = labels["clusters"]
    n = len(df)
    groups = sorted(int(c) for c in names if int(c) in set(df["cluster"]))

    def stats(c):
        members = df[df["cluster"] == c]
        avg = members[rating].mean() if rating else None
        return len(members), avg

    lines = [
        f"# {labels.get('title', 'Insights')}",
        "",
        f"_{n} documents, {len(groups)} groups. Made {date.today():%B %d, %Y}. "
        "Open `map.html` in any browser to explore them._",
        "",
    ]

    if rating:
        pains = [c for c in groups if stats(c)[1] is not None and stats(c)[1] < LOW_RATING]
        pains.sort(key=lambda c: -stats(c)[0])
        if pains:
            lines += ["## Fix these first", ""]
            for c in pains[:3]:
                count, avg = stats(c)
                action = names[str(c)].get("action") or names[str(c)].get("summary", "")
                lines.append(f"1. **{names[str(c)]['label']}**: {count} people, average {avg:.1f}★. {action}")
            lines.append("")

    lines += ["## All groups", ""]
    header = "| Group | Documents | Share |" + (" Avg rating |" if rating else "")
    lines += [header, "|---|---:|---:|" + ("---:|" if rating else "")]
    for c in groups:
        count, avg = stats(c)
        row = f"| {names[str(c)]['label']} | {count} | {count / n:.0%} |"
        lines.append(row + (f" {avg:.1f}★ |" if rating else ""))
    noise_count = int((df["cluster"] == NOISE).sum())
    if noise_count:
        lines.append(f"| _{NOISE_LABEL}_ | {noise_count} | {noise_count / n:.0%} |" + (" |" if rating else ""))
    lines.append("")

    for c in groups:
        info = names[str(c)]
        count, avg = stats(c)
        heading = f"### {info['label']} ({count}, {count / n:.0%}"
        lines += [heading + (f", {avg:.1f}★)" if rating else ")"), ""]
        if info.get("summary"):
            lines += [info["summary"], ""]
        if info.get("action"):
            lines += [f"**Try:** {info['action']}", ""]
        examples = typical_examples(df, vectors, c, 6)
        for _, row in examples[examples["duplicate_of"].isna()].head(2).iterrows():
            lines += [f"> {_shorten(row['text'], 280)}", ">", f"> _{_meta_line(row, rating)}_", ""]

    lines += _worth_a_look(df, labels.get("flags", {}))
    lines += [
        "## How this was made",
        "",
        "Everything except naming the groups ran on this computer: the text was turned into "
        "vectors with all-MiniLM-L6-v2, laid out with UMAP, grouped with HDBSCAN and drawn "
        "with DataMapPlot (UMAP, HDBSCAN and DataMapPlot are open source from the Tutte "
        "Institute for Mathematics and Computing). Claude read a few typical examples per "
        "group to name it.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _worth_a_look(df: pd.DataFrame, flags: dict) -> list[str]:
    lines = ["## Worth a look", ""]
    by_id = df.set_index("id")
    flagged = [i for i in flags if i in by_id.index]
    if flagged:
        lines += [f"**Probably not about your business ({len(flagged)}).** Report or ignore these:", ""]
        lines += [
            f"- `{i}` ({flags[i]}): {_shorten(by_id.loc[i, 'text'], 140)}" for i in flagged
        ]
        lines.append("")
    dups = df[df["duplicate_of"].notna()]
    if len(dups):
        lines += [f"**Near-duplicates ({len(dups)}).** The same text saved or posted twice; count it once:", ""]
        lines += [f"- `{r['id']}` repeats `{r['duplicate_of']}`" for _, r in dups.head(10).iterrows()]
        lines.append("")
    one_offs = df[~df["id"].isin(flagged) & df["duplicate_of"].isna()].nlargest(5, "oddness")
    if len(one_offs):
        lines += ["**Unusual one-offs.** Unlike anything else in this collection; worth a second look:", ""]
        lines += [f"- `{r['id']}`: {_shorten(r['text'], 160)}" for _, r in one_offs.iterrows()]
        lines.append("")
    return lines if len(lines) > 2 else []


def page_url(link_base: str, source_file: str) -> str:
    """Where Hugo publishes content/<source_file> by default: extension dropped,
    lowercased, spaces to hyphens, trailing slash. Check against the real site."""
    slug = re.sub(r"\s+", "-", source_file.rsplit(".", 1)[0].strip()).lower()
    return f"{link_base.rstrip('/')}/{quote(slug)}/"


def _meta_line(row: pd.Series, rating: str | None) -> str:
    parts = []
    if rating and pd.notna(row.get(rating)):
        parts.append("★" * int(round(row[rating])))
    for col in ("type", "domain", "date", "source", "source_file"):
        if col in row and pd.notna(row[col]) and str(row[col]).strip():
            parts.append(str(row[col]))
            if col == "source":
                break
    return " · ".join(parts)


def _dates(df: pd.DataFrame):
    if "date" not in df.columns:
        return None
    dates = pd.to_datetime(df["date"], errors="coerce")
    return dates if dates.notna().mean() > 0.9 else None


def _shorten(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + " …"
