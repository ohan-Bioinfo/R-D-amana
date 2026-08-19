# Chemistry — Change Log

Running log of data, pipeline, and dashboard changes (newest first), mirroring
the convention in `microbiology/CHANGELOG.md`.

---

## 2026-08-20 — Compliance Filter Scope Refactor

- **Fixed Multi-Select Compliance Filter Scope (`applyScopeFilters`):**
  - Refactored compliance filtering to evaluate `v === 1` (Compliant) and `v === 0` (Non-compliant) with exact OR logic, preventing `Unknown / No Limit` samples from being improperly included when both toggles are selected.

## 2026-08-12 — Comprehensive report relocated into chemistry/reports/

Moved the standalone HTML report next to the dashboard it documents, and made it
reachable from the places a reader actually is.

- `Gemini-reports/Chemistry_Comprehensive_Report.html` →
  **`chemistry/reports/chemistry_comprehensive_report.html`** (co-located with the
  dashboard + sunbursts; already inside the server allowlist). The file is
  self-contained, so the move needs no asset fixups.
- **Lab hub Report tile** (`chemistry/index.html`) now points at
  `reports/chemistry_comprehensive_report.html`.
- **Dashboard GSO & Quality view** guideline card now carries a real clickable
  link (opens in a new tab) to the report, so it's one click from the GSO focus
  view.
- The two `.md` companions stay in `Gemini-reports/`. Microbiology's report was
  mirrored the same way (→ `microbiology/reports/microbiology_comprehensive_report.html`,
  linked from its hub tile + GSO view), so `Gemini-reports/` now holds only the
  four `.md` companions.

## 2026-08-12 — GSO focus view + floating Hub/Sign-out nav

- The lab hub's **GSO & Quality** tile opens the dashboard with `#tab=gso&focus=1`,
  which hides the tab nav, KPI banners, and filter chrome and shows only the GSO
  categorisation (guideline + sortable GSO 1016 table + drilldown). Wired in both
  dashboards.
- `server.py` injects a small floating **⌂ Hub / Sign out** control on every served
  deliverable (dashboards, sunbursts, reports) so viewers are never stranded.

## 2026-08-11 — Comprehensive report + GSO guideline (responsive/impeccable)

Gave chemistry the same reporting set microbiology already had under
`Gemini-reports/`, and raised the whole report family to a genuinely responsive
bar. No data or parquet changes — figures below are read from the current
dashboard payload and README (15,876 rows unchanged).

- **New `Gemini-reports/Chemistry_Comprehensive_Report.html`** — standalone,
  bilingual, Najdi-Heritage-themed report mirroring micro's 8 sections (headline
  KPIs → pipeline stages → GSO classification challenges → data-quality challenges
  → numerical ledger → dashboard inventory → enhancement roadmap → timeline) with
  real figures (valid 14,677 · invalid 1,101 · no_limit 92 · rejected 4 · unknown
  2; 1,133,621 tests; 15 GSO categories).
- **Responsive/impeccable upgrade** (new report + retrofitted onto
  `Microbiology_Comprehensive_Report.html`): `clamp()` fluid type, 760/480px
  breakpoints, every table wrapped in `.table-wrap{overflow-x:auto}` with an
  edge-fade scroll cue, `prefers-reduced-motion` guard, A4 `@media print`, and a
  back-to-top affordance. The incumbent report had zero max-width breakpoints and
  overflowing tables on mobile; both now hold 390px cleanly (verified via headless
  screenshots, desktop + mobile).
- **New `.md` companions:** `Chemistry_Statistics_and_GSO_Challenges.md` and
  `Chemistry_Dashboard_Enhancement_Proposal.md`.
- **GSO & Quality tab guideline** enriched in `build_dashboard.py`: a `card-sub`
  prose card explaining the 7-tier GSO bridge, the five `validity_status` states,
  no-limit/non-detect semantics, the pesticide row-vs-sample denominator, and the
  heavy-metals/pesticides YoY spikes. Dashboard rebuilt; emitted JS passes
  `node --check`; totals unchanged.
- **Landing page:** a "Report" entry added to both lab cards in `build_landing.py`
  (→ each `*_Comprehensive_Report.html`); `index.html` rebuilt.

Spec: `docs/superpowers/specs/2026-08-11-chem-comprehensive-report-design.md`.

## 2026-08-11 — Dashboard standardized to the tabbed touch-first design

Brought the chemistry dashboard to the **same design language** as the redesigned
microbiology dashboard, so the two read as one R&D lab suite. The palette,
masthead, KPI strip, and filter-chip idioms were already shared; this adds the
structural half. Totals unchanged: **15,876 rows across 8 sections** (2024 + 2025),
**1,133,621** distinct tests; emitted JS passes `node --check`; still self-contained
offline HTML.

- **Zoom / pinch / touch on every chart.** Introduced a shared `PLOTLY_CONFIG`
  (`scrollZoom`, `displayModeBar:'hover'`, `doubleClick:'reset'`, lasso/select removed)
  and applied it at all 6 `Plotly.newPlot` sites.
- **5-tab lab-record-divider shell** (📊 Overview · 📍 Location · 🧪 Products ·
  ⚗️ Sections & tests · 📋 GSO & Quality), matching micro's tabs with "Sections & tests"
  in place of "Organisms". Masthead + Section bar + filter chips + KPI strips stay
  pinned above all tabs. Charts render once and `Plotly.Plots.resize()` on tab-show.
  The year-over-year card was relocated into the Sections & tests tab.
- **Active tab persisted in a minimal `#tab=` hash**; old links open Overview.
- **Click-to-drill** on the two charts with a matching filter: sector-breakdown bar →
  toggles that sector (`activeSectors`); GSO-category bar → toggles that category
  (`activeGso`). Charts without a filter dimension stay non-interactive (not invented).
- **Sortable GSO 1016 categories table** in the GSO & Quality tab: Category · Samples ·
  Non-compliant · NC % (NC = `is_valid === 0`, rate over evaluated samples),
  header-click sort. Represents the numbers; makes no scope judgment.

Spec: `docs/superpowers/specs/2026-08-11-chem-dashboard-standardize-design.md`.
Plan: `docs/superpowers/plans/2026-08-11-chem-dashboard-standardize-design.md`.

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
