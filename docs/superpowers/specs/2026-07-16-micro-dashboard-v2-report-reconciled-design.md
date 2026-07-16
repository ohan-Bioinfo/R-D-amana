# Microbiology Dashboard v2 — Report-Reconciled, Sector-Level, Single-Tier Filters

**Date:** 2026-07-16
**Status:** Design approved (pending spec review)
**Scope:** Microbiology only. No chemistry files are touched.

## 1. Problem

Muhannad reviewed the combined micro dashboard against the official **Annual
Report** and raised 22 points. Investigation groups them into five root causes:

1. **Reconciliation gap (by design).** The dashboard recomputes every number from
   our cleaned parquet, which diverges from the report by construction:
   - **Date basis** — we key on *sampling* date; the report keys on *receive/report*
     date. This shifts samples between adjacent months (May −295, Aug −439…) while
     keeping the year total within ~1.4%.
   - **Dedup** — we removed 7 duplicate sample IDs / suffixed 11 collisions; the
     report kept them.
   - **Replicate test counting** — the report counts test *runs* (incl. replicates
     and confirmatory tests); our `invalid_tests` counts a failure once per sample.
   - Net: 2025 samples 11,564 (ours) vs 11,404 (report) = **+160**; 2025 compliance
     73.7% vs 73.18%. The 2025 data is essentially correct.
2. **2024 is geography-blind and short.** The raw 2024 per-day files carry **no
   municipality / sector / facility** (all null in `data2024.parquet`), and 2024 is
   **1,014 samples short** of the user's 2024 report (769 compliant + 245
   non-compliant). No 2024 Annual Report exists in the repo yet.
3. **Wrong geography granularity.** The report groups by **5 sectors** (القطاع الأوسط
   / Central 38.5% biggest, then East 30.6%, North 17.8%, West 7.0%, South 5.6% +
   العينات الخاصة / Special 0.5%). We invented a 16-sub-municipality layer (only 11
   populated, North empty), so "highest-risk = الروضة" (a sub-municipality) instead
   of Central.
4. **Approximated test counts + wrong "top test".** 2025 source is one-row-per-
   sample, so total tests are *estimated* (3.9 × samples = 45,100); the report Test
   sheet has the exact **46,309**. The "top failing test = Staph" card ranks the top
   *pathogen by count*; the report ranks **all tests by failure rate** (Total Count
   22.9% first).
5. **Scope/slice filter model confuses.** Severity + microbe are "slice" filters that
   drive only 5 of 15 figures, so they feel dead. Pathogen-only shows indicator
   co-failures (العد الكلي) in the organism chips. The facilities chart is scope-bound
   and ignores the microbe filter.

Additionally: the "96.6% compliance" the user saw is a **misread** — the current
build computes 72% overall (2024 69.6%, 2025 73.7%), matching the report; 96.6% is
the inverse of the 3.4% *pathogen* failure rate ("Pathogen failures" card).

## 2. Decisions (user-approved)

| Decision | Choice |
|---|---|
| Source of truth for headline numbers | **Annual Report** (match 1:1) |
| 2024 data | User provides **2024 Annual Report + richer 2024 raw with geography** |
| Layout | **Two-tier** — static official figures + interactive explorer |
| Geography | **5 sectors + Special** only; drop the 16-sub-municipality layer & filter |
| Filter model | **Single tier** — every filter drives every chart + KPI |

## 3. Architecture

Two tiers on one page, plus a data-dependent third phase.

```
┌─ Tier 1 · OFFICIAL ANNUAL FIGURES (per year, from Annual Report) ─ matches 1:1
│    KPIs · per-test failure-rate table · 5-sector split
├─ Tier 2 · INTERACTIVE EXPLORER (from cleaned parquet) ─ every filter → every chart
│    single-tier filters · 5-sector geography · rate-based rankings
└─ Tier 3 · 2024 ENRICHMENT (needs user files) ─ re-clean 2024 with geography
```

### 3.1 Tier 1 — Official Annual Figures *(new)*

**New module `microbiology/scripts/annual_report.py`.** Parses the report workbook
into a per-year JSON block consumed by the dashboard builder. It must not fail the
whole build if a sheet/label is missing (degrade to "n/a").

