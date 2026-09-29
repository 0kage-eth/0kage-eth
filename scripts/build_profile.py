#!/usr/bin/env python3
"""
Build the GitHub profile README from:

  1. Cyfrin public audit reports (https://github.com/Cyfrin/cyfrin-audit-reports)
     - the main README table gives audit dates, protocol name, Tech (category) and PDF link
     - each PDF's first pages are scanned for the auditor name (Kage / 0kage / Kage Alexander)
     - scan results are cached in data/cyfrin_scan_cache.json so only new PDFs are downloaded
  2. data/private_audits.json   - REDACTED (private) audits, referenced by README row
  3. data/risk_reports.json     - risk reports
  4. data/governance.json       - governance forum responses
  5. data/articles.json         - blogs / articles

Usage:
  python3 scripts/build_profile.py                 # rebuild README.md
  python3 scripts/build_profile.py --list-redacted # show REDACTED rows to pick from
  python3 scripts/build_profile.py --commit --push # rebuild, commit and push

Requires: pypdf  (pip install -r requirements.txt)
"""

import argparse
import io
import json
import os
import re
import subprocess
import sys
import urllib.request
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
CACHE_DIR = os.path.join(ROOT, ".cache", "reports")
SCAN_CACHE = os.path.join(DATA_DIR, "cyfrin_scan_cache.json")
TEMPLATE = os.path.join(ROOT, "README.template.md")
OUTPUT = os.path.join(ROOT, "README.md")

CYFRIN_REPO = "Cyfrin/cyfrin-audit-reports"
CYFRIN_BRANCH = "main"
RAW_BASE = f"https://raw.githubusercontent.com/{CYFRIN_REPO}/{CYFRIN_BRANCH}"
BLOB_BASE = f"https://github.com/{CYFRIN_REPO}/blob/{CYFRIN_BRANCH}"

# Name variants that identify me on a report's auditor page.
AUDITOR_PATTERNS = [r"0kage", r"kage\s+alexander", r"\bkage\b"]
AUDITOR_RE = re.compile("|".join(AUDITOR_PATTERNS), re.IGNORECASE)
PAGES_TO_SCAN = 5  # auditor names are on the cover / first pages

PDF_LINK_RE = re.compile(r"\[([^\]]+)\]\((\./reports/[^)]+\.pdf)\)")
DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def log(msg):
    print(msg, file=sys.stderr)


