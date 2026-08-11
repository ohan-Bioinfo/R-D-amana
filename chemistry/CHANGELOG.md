# Chemistry — Change Log

Running log of data, pipeline, and dashboard changes (newest first), mirroring
the convention in `microbiology/CHANGELOG.md`.

---

## 2026-08-11 — Chemistry dashboard rebuilt & activated on the landing page

User direction: build the chemistry dashboard (chemistry phase opens after
microbiology sign-off).

### Dashboard rebuild + audit
- Rebuilt `reports/chemistry_dashboard.html` from the current 14 parquets:
  **15,876 rows · 8 sections · 2024+2025**.
- Audited against the parquets: payload row counts match every section-year
  exactly; `validity_status` distribution identical (valid 14,677 · invalid
  1,101 · no_limit 92 · rejected 4 · unknown 2). JS passes `node --check`;
  markup balanced; the 4 half-width cards are intentional side-by-side pairs
  (not the lone-card bug fixed in microbiology).
- Build stamp present in the masthead (date + time), same as microbiology.

### Landing page
- Chemistry card activated: removed the ✕ "under construction" glyph, the
  greyed ring, the disabled entries, and the "Audit in progress" badge.
- Three live links: Dashboard, Interactive (Plotly assay-plate sunburst),
  Interactive 2 (D3 sunburst).

### README
- The per-section table was stale (older cleaning run; summed to 16,069 vs
  the real 15,876). Replaced with current parquet counts and recomputed the
  YoY invalid-rate delta table (heavy metals +12.0 pp ⚠️, pesticides
  +8.5 pp ⚠️; honey added). Noted jam 2024 = 82/83 `no_limit`.

### Known open items (from CHEM_NOTES, unchanged)
- 167 pesticide samples flagged invalid with no limit-exceeding row.
- `analysis_section` free-text column is dirty (spelling variants) — unused
  by the dashboards, which key sections off parquet filenames.
- Sunburst sample denominator: 15,297 unique samples (pesticides collapsed),
  5.8% NC — vs 15,876 rows in the dashboard. Both documented as intended.

### Files touched
- `chemistry/reports/chemistry_dashboard.html` (regenerated)
- `chemistry/README.md` (tables refreshed)
- `build_landing.py`, `index.html` (chemistry card activated)
