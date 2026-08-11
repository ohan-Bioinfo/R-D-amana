# Chemistry Comprehensive Report + GSO Guideline — Design Spec

**Date:** 2026-08-11
**Status:** Approved (design + scope confirmed by user 2026-08-11)
**Mode (impeccable):** Read — comprehension-first, extending the existing "Najdi Heritage" visual system.

## Goal

Give the **chemistry** pipeline the same reporting/guideline artifacts the
**microbiology** pipeline already has under `Gemini-reports/`, and use the
occasion to raise the whole report family to a genuinely **responsive,
impeccable** bar. The two comprehensive reports must read as siblings from one
R&D lab suite — identical visual system, chemistry-specific truthful content.

## Why now

- `Gemini-reports/` holds micro's `Microbiology_Comprehensive_Report.html` + two
  `.md` companions. Chemistry has **none** of these.
- Rechecking the incumbent micro report through the impeccable lens exposed a
  real craft gap: it has **one** `@media print` rule and **zero** `max-width`
  breakpoints. On mobile its `.data-table`s overflow the page (no scroll
  wrapper), paddings/type are fixed-px, and `fadeUp` has no reduced-motion
  guard. "Responsive/impeccable" is the actual deliverable, not a nicety.

## Scope (all approved)

1. **`Gemini-reports/Chemistry_Comprehensive_Report.html`** — new, responsive,
   real figures. The primary deliverable.
2. **Retrofit** the responsive/impeccable upgrade onto
   `Gemini-reports/Microbiology_Comprehensive_Report.html` so both match.
3. **`.md` companions:** `Chemistry_Statistics_and_GSO_Challenges.md` +
   `Chemistry_Dashboard_Enhancement_Proposal.md`.
4. **Enrich** the chem dashboard's "📋 GSO & Quality" tab `card-sub` guideline
   prose (in `chemistry/scripts/build_dashboard.py`) to micro's depth, then
   rebuild `chemistry/reports/chemistry_dashboard.html`.
5. **Landing link:** add the report(s) to `build_landing.py`, rebuild
   `index.html`.

## Visual system — preserve & unify (do NOT redesign)

Incumbent authority = the micro report CSS + both dashboards. All share the
**Najdi Heritage** token set (`--green-900 #0a3d24`, `--gold-500 #c8a85a`,
`--clay-500 #a8331a`, `--sand-50 #faf6ee`, `--ink-900 #1a1f2c`) and fonts
(Tajawal, IBM Plex Sans Arabic, DM Mono, Cormorant Garamond, loaded from Google
Fonts with system fallbacks). Chemistry is distinguished **only** by content and
iconography (⚗️/🧪, sector language) — **no palette divergence**. Reuse the
existing component classes: `.masthead`, `.toc`, `.kpi-grid/.kpi`,
`.data-table`, `.priority-card`, `.inv-grid/.inv-card`, `.timeline`,
`blockquote`, `footer`.

## The responsive/impeccable upgrade (shared by both reports)

- Fluid type: `clamp()` on masthead `h1` and section `h2`.
- Breakpoints at ~760px and ~480px: collapse masthead/`.page` padding, tighten
  grid gaps, drop KPI value size a step.
- **Wrap every `.data-table` in `.table-wrap{ overflow-x:auto; -webkit-overflow-scrolling:touch }`**
  with a right-edge fade cue. This fixes the #1 mobile break.
- Touch targets ≥44px on TOC links.
- `@media (prefers-reduced-motion: reduce)` disables `fadeUp` and smooth scroll.
- A real `@media print` block: A4-clean, no animation, avoid card page-breaks.
- Back-to-top affordance (small, unobtrusive).

## Content structure — mirror micro's 8 sections, chemistry-scoped

1. **Headline numbers** (KPI grid) — real figures below.
2. **Pipeline stages** — `clean_chemistry.py` → validity judgment →
   categorization → dashboard/sunburst (from chem scripts).
3. **GSO 1016 classification challenges** — chem-specific: 8 analytical
   sections, Arabic sample naming, `category_corrections.csv`, analyte handling.
4. **Data-quality & statistical challenges** — chem-specific:
   `validity_status` states (valid / invalid / **no_limit** / rejected /
   unknown), what `no_limit` means, pesticides per-analyte row explosion,
   comparison-prefix / detection-limit handling, date anomalies, small-n
   sections.
5. **Numerical ledger** — the verified figures (below), no placeholders.
6. **Dashboard inventory** — 5 tabs, 6 Plotly charts + sortable GSO table, 2
   sunbursts.
7. **Enhancement opportunities** — chem-specific priority tiers.
8. **Implementation roadmap** — phased timeline.

## Verified figures (source: chem dashboard `DATA` payload + README/CHANGELOG, 2026-08-11)

- **15,876 cleaned rows** · 8 sections · 2 years (2024: **6,441** / 2025: **9,435**).
- Per-section `n_total`: aflatoxins **2,269**, food_chemistry **7,000**,
  heavy_metals **1,138**, honey **70**, jam **83** (2024-only),
  hormones_antibiotics **9** (2025-only), pesticides **4,701**,
  water_analysis **606**.
- Sample `validity_status`: valid **14,677** · invalid **1,101** ·
  no_limit **92** · rejected **4** · unknown **2**. `is_valid`: 1→14,677,
  0→1,101, null→98. Non-compliance = **1,101 / 15,778 evaluated ≈ 6.98%**
  (sunburst reports 5.8% over 15,297 unique samples after pesticide collapse).
- **1,133,621 distinct test results** (2024: 634,978 · 2025: 498,643).
  Test-level compliance: compliant **1,131,632** · non_compliant **1,243** ·
  not_evaluated **746**.
- **15 GSO 1016 categories**; largest Fruit & Vegetables **7,257**, smallest
  Ready to Eat Foods **2**.
- YoY invalid-rate concern: heavy_metals **4.1%→16.1% (+12.0 pp)**, pesticides
  **8.3%→16.9% (+8.5 pp)**.

## Out of scope

- No change to chem cleaning logic, parquets, or dashboard data.
- No new palette / font / logo. No unrelated refactor.

## Verification

- `node /home/lab/.claude/skills/impeccable/scripts/detect.mjs --json <targets>`
  over the two reports once, at the end.
- Desktop + mobile screenshots (batched, one round), fix findings, one confirm
  round, stop.
- Rebuilt dashboard/landing: JS `node --check` clean, figures unchanged.