Reads (MICRO stream only):
- **`Compliance rate` sheet** → total samples, valid (compliant) samples, compliance
  rate, monthly breakdown. 2025: total 11,404, valid 8,345, 73.18%.
- **`Test` sheet** → MICRO total tests (46,309) and per-test `{total, compliant,
  invalid, rate = invalid/total}`. Produces the ranked failure-rate table.
- **`Municipalities` sheet** → per-sector sample counts (collection basis, 17,648:
  Central 6,790 / East 5,405 / North 3,133 / West 1,230 / South 995 / Special 95).
  Labelled in Tier 1 exactly as the report labels it ("samples collected by sector")
  so its different basis (collection, not micro-tested) is not conflated with the
  compliance totals.

Output shape (per year): `{ total_samples, compliant, compliance_rate,
total_tests, non_compliant_tests, per_test: [{name_ar, total, invalid, rate}],
sectors: [{name_ar, samples, pct}] }`.

**Rendering** — a year-tabbed band at the top of the page:
- KPI row: Total samples · Compliance % · Total tests · Non-compliant tests.
- Per-test failure-rate table, **sorted by rate desc** (reproduces the user's
  expected ordering).
- 5-sector distribution bar.
- Header note: "Official figures — Annual Report <year>".

2025 is wired immediately. 2024 slots in when its report file is provided; until
then the 2024 tab shows "Annual Report 2024 not yet ingested".

### 3.2 Tier 2 — Interactive Explorer *(modify `build_dashboard_combined.py`)*

1. **Single filter tier.** Remove the `SCOPE_CHIPS` / `SLICE_CHIPS` split and the
   `rowsScope / rowsSliced / rowsActive` three-way partition. Every active filter
   (year, date, compliance, sector, GSO category, microbe, severity, pathogen-only,
   repeat-only, exclude-meat) contributes to **one** `rowsFiltered` set that feeds
   **every** render function. `rowsActive` (severity ≠ none) is retained only where a
   chart is intrinsically about severity events (severity-month, heatmap), derived as
   `rowsFiltered.filter(sev ≠ none)` locally.
   - Compliance-rate KPI: when the active filter set restricts to non-compliant
     samples (compliant count = 0), show a **"filter mode"** badge instead of a
     misleading 0%/100% (reuse existing `allNonCompliant` logic).
2. **Geography → 5 sectors + Special.** Remove the sub-municipality multi-select
   filter and the 16-district map/aggregation. Map bubbles, the sector chart, and a
   renamed **"Highest-risk sector"** KPI aggregate at sector level
   (Central/North/West/East/South + Special) using `derive_sector_5`. Sub-municipality
   → sector mapping (`SECTOR_5_OF_SUBMUNI`) stays as the internal lookup that assigns
   each row a sector; it is no longer surfaced as a filter dimension.
3. **Top failing test → failure rate across all tests.** Replace the "Most frequent
   pathogen" KPI/logic with a ranking of **every** test by `invalid / total` rate
   (pathogens + indicators together), matching the report. The Tests panel gains a
   rate view.
4. **Organism chips.** In the most-contaminated ranking, when a pathogen-only or
   specific-microbe filter is active, tally **only the filtered organism class** in
   the chips (drop indicator co-failures under a pathogen filter). With no microbe
   filter, behaviour is unchanged.
5. **Remove the subtitle count line** ("N samples in scope · N in slice · …").
6. **Clarify the pathogen card.** Relabel/reformat so its value can never be read as
   compliance (e.g. "Pathogen-failure rate: 3.4% (N samples)"), removing the 96.6%
   inverse confusion.
7. **Test counts.** Exact counts live in Tier 1. The interactive "Total tests
   performed" KPI is **removed** from Tier 2 (the estimate can't compete with the
   official figure, and 2025 has no per-test data to compute it honestly).

All Tier-2 charts continue to derive from the cleaned parquet and remain fully
interactive.

### 3.3 Tier 3 — 2024 enrichment *(depends on user files)*

When the user provides **2024 raw with geography** + **Annual Report 2024**:
- Extend `clean_2024.py` (or a variant) to read municipality/sector/facility from the
  richer raw and populate those columns instead of `None`.