def fetch(url, binary=False):
    req = urllib.request.Request(url, headers={"User-Agent": "0kage-profile-builder"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()
    return data if binary else data.decode("utf-8")


def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, sort_keys=True)
        f.write("\n")


def md_escape(text):
    return text.replace("|", "\\|")


# --------------------------------------------------------------------------- #
# Cyfrin README parsing
# --------------------------------------------------------------------------- #
def parse_cyfrin_readme(content):
    """Return the rows of the main audit table as dicts."""
    columns = ["audit_start", "audit_end", "report", "tech", "C", "H", "M", "L", "I", "G"]
    rows = []
    in_table = False
    for line in content.splitlines():
        if not line.startswith("|"):
            if in_table:
                break
            continue
        fields = [re.sub(r"\s+", " ", f).strip() for f in line.strip().strip("|").split("|")]
        if len(fields) != len(columns):
            continue
        if fields[0] == "Audit Start":
            in_table = True
            continue
        if not in_table or set(fields[0]) <= {"-", " "}:
            continue
        if "**Total**" in line:
            break
        row = dict(zip(columns, fields))
        row["links"] = [(t, os.path.basename(p)) for t, p in PDF_LINK_RE.findall(row["report"])]
        row["prefix"] = row["report"].split("[", 1)[0].strip() if row["links"] else ""
        rows.append(row)
    if not rows:
        raise SystemExit("Could not parse the Cyfrin README audit table - format changed?")
    return rows


# --------------------------------------------------------------------------- #
# PDF scanning
# --------------------------------------------------------------------------- #
def pdf_mentions_me(filename):
    from pypdf import PdfReader  # imported lazily so --list-redacted works without it

    local = os.path.join(CACHE_DIR, filename)
    if not os.path.exists(local):
        log(f"  downloading {filename}")
        os.makedirs(CACHE_DIR, exist_ok=True)
        data = fetch(f"{RAW_BASE}/reports/{filename}", binary=True)
        with open(local, "wb") as f:
            f.write(data)
    try:
        reader = PdfReader(local)
        text = "\n".join((p.extract_text() or "") for p in reader.pages[:PAGES_TO_SCAN])
    except Exception as exc:  # corrupt / unreadable pdf
        log(f"  WARNING could not read {filename}: {exc}")
        return None
    return bool(AUDITOR_RE.search(text))


def scan_reports(rows):
    """Return {pdf filename: bool} for every PDF linked in the README."""
    cache = load_json(SCAN_CACHE, {})
    changed = False
    for row in rows:
        for _, filename in row["links"]:
            if filename in cache:
                continue
            result = pdf_mentions_me(filename)
            if result is None:
                continue
            cache[filename] = result
            changed = True
    if changed:
        save_json(SCAN_CACHE, cache)
    return cache


# --------------------------------------------------------------------------- #
# build audit entries
# --------------------------------------------------------------------------- #
def public_audit_entries(rows, scan):
    entries = []
    for row in rows:
        matched = [(t, f) for t, f in row["links"] if scan.get(f)]
        if not matched:
            continue
        names = [re.sub(r"\s*\(\\?\*\)\s*", "", t).strip().lstrip("[") for t, _ in matched]
        protocol = " ".join(x for x in [row["prefix"], ", ".join(names)] if x)
        report_date = min(DATE_RE.match(f).group(1) for _, f in matched)
        links = ", ".join(f"[{'Report' if len(matched) == 1 else t}]({BLOB_BASE}/reports/{f})" for t, f in matched)
        entries.append({
            "report_date": report_date,
            "audit_start": row["audit_start"],
            "audit_end": row["audit_end"],
            "protocol": protocol,
            "type": row["tech"],
            "link": links,
        })
    return entries


def private_audit_entries(rows):
    """Entries from data/private_audits.json.

    Each entry either references a REDACTED row of the Cyfrin README
        {"audit_start": "2026-08-19", "label": "REDACTED WI R P"}
    (report date and type are then taken from the README), or is fully manual
        {"report_date": "2025-03-01", "type": "Lending, Vault", "note": "..."}
    """
    wanted = load_json(os.path.join(DATA_DIR, "private_audits.json"), [])
    index = {(r["audit_start"], r["report"]): r for r in rows if not r["links"]}
    entries = []
    for item in wanted:
        row = index.get((item.get("audit_start"), item.get("label")))
        if row is None and "label" in item:
            log(f"  WARNING private audit not found in Cyfrin README: {item}")
        entries.append({
            "report_date": item.get("report_date") or (row["audit_end"] if row else ""),
            "audit_start": row["audit_start"] if row else item.get("audit_start", ""),
            "audit_end": row["audit_end"] if row else item.get("audit_end", ""),
            "protocol": "REDACTED",
            "type": item.get("type") or (row["tech"] if row else ""),
            "link": item.get("note") or "Private",
        })
    return entries


def render_audit_table(entries):
    entries = sorted(entries, key=lambda e: (e["report_date"], e["audit_end"]), reverse=True)
    lines = [
        "| S.No | Report Date | Protocol | Protocol Type | Report |",
        "| ---: | ----------- | -------- | ------------- | ------ |",
    ]
    for i, e in enumerate(entries, 1):
        lines.append(
            f"| {i} | {e['report_date']} | {md_escape(e['protocol'])} | "
            f"{md_escape(e['type'])} | {e['link']} |"
        )
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# generic tables for manually curated sections
# --------------------------------------------------------------------------- #
def render_simple_table(items, columns, empty_msg):
    """items: list of dicts; columns: list of (header, key)."""
    if not items:
        return f"_{empty_msg}_"
    items = sorted(items, key=lambda x: x.get("date", ""), reverse=True)
    header = "| S.No | " + " | ".join(h for h, _ in columns) + " |"
    sep = "| ---: | " + " | ".join("---" for _ in columns) + " |"
    lines = [header, sep]
    for i, item in enumerate(items, 1):
        cells = []
        for _, key in columns:
            val = item.get(key, "")
            if key == "link" and val:
                val = f"[Link]({val})"
            cells.append(md_escape(str(val)))
        lines.append(f"| {i} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def git(*args):
    subprocess.run(["git", *args], cwd=ROOT, check=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list-redacted", action="store_true", help="print REDACTED rows from the Cyfrin README and exit")
    ap.add_argument("--commit", action="store_true", help="git commit the regenerated files")
    ap.add_argument("--push", action="store_true", help="git push after committing (implies --commit)")
    args = ap.parse_args()

    log("Fetching Cyfrin README ...")
    rows = parse_cyfrin_readme(fetch(f"{RAW_BASE}/README.md"))
    log(f"  {len(rows)} audit rows found")

    if args.list_redacted:
        print("audit_start | audit_end  | label                 | tech")
        for r in rows:
            if not r["links"]:
                print(f"{r['audit_start']} | {r['audit_end']} | {r['report']:<21} | {r['tech']}")
        print('\nAdd the ones you worked on to data/private_audits.json as '
              '{"audit_start": "...", "label": "REDACTED ..."}')
        return

    log("Scanning report PDFs for auditor name ...")
    scan = scan_reports(rows)
    public = public_audit_entries(rows, scan)
    private = private_audit_entries(rows)
    log(f"  {len(public)} public audits, {len(private)} private audits")

    risk = load_json(os.path.join(DATA_DIR, "risk_reports.json"), [])
    gov = load_json(os.path.join(DATA_DIR, "governance.json"), [])
    articles = load_json(os.path.join(DATA_DIR, "articles.json"), [])

    with open(TEMPLATE, encoding="utf-8") as f:
        template = f.read()

    replacements = {
        "{{AUDIT_COUNT}}": str(len(public) + len(private)),
        "{{AUDIT_PUBLIC_COUNT}}": str(len(public)),
        "{{AUDIT_PRIVATE_COUNT}}": str(len(private)),
        "{{AUDITS_TABLE}}": render_audit_table(public + private),
        "{{RISK_REPORTS_TABLE}}": render_simple_table(
            risk, [("Date", "date"), ("Protocol", "protocol"), ("Title", "title"), ("Link", "link")],
            "No risk reports published yet."),
        "{{GOVERNANCE_TABLE}}": render_simple_table(
            gov, [("Date", "date"), ("Forum / DAO", "forum"), ("Topic", "title"), ("Link", "link")],
            "No governance responses published yet."),
        "{{ARTICLES_TABLE}}": render_simple_table(
            articles, [("Date", "date"), ("Title", "title"), ("Published At", "venue"), ("Link", "link")],
            "No articles published yet."),
        "{{LAST_UPDATED}}": date.today().isoformat(),
    }
    out = template
    for key, val in replacements.items():
        out = out.replace(key, val)

    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(out)
    log(f"Wrote {OUTPUT}")

    if args.commit or args.push:
        git("add", "README.md", "data")
        status = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT)
        if status.returncode == 0:
            log("Nothing to commit.")
            return
        git("commit", "-m", f"Update profile ({date.today().isoformat()})")
        if args.push:
            git("push")


if __name__ == "__main__":
    main()
