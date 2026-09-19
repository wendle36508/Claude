# Portfolio report

`portfolio-report.html` is the source for the published artifact at
https://claude.ai/artifact/4W7pweYokFoiLo68MYUs7x — the recruiter-facing
writeup/dashboard for the paper portfolio tracked in `wealth_lab/`.

It's hand-authored, not generated from the database. To refresh it with new
numbers: pull current figures with `python -m wealth_lab portfolio` and
`python -m wealth_lab report`, edit the relevant KPI tiles / table rows /
allocation bar widths in this file, then republish it to the same artifact
URL so the link stays live. Add new research-note cards under "Research
notes" the same way new signals get logged in the tracker.
