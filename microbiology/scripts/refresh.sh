#!/usr/bin/env bash
# One-command full refresh: re-clean both years, re-enrich, rebuild the dashboard.
# The self-contained HTML lands at reports/microbiology_dashboard.html.
set -euo pipefail
cd "$(dirname "$0")/.."          # -> microbiology/
PY=.venv/bin/python
echo "▶ 1/5 clean 2024";    "$PY" scripts/clean_2024.py --year 2024
echo "▶ 2/5 enrich 2024";   "$PY" scripts/enrich_2024.py --year 2024
echo "▶ 3/5 clean 2025";    "$PY" scripts/clean_2025.py 2025-original/'Data 2025.xlsx' \
                                 cleaned/data2025.parquet reports/data2025_diff.md
echo "▶ 4/5 enrich GSO";    "$PY" scripts/enrich_gso.py
echo "▶ 5/5 build";         "$PY" scripts/build_dashboard_combined.py
echo "✔ dashboard refreshed → reports/microbiology_dashboard.html"
