# Archived microbiology demos — 2026-07-18 (retired 2026-08-07)

On 2026-07-18 we built **three** standalone, self-contained "demo style"
visualizations for the microbiology data — each a separate one-file HTML,
deliberately *not* wired into the main dashboard, as a pitch to show what an
interactive presentation could look like.

Muhannad reviewed them on **2026-08-07** and chose the **zoomable sunburst**.
The other two are archived here (kept, not deleted) for reference.

## What each demo was

| Demo | Files | Concept |
|---|---|---|
| **1 · Zoomable sunburst** ✅ *kept* | `scripts/build_micro_sunburst.py` → `reports/microbiology_sunburst.html` | An agar-plate "Culture Plate": rings drill Year → Sector → GSO Category → most-severe Organism. Angle = sample count, colour = contamination. Click to zoom; a specimen "report slip" + monthly sparkline update. **This is the one we kept and are enhancing.** |
| **2 · Time-lapse survey map** 🗄️ *archived* | `build_micro_demo2_map.py`, `micro_demo2_map.html` | Riyadh sectors plotted at real lon/lat on a field-ops sheet; press-play/drag a timeline through 2024–2025, each sector station pulses (size = monthly samples, colour = contamination rate). No map tiles — plain Plotly scatter + custom slider. |
| **3 · Contamination-flow Sankey** 🗄️ *archived* | `build_micro_demo3_flow.py`, `micro_demo3_flow.html` | A Sankey styled as a paper chromatogram: non-compliant samples flow Sector → GSO Category → the organism that spoiled them (most-severe: pathogen beats indicator). Band width = contaminated samples. |

## Why the sunburst won
It carries the most information in one view (four nested dimensions + drill-down),
the agar-plate metaphor fits a microbiology lab, and the click-to-zoom + specimen
slip make it genuinely explorable rather than a static picture.

## Decision & next steps (2026-08-07)
- Keep + **enhance** the sunburst: rebrand to the Riyadh Municipality emblem &
  palette (green `#006040` / periwinkle `#8e9fc7` / white), Arabic-forward;
  add clickable breadcrumb, a volume colour metric, centre label + ring legend,
  a real colorbar + label thinning, and a shareable deep-link (URL hash).
- These two demos stay archived. To revive one, the scripts still run from
  `microbiology/` via `.venv/bin/python archive/demos-2026-07/build_micro_demo2_map.py`
  (they import from `scripts/` — run with `scripts/` on `PYTHONPATH` or move back).

## Env note
`microbiology/.venv` was repaired on 2026-08-07 (its python symlink was broken by
the project move from `/home/bioinfo/...` to `/home/lab/...`). Rebuild the kept
demo with: `microbiology/.venv/bin/python microbiology/scripts/build_micro_sunburst.py`.
