# Data files

Each file is a JSON list. Add an entry, then run `python3 scripts/build_profile.py` from the repo root.

## audit_overrides.json
Public reports to force-include when their markdown in `reports_md/` has no auditor block (only a few 2023 reports):
```json
{"pdf": "2023-06-01-sudoswap-report.pdf", "reason": "why"}
```

## private_audits.json
Private (REDACTED) Cyfrin audits are not attributable from the public repo, so list them here.
Run `python3 scripts/build_profile.py --list-redacted` to see the REDACTED rows, then reference one:

```json
{"audit_start": "2026-08-19", "label": "REDACTED WI R P"}
```
Report date and protocol type are taken from the Cyfrin README. A fully manual entry also works:
```json
{"report_date": "2025-03-01", "type": "Lending, Vault", "note": "Private"}
```

## risk_research.json
`type` is free text, e.g. Assessment, Incident replay, Liquidity analysis, Tool, Note.
```json
{"date": "2026-01-15", "type": "Assessment", "protocol": "Aave / GHO", "title": "GHO peg risk assessment", "link": "https://..."}
```

## governance.json
```json
{"date": "2026-01-15", "forum": "Lido DAO", "title": "Response to LIP-xx", "link": "https://..."}
```

## articles.json
Medium posts are pulled automatically from the RSS feed (cached in `medium_articles.json`).
Use this file only for articles published elsewhere (Cyfrin blog, Substack, etc.):
```json
{"date": "2026-01-15", "title": "Title", "venue": "Cyfrin Blog", "link": "https://..."}
```

## contributions.json
Open source contributions. `prs` are listed newest first.
```json
{
  "project": "Project name",
  "repo": "https://github.com/org/repo",
  "contribution": "One or two sentences on what you contributed.",
  "prs": [{"number": 74, "date": "2025-03-21", "url": "https://github.com/org/repo/pull/74"}]
}
```
