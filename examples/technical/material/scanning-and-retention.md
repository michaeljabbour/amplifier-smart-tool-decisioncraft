# Virus scanning and keeping files, current setup (fictional)

- Scanning today: after upload, a background job reads the file from storage and runs the
  scanner. Average 9 seconds for files under 100 MB; up to 4 minutes for 5 GB.
- Files are shown to the customer before the scan finishes. Downloads are blocked only if
  the scan fails.
- 0.02% of uploads were flagged in the last year, all from free accounts.
- Our terms promise that deleted files are gone within 30 days, including backups.
- Account closure deletes all files after 14 days.
