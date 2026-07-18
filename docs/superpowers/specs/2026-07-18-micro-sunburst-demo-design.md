# Micro Zoomable Sunburst — Standalone Demo Design

**Date:** 2026-07-18
**Status:** Approved for build (demo, pending Muhannad's review of the result)

## Goal

A creative, highly-interactive **standalone demo** for the microbiology data — a
zoomable sunburst that drills Year → Sector → GSO Category → Organism. Completely
separate from the existing dashboard (its own file, nothing wired together);
built as a demo to show what's possible before any approval to integrate.

## Constraints

- **Standalone, self-contained HTML** — one file, opens in a browser, same
  file-share deployment model as the main dashboard.
- **Separate from the current dashboard** — new generator, new output file; do
  not modify `build_dashboard_combined.py` or the main dashboard.
- Micro-only commits (chemistry leak-check = 0); `node --check` on the emitted
  `<script>` must pass.
- Reuse the existing classification derivation (`classify()` / `_val()` from
  `build_classification_table.py`, and `SEVERITY`/organism sets) so the demo's
  categories match the dashboard.

## Data & Hierarchy

Source: `microbiology/cleaned/data2024.parquet` + `data2025.parquet` (20,880
samples). Rings, outward:

1. **Year** (2024, 2025)
2. **Sector** (5 sectors + Special; derived sector)
3. **GSO Category** (the sample's classified `gso_category`)
4. **Organism ring** — within each (year, sector, category), split into:
   - **`✓ Compliant`** — one wedge, count of compliant samples
   - **one wedge per organism** — each non-compliant sample attributed to its
     **single most-severe failed organism**: if the sample has any pathogen
     failure, its first failed test that is in the pathogen set; otherwise its
     first failed indicator. This attributes each non-compliant sample to exactly
     one organism, so `compliant + Σ organisms = category total` (exact nesting).

Wedge **angle = sample count**. Plotly sunburst with `branchvalues:'total'`;
counts computed bottom-up so every parent = sum of its children.

## Visual & Interaction

- **Chart:** Plotly native `sunburst` (Plotly already vendored/loaded). Native
  behaviour gives: click a wedge → zoom it to center with descendants; built-in
  breadcrumb (`maxdepth` + click-root) to climb out; smooth transitions; hover.
- **Color = non-compliance rate**, green→amber→red continuous scale
  (`marker.colors` = each node's %NC, `colorscale`, `cmin:0 cmax:60`), so hot
  spots read at any zoom. The `✓ Compliant` leaves render green (0%).
  A **color-metric toggle**: %non-compliance (default) · %pathogen · volume.
- **Detail panel** (right of the chart): on `plotly_sunburstclick`, show the
  clicked node's precomputed stats — total samples, compliant / non-compliant,
  %NC, top-3 failing organisms (name · count), and a small inline monthly
  sparkline (SVG, self-contained) of that segment's samples. Updates on every
  click/zoom. Clicking the center (root) resets the panel to the whole-lab view.
- **Styling:** heritage palette + fonts matching the dashboard (green/gold/sand,
  Tajawal / IBM Plex Sans Arabic), masthead-lite header, ۞ accents. Arabic
  category/organism labels render RTL-correct.

## Architecture

- New generator `microbiology/scripts/build_micro_demo.py`:
  1. Load both parquets; for each row derive `(year, sector, gso_category,
     leaf)` where `leaf` = `'✓ Compliant'` or the most-severe organism.
  2. Aggregate node counts + per-node stats (n, nc, top organisms, monthly
     series) into `ids/labels/parents/values/colors` arrays + a `nodeStats`
     map keyed by node id.
  3. Emit a self-contained HTML (inline `<script>` with the arrays + `nodeStats`
     as JSON, Plotly `react`, click handler, color toggle, detail panel, SVG
     sparkline renderer) → `microbiology/reports/micro_sunburst_demo.html`.
- Node id scheme: pipe-joined path, e.g. `2025|Central|Dairy Products|Staph…`;
  root id `''` (whole lab). `parents[i]` = the id with the last segment removed.

## Error Handling / Edge Cases

- Rows with no sector or unclassifiable category are bucketed under
  `Unspecified` at that ring (never dropped) so counts reconcile to 20,880.
- A non-compliant sample whose `failed_tests` is empty (validity disagreement)
  is attributed to a `Other` organism leaf rather than lost.
- Zero-count wedges are simply absent (not emitted).
- Colorbar clamped `cmin:0`, `cmax:60` so a single 100%-NC micro-wedge doesn't
  wash out the scale.

## Testing

- `node --check` on the emitted `<script>` — must pass.
- Generator prints total samples reconciling to 9,316 + 11,564 = 20,880, and the
  sunburst root value equals 20,880.
- Manual: click wedges → zoom + breadcrumb work; detail panel updates; color
  toggle recolors; Arabic labels render RTL.
- Micro-only commit.

## Out of Scope

- Any integration with the main dashboard (this is a standalone demo).
- Cross-filtering to other views, export, hosting, backend.
- Filters beyond the color-metric toggle (the sunburst zoom IS the exploration).