- Re-run the 2024 pipeline → `data2024.parquet` gains geography; 2024 sector/facility
  charts and rankings become populated.
- `annual_report.py` ingests the 2024 report → Tier-1 2024 tab.
- Reconcile the 1,014-sample gap against the 2024 report (expected to close once the
  richer raw is used).

File landing convention: richer raw under `microbiology/2024-original/…`; report at
`microbiology/2024-original/Annual Report 2024.xlsx` (confirmed with user at handoff).

## 4. Traceability — 22 points → resolution

| # | User point | Resolution |
|---|---|---|
| 1 | Samples 2024 −1014 / 2025 +160 | T1 shows report totals; 2025 +160 documented (dedup/date); 2024 via T3 |
| 2 | Remove subtitle line | T2 #5 |
| 3 | Compliant 2024 −769 | T1 report figure; 2024 via T3 |
| 4 | Compliance 96.6% vs 70% | Misread (build=72%); T2 #6 clarify pathogen card; T1 shows 73.18% |
| 5 | Remove sub-municipality filter | T2 #2 |
| 6 | Non-comp 2024 −245 / 2025 −20 | T1 report; 2024 via T3 |
| 7 | Severity filters dead | T2 #1 single tier |
| 8 | Sub-municipality 11 vs 16 / North empty | Resolved by dropping sub-municipality (T2 #2) |
| 9 | Tests 2024 36,596 vs 31,583 | T1 exact (needs 2024 report) |
| 10 | Highest-risk sector "no data" | T2 #2 sector ranking; 2024 via T3 |
| 11 | "Highest-risk chain" meaning + no data | T2 #1 (reacts to filters); label clarified; 2024 facilities via T3 |
| 12 | 2025 11,564 vs 11,404 (+160) | T1 report; delta documented |
| 13 | 2025 tests 45,100 vs 46,309 | T1 exact 46,309 |
| 14 | 2025 non-comp tests 3,730 vs 4,211 | T1 exact |
| 15 | Highest-risk = الروضة not Central | T2 #2 sector-level → Central |
| 16 | Highest facility = Othaim | T2 with sector + rate context; re-validated after fixes |
| 17 | Top test 2025 = Staph vs report ranking | T1 per-test rate table + T2 #3 |
| 18 | Top test 2024 = Staph vs report ranking | T1 + T2 #3 |
| 19 | Filters still broken | T2 #1 single tier |
| 20 | Pathogen filter shows العد الكلي in top-10 | T2 #4 org-chip class fix |
| 21 | Microbe filter not reflecting on facilities | T2 #1 (facilities chart reacts) |
| 22 | Filter at sector not sub-municipality | T2 #2 |

## 5. Phasing

- **Phase 1 (now):** `annual_report.py` + Tier-1 band (2025) + all Tier-2 interactive
  fixes. No dependency on new files.
- **Phase 2 (on user files):** ingest Annual Report 2024 (Tier-1 2024) + richer 2024
  raw (Tier-3 geography), then reconcile the 2024 gap.

## 6. Verification

- **Tier 1 matches report:** assert parsed totals equal the report's Total row (2025:
  11,404 / 8,345 / 73.18% / 46,309 tests) and per-test rates match the user's ranking.
- **Single-tier filters:** every render function receives `rowsFiltered`; picking a
  severity or microbe chip changes KPIs, facilities, sectors, and subtypes (not just
  5 charts).
- **Sector geography:** exactly 5 sectors + Special appear; no sub-municipality filter
  remains; "Highest-risk sector" returns a sector, and Central leads by volume.
- **Top test by rate:** the top-test ranking lists Total Count first (2025), matching
  the report.
- **Org chips:** under pathogen-only, no indicator organism appears in the chips.
- **No chemistry files staged** on any commit (`git diff --cached --name-only | grep -c chemistry` = 0).

## 7. Open items / dependencies

- **2024 richer raw + Annual Report 2024** — required for Phase 2; Phase 1 proceeds
  without them.
- Exact 2024 report column layout unknown until the file arrives; `annual_report.py`
  parsing for 2024 is finalised then.
- The `Municipalities` sheet is collection-basis (17,648), not micro-tested totals;
  Tier 1 presents it labelled as such and does not reconcile it against the 11,404
  micro total.
