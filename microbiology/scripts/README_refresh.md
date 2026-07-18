# Refreshing the microbiology dashboard

One command rebuilds everything from the raw files:

    ./scripts/refresh.sh

It re-cleans 2024 + 2025, re-enriches (GSO join), and regenerates the
self-contained dashboard at `reports/microbiology_dashboard.html`. Share that
one file — it needs no server and opens in any browser.

## Scheduled auto-refresh (optional)

There is no live server; "fresh" means re-running the build. To refresh daily at
06:00, add a cron entry (`crontab -e`):

    0 6 * * * cd /home/bioinfo/Documents/Data-Analysis-Muhannad/microbiology && ./scripts/refresh.sh >> /tmp/micro_refresh.log 2>&1
