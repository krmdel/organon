---
name: "sci-writing-bib-audit"
time: "09:00"
days: "mon"
active: "true"
model: "sonnet"
notify: "on_finish"
description: "Weekly citation integrity audit of all .bib files in projects/ and clients/*/projects/"
timeout: "15m"
retry: "0"
---

You are running as a scheduled job for Organon.

Read CLAUDE.md for system context.

Task: Run the citation integrity gate on every .bib file under projects/ and clients/*/projects/, then save a summary report.

Steps:

1. Find all .bib files (excluding archived/processed paths):
   ```bash
   find projects/ clients/*/projects/ -name "*.bib" \
     -not -path "*/_processed/*" \
     -not -path "*/node_modules/*" \
     2>/dev/null | sort
   ```
   If none are found, write a single line "No .bib files found — skipping" to the output file and exit 0.

2. For each .bib file found, run the integrity check:
   ```bash
   python3 -c "
   import sys, json
   sys.path.insert(0, '.claude/skills/sci-writing/scripts')
   sys.path.insert(0, '.')
   from verify_ops import check_bib_integrity
   try:
       from writing_ops import parse_bib_file
   except ImportError:
       # Fallback: minimal inline parser (key = first word after @type{)
       def parse_bib_file(path):
           import re
           entries = {}
           with open(path) as f:
               content = f.read()
           for m in re.finditer(r'@\w+\{([^,]+),', content):
               entries[m.group(1).strip()] = {'key': m.group(1).strip()}
           return entries

   bib_path = sys.argv[1]
   entries = parse_bib_file(bib_path)
   if not entries:
       print(json.dumps({'bib': bib_path, 'entries': 0, 'findings': []}))
       sys.exit(0)

   findings = check_bib_integrity(entries)
   critical = [f for f in findings if f.get('severity') == 'critical']
   major = [f for f in findings if f.get('severity') == 'major']
   print(json.dumps({
       'bib': bib_path,
       'entries': len(entries),
       'critical': len(critical),
       'major': len(major),
       'findings': findings,
   }))
   " {bib_path}
   ```

3. Collect results across all .bib files. Save to:
   `projects/sci-writing/bib-audit_{today's date in YYYY-MM-DD format}.md`

   Format the report as:

   ```markdown
   # Weekly Bib Audit — {YYYY-MM-DD}

   | File | Entries | CRITICAL | MAJOR |
   |------|---------|----------|-------|
   | {relative path} | {n} | {n} | {n} |

   ## CRITICAL Findings (must fix before next publish)
   {list each critical finding with bib key, criterion, and suggestion}

   ## MAJOR Findings
   {list each major finding with bib key, criterion, and suggestion}

   ## Summary
   Total files audited: {n}
   Total entries checked: {n}
   Files clean (0 findings): {n}
   Total CRITICAL: {n}
   Total MAJOR: {n}
   ```

4. If any CRITICAL findings exist, write the output file path and a one-sentence summary to stderr so the cron dispatcher marks the job as needing attention.

Notes:
- Network calls hit CrossRef / arXiv / NCBI. If the network is unavailable, note it in the report and exit 0 (do not fail the job for transient network errors).
- Only audit .bib files that have at least 1 entry. Empty .bib files produce a "0 entries — skipped" row.
- Historical bib files in _processed/ are excluded (the find command above already handles this).
- The UNPAYWALL_EMAIL environment variable is sourced from .env via scripts/with-env.sh — no manual export needed.
