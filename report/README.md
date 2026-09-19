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

The actual tool: every thesis's composite score, confidence, expected
floor/base/ceiling range, category sub-scores, risk metrics, and full
signal list with sources - sortable, click a row to expand it - plus the
funded portfolio's allocation and risk. `console.html` is a static shell
that fetches `data.json` at load and renders it; it does not change when
the data changes.

**To refresh it:** regenerate the data file and republish just that file to
the same artifact:

```
python -m wealth_lab.export          # writes report/data.json
```

Then republish via the Artifact tool with `url` set to the console's URL
and `files: {"data.json": "report/data.json"}` - `console.html` itself
doesn't need to be touched unless the layout or columns change.
