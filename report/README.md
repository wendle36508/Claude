# Report / dashboard artifacts

Two separate published Artifacts, for two different audiences:

## `portfolio-report.html` - recruiter-facing writeup

https://claude.ai/artifact/4W7pweYokFoiLo68MYUs7x

A narrative pitch: methodology, construction rationale, risk framework,
research notes. Hand-authored, not generated from the database. To refresh
it with new numbers: pull current figures with `python -m wealth_lab
portfolio` and `python -m wealth_lab report`, edit the relevant KPI tiles /
table rows / allocation bar widths in this file, then republish it to the
same artifact URL so the link stays live.

## `console.html` + `data.json` - working dashboard

https://claude.ai/artifact/CAZEioYamJYzt8yF559rrq

The actual tool, split into two tabs since they're different jobs:

- **Lookup** (default tab) - the stock research tool. A type-ahead search
  box (matches on symbol or company name) jumps straight to a ticker's full
  card: thesis, signals with sources, category sub-scores, composite
  score/confidence/expected range, risk metrics, IPO details if applicable.
  The "every thesis side by side" comparison table sits below it for
  browsing/sorting the whole researched universe.
- **Portfolio** - the account view: allocation bar, sleeve weights, real +
  naive risk, confidence-driven sizing suggestions. This is one application
  of the lookup tool's research, not the tool itself - kept separate on
  purpose (a user asked "which stocks are good bets" doesn't care about
  someone else's specific position sizing).

`console.html` is a static shell that fetches `data.json` at load and
renders it; it does not change when the data changes.

**To refresh it:** regenerate the data file and republish just that file to
the same artifact:

```
python -m wealth_lab.export          # writes report/data.json
```

Then republish via the Artifact tool with `url` set to the console's URL
and `files: {"data.json": "report/data.json"}` - `console.html` itself
doesn't need to be touched unless the layout or columns change.
