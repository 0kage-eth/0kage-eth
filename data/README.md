# Data files

Each file is a JSON list. Add an entry, then run `python3 scripts/build_profile.py` from the repo root.

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

## risk_reports.json
```json
{"date": "2026-01-15", "protocol": "Aave", "title": "GHO peg risk assessment", "link": "https://..."}
```

## governance.json
```json
{"date": "2026-01-15", "forum": "Lido DAO", "title": "Response to LIP-xx", "link": "https://..."}
```

## articles.json
```json
{"date": "2026-01-15", "title": "Title", "venue": "Medium", "link": "https://..."}
```
