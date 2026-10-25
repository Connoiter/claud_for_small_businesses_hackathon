---
name: datamap
description: Turn a small business's pile of customer text (reviews, survey answers, support emails, feedback forms, a folder of documents) into an interactive map of what people are saying plus a plain-language insights report with suggested fixes. Use when the user types /datamap, or asks what their customers are saying, wants to make sense of a lot of reviews or feedback, or wants to see what is in a folder of documents.
---

# /datamap: hear all your customers at once

The person you are helping is usually a small business owner, not a developer.
Talk to them in plain words: say "groups", "map" and "report", never
"embeddings", "UMAP", "HDBSCAN" or "clusters". Run every command yourself.

All commands run from the repository root: the folder that holds
`pyproject.toml`, two levels above this skill's folder.

## 1. Find their data

If they didn't say what to map, ask once: "What would you like to map? A CSV or
Excel export of reviews or survey answers, or a folder of documents (.md, .txt
or .pdf)?" Exports from Google reviews, Yelp, Shopify, Typeform, Google Forms
and most help desks are fine as they are.

- CSV/Excel: the text column is detected automatically (the one with the
  longest entries). If the wrong one gets picked, rerun with
  `--text-col "<column name>"`. A `rating`/`stars` column and a `date` column
  are used automatically when present.
- Folder: every `.md`, `.txt` and `.pdf` file becomes one dot on the map.
  This includes an Obsidian vault, a "second brain", or an OKF (Open
  Knowledge Format) bundle. `index.md` and `log.md` are skipped because OKF
  reserves them, and each file's front-matter `title`, `type` and
  `description` are used.
- It needs at least 10 items, and works best from about 100 up.

Pick a short run name, e.g. `reviews-oct`.

## 2. Prepare (runs on this computer)

```
uv run datamap prepare "<file or folder>" --out out/<run-name>
```

If `uv` is missing, install it first (https://docs.astral.sh/uv/) and tell the
owner it's a one-time step. The first run downloads a small language model
(about 90 MB) and takes a few minutes; later runs take about a minute.

Tell the owner how many items and groups were found.

## 3. Name the groups (your job)

Read `out/<run-name>/briefing.md`. It lists every group with its size, average
rating, keywords and its most typical examples, then the most unusual
documents. Overwrite `out/<run-name>/labels.json`, keeping this shape:

```json
{
  "title": "What <business>'s customers are saying",
  "flags": {"r094": "crypto spam"},
  "clusters": {
    "0": {"label": "Long weekday morning lines",
          "summary": "One sentence on what these say.",
          "action": "One concrete thing the business could do."}
  }
}
```

- Every group number in the briefing needs an entry with a non-empty `label`.
- `label`: 2 to 5 words in the customer's language ("Mobile orders not ready").
  Make labels distinct from each other.
- `summary`: one sentence. Mention it if a group mixes two topics.
- `action`: specific and doable this month by a small team ("Add a third person
  7:30 to 9:30 on weekdays"), or `""` for groups that are pure praise with no
  action.
- `flags`: from the "Most unusual documents" list, only the ones that are not
  genuinely about this business (spam, scams, reviews meant for another
  business), with a 2 to 4 word reason. Leave real one-off comments out.
- `title`: use the business's name if you know it.

Only the briefing goes into your context, not the whole dataset.

## 4. Render

```
uv run datamap render --out out/<run-name>
```

If it reports a missing or empty label, fix `labels.json` and run it again.

If the folder is also published as a website (for example a Hugo site built
from the same OKF bundle), add `--link-base <site URL>`. Clicking a dot then
opens that document's page at `<site URL>/<path, lowercased, spaces as
hyphens>/`. Open one link to check that it matches the site.

## 5. Hand it over

Open `out/<run-name>/map.html` for them (`start` on Windows, `open` on macOS,
`xdg-open` on Linux). Then, in a few short lines:

1. The top 3 items from the "Fix these first" section of `insights.md` (or the
   biggest groups if there are no ratings).
2. One thing customers love, worth keeping or advertising.
3. Anything under "Worth a look" (spam to report, double posts).

Tell them that `map.html` is a single file they can email to a partner or
employee, and `insights.md` is the full report.
