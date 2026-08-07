# Riyadh Municipality — Microbiology Lab Data

Cleans and analyses Riyadh Municipality (أمانة منطقة الرياض) food-safety
**microbiology** lab data (tests vs. **GSO 1016** standards) into two
self-contained, shareable HTML deliverables.

> Rebuilt & audited 2026-08-07. Full session log: `MICRO_NOTES_2026-08-07.md`.

## Status

| Year | Source | Samples | Notes |
|---:|---|---:|---|
| 2024 | monthly xlsx (`2024-original/2024/`) | **9,316** | GSO code native |
| 2025 | single xlsx (`2025-original/Data 2025.xlsx`) | **11,564** | GSO derived (no source code); full facility + 5-sector metadata |
| **Combined** | — | **20,880** | overall non-compliance **28.0%** |

*(2023 was dropped from this workstream. Any 22,596 / 19,658 / `data_combined_dashboard.html`
references in old docs are stale — the canonical figure is 20,880.)*

## Deliverables (in `reports/`)

- **`microbiology_dashboard.html`** — the interactive decision dashboard
  (filters, cross-filtering, URL-hash views + bookmarks, Riyadh map).
- **`microbiology_sunburst.html`** — the "Culture Plate" zoomable sunburst view
  (Year → Sector → GSO Category → Organism), Riyadh-emblem branded, bilingual,
  with a shareable deep-link.

Both are one self-contained file each (Plotly + fonts inlined from `vendor/`);
share the file, open in any browser, no server.

## Rebuild

```bash
cd microbiology
./scripts/refresh.sh                              # full: re-clean 2024+2025 → enrich → dashboard (~3 min)
.venv/bin/python scripts/build_micro_sunburst.py      # rebuild the sunburst view
```
`refresh.sh` regenerates the parquets **deterministically** (byte-identical) and
rebuilds `microbiology_dashboard.html`. The demo is a separate command.

> **Env:** `.venv` was repaired 2026-08-07 after the project moved to
> `/home/lab/storage/...` (the interpreter symlinks were dangling). `.venv/bin/python`
> works normally now.

## Active scripts (`scripts/` — 10 files)

**Core build**
| Script | Purpose |
|---|---|
| `clean_2024.py` | Year-parameterised cleaner for the 2024 monthly forms. `--year 2024`. |
| `clean_2025.py` | 2025 cleaner (single flat xlsx). Args: `<src.xlsx> <out.parquet> <diff.md>`. |
| `enrich_2024.py` | Adds pathogen/indicator/severity/repeat-offender columns. `--year 2024`. |
| `enrich_gso.py` | Applies GSO product info, panel-completeness, lab-vs-GSO cross-check. |
| `parse_gso_reference.py` | One-time parse of the GSO 1016 table → `schemas/gso_1016_reference.yaml` (only re-run if the source table changes). |
| `build_dashboard_combined.py` | Builds `microbiology_dashboard.html` from all `cleaned/data<YEAR>.parquet`. |

**Demo**
| `build_micro_sunburst.py` | Builds the sunburst view (`microbiology_sunburst.html`). |
| `demo_assets.py` | Inlines vendored Plotly + fonts into demos (offline). |
| `vendor_assets.py` | Populates `vendor/` with Plotly + fonts (run once). |

**Shared library**
| `build_classification_table.py` | `classify()` / severity sets, reused by the demo and dashboard. |

**Build inputs (not scripts):** `scripts/gso_category_corrections.csv`,
`scripts/name_gso_corrections.csv` (per-sample GSO overrides, read by the dashboard builder).

## Layout

```
microbiology/
├── 2024-original/2024/            raw source xlsx (12 monthly folders)
├── 2025-original/                 Data 2025.xlsx, Annual Report 2025.xlsx, Data_2025.csv
├── schemas/                       lab_data_2024_v2.yaml, lab_data_2025_v1.yaml, gso_1016_reference.yaml
├── assets/riyadh_emblem.jpg       Riyadh Municipality logo (used by dashboard + demo)
├── vendor/                        offline-inlined Plotly 2.35.2 + fonts
├── scripts/                       10 active scripts + refresh.sh + correction CSVs
├── cleaned/                       data2024.parquet, data2025.parquet, data2024_long.parquet
├── reports/                       the 2 deliverables + 3 pipeline audit reports
└── archive/                       everything retired (single tree — see below)
```

## Archive (`archive/`)

Single tree for everything retired. Notable subfolders:
- `validation-tools-2026-07/` — one-off review/audit workbook generators + `audit_filters.py`
  (from completed 2026-07 validation rounds; import from `scripts/`, so run with
  `scripts/` on `PYTHONPATH` if ever needed again).
- `reports-validation-2026-07/` — their `*_to_fill.xlsx` outputs + old audit `.md`/`.html`.
- `demos-2026-07/` — the two retired demos (time-lapse map, chromatogram Sankey) + NOTE.md.
- `legacy-charts-v0/` — the original numbered chart scripts + PNGs (superseded by the dashboard).
- `source-zips/`, `cleaned/`, `reports/`, `schemas/`, `scripts/`, `old-output/` — earlier iterations.
```
