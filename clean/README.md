# Riyadh Lab — Combined Clean Dataset

Self-contained snapshot of the cleaned chemistry + microbiology pipelines with
a single joint dashboard. Sample-keyed across both domains so you can see which
physical samples were tested in which lab(s), and how the verdicts compare.

## Layout

```
clean/
├── chemistry/                       12 parquets + 12 xlsx mirrors
│   ├── chem_aflatoxins_2024.parquet            chem_aflatoxins_2024.xlsx
│   ├── chem_aflatoxins_2025.parquet            chem_aflatoxins_2025.xlsx
│   ├── chem_food_chemistry_2024.parquet        chem_food_chemistry_2024.xlsx
│   ├── chem_food_chemistry_2025.parquet        chem_food_chemistry_2025.xlsx
│   ├── chem_heavy_metals_2024.parquet          chem_heavy_metals_2024.xlsx
│   ├── chem_heavy_metals_2025.parquet          chem_heavy_metals_2025.xlsx
│   ├── chem_honey_2025.parquet                 chem_honey_2025.xlsx
│   ├── chem_hormones_antibiotics_2025.parquet  chem_hormones_antibiotics_2025.xlsx
│   ├── chem_pesticides_2024.parquet            chem_pesticides_2024.xlsx
│   ├── chem_pesticides_2025.parquet            chem_pesticides_2025.xlsx
│   ├── chem_water_analysis_2024.parquet        chem_water_analysis_2024.xlsx
│   └── chem_water_analysis_2025.parquet        chem_water_analysis_2025.xlsx
│
├── microbiology/                    5 parquets + 5 xlsx mirrors
│   ├── data2023.parquet         data2023.xlsx           (wide, per sample)
│   ├── data2023_long.parquet    data2023_long.xlsx      (long, per sample-test)
│   ├── data2024.parquet         data2024.xlsx
│   ├── data2024_long.parquet    data2024_long.xlsx
│   └── data2025.parquet         data2025.xlsx           (wide only; 2025 source is per-sample)
│
├── scripts/
│   ├── build_joint_dashboard.py    regenerates the joint dashboard
│   └── export_to_xlsx.py           regenerates the xlsx mirrors
│
├── reports/
│   └── joint_dashboard.html        single self-contained light-theme dashboard
│
└── README.md
```

Each xlsx has two sheets:
- `data` — the table, with bold headers, frozen top row, autofilter, sensible column widths
- `summary` — per-column inventory (non-null counts + sample values)

xlsx files are mirrors of the parquets — exact same numbers, just in a format Excel can open.

## Headline numbers

| | Test events | Unique physical samples |
|---|---:|---:|
| Chemistry (2024 + 2025) | 15,786 | 12,615 |
| Microbiology (2023 + 2024 + 2025) | 22,596 | 11,735 |
| **Union (joint dashboard total)** | — | **23,402** |
| Tested in **chemistry only** | | 11,667 |
| Tested in **microbiology only** | | 10,787 |
| **Tested in BOTH labs** | | **948** (all in 2025) |

### Cross-tested samples (948) — chem verdict × micro verdict

|  | Micro Valid | Micro Invalid | Micro Unknown |
|---|---:|---:|---:|
| **Chem Valid** | **621** both pass | 121 chem ✓ / micro ✗ | 0 |
| **Chem Invalid** | 132 chem ✗ / micro ✓ | **68** both fail | 0 |
| **Chem Unknown** | 4 | 2 | 0 |

**253 samples (26.7%)** had disagreeing verdicts between the two labs —
worth a follow-up.

## How to use the dashboard

Open `clean/reports/joint_dashboard.html` in any browser.

**Filters:**
- **Year**: All / 2023 / 2024 / 2025
- **Domain**: All / Chemistry only / Microbiology only / Tested in BOTH
- **Verdict**: All / Valid / Invalid / Unknown
- **Search**: live filter on sample ID, name, facility, municipality, failed test
- **2×2 matrix**: click any cell to filter the drilldown to that combination
- **Reset**: clears all filters

**Cards:**
- 6 KPIs at top (unique samples, per-domain counts, valid/invalid)
- Cross-tested validity matrix (chem × micro 2×2)
- Domain breakdown pie
- Monthly volume stacked bar
- Year-on-year fail rate per domain
- Top failed tests / pesticides / pathogens (purple = chemistry, green = microbiology)
- Top repeat-offender facilities
- Sample-category breakdown
- Drilldown table — 300 matching samples, invalid first

**Download CSV** exports the currently-filtered drilldown.

## Risk-assessment model

Each unique physical sample gets a **risk score (0-100)** and a **tier**:

| Score | Tier | Meaning |
|---:|---|---|
| 0 | None | passed all panels |
| 1-25 | Low | minor exceedance or low-toxicity excursion |
| 26-50 | Medium | moderate exceedance or single indicator-level micro failure |
| 51-75 | High | significant pathogen presence or 2-5× critical-contaminant exceedance |
| 76-100 | **Critical** | multi-pathogen or extreme (>5×) critical-contaminant exceedance |

**Composite = max(chemistry component, microbiology component) + 5 if invalid in BOTH.**

### Chemistry component
Base score from `value / limit` ratio:
- 1-2×: 25 · 2-5×: 50 · 5-10×: 70 · >10×: 90

Multiplied by **contaminant weight**:
- 1.0× — Lead, Mercury, Cadmium, Arsenic, Aflatoxins, banned pesticides
- 0.8× — Restricted pesticides
- 0.7× — Chromium, Nickel, Uranium, Nitrite
- 0.5-0.6× — other metals (Cu, Zn, Fe, Mn…)
- 0.3-0.4× — quality tests (pH, moisture, ash, sugar tests)

### Microbiology component
Maps the cleaner's `severity_tier`:
- `none` → 0
- `indicator_only` (coliform, total bacteria) → 30
- `pathogen` (one critical pathogen: Salmonella, E. coli O157, Listeria, Staphylococcus…) → 65
- `multi_pathogen` → 95

### Current distribution

| Tier | Samples | % |
|---|---:|---:|
| None | 19,782 | 84.5% |
| Low | 255 | 1.1% |
| Medium | 2,224 | 9.5% |
| High | 977 | 4.2% |
| **Critical** | **164** | **0.7%** |

Of the 164 Critical: 137 micro-only, 19 cross-tested in both labs, 8 chemistry-only.

Source: `clean/scripts/risk.py` — standalone-runnable for inspection.

## Verdict aggregation rule

For each physical sample (keyed by `year + lowercase sample_id`):

| Within a domain | Multiple test results → |
|---|---|
| Any **invalid** result | sample is **Invalid** for that domain |
| Else any **valid** result | sample is **Valid** for that domain |
| Else | **Unknown** |

The same hierarchy applies across the dashboard's "overall verdict" KPIs.

## Sample-ID matching

Chemistry parquets store `sample_id` lowercased (e.g. `mango-0004-r01`).
Microbiology stores the original casing (e.g. `1-2637-R01`, `OO-OSS-po-0307-R01`).
The joint dashboard lowercases both sides before joining, so the 948 cross-tested
samples are correctly matched.

## Regenerating

```bash
# Re-run after updating either pipeline's parquets:
.venv/bin/python clean/scripts/build_joint_dashboard.py
.venv/bin/python clean/scripts/export_to_xlsx.py   # regenerate xlsx mirrors

# To re-run a source pipeline:
.venv/bin/python chemistry/scripts/clean_chemistry.py --section all
.venv/bin/python food_analysis/Iter-2/scripts/clean_2024.py --year 2024   # etc.

# Then re-copy if you want the clean/ snapshot updated:
cp chemistry/cleaned/*.parquet clean/chemistry/
cp food_analysis/Iter-2/cleaned/*.parquet clean/microbiology/
.venv/bin/python clean/scripts/build_joint_dashboard.py
.venv/bin/python clean/scripts/export_to_xlsx.py
```

Shared venv lives at `food_analysis/Iter-2/.venv/`.

## Per-domain dashboards

The per-domain dashboards still exist and remain useful for deep-dives:

- `chemistry/reports/chemistry_dashboard.html` — section/year filters, per-section drilldowns
- `food_analysis/Iter-2/reports/data_combined_dashboard.html` — microbio map, GSO panel audit, pathogen filter, sector view
