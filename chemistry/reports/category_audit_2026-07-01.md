# Chemistry category audit — 2026-07-01 (Phase 0, no changes applied)

Workbook: `category_audit_2026-07-01.xlsx` (8 sheets). Rules are DRAFT — confirm before Phase 1.

Three buckets, kept separate on purpose:

- **SUSPECT** = a known category that is WRONG for the section (the real mislabels — D1/D2/D3).
- **review** = allowed but worth a look (e.g. fruit/veg in aflatoxins — dried ok, fresh not).
- **UNCLASSIFIED** = 2024 rows with no source category the name-guesser couldn't place — a coverage gap, NOT a mislabel. Phase 1 fixes with section-aware guessing.

## SUSPECT — genuine cross-section mislabels (D1/D2/D3)

- **107 SUSPECT** + **18 review**. See `suspect_rows` sheet.

  - SUSPECT: aflatoxins 2024 → المشروبات (93)
  - SUSPECT: aflatoxins 2024 → عسل (7)
  - SUSPECT: aflatoxins 2024 → اللحوم والدواجن (2)
  - SUSPECT: food_chemistry 2024 → مياه الحنفية (1)
  - SUSPECT: food_chemistry 2025 → مياه الحنفية (1)
  - SUSPECT: pesticides 2024 → الأسماك والمأكولات البحرية (1)
  - SUSPECT: pesticides 2024 → المشروبات (1)
  - SUSPECT: water_analysis 2025 → اللحوم والدواجن (1)
  - review: aflatoxins 2025 → الفواكه والخضار (18)

## UNCLASSIFIED — 2024 name-guesser coverage gap (2519 rows)

- Not mislabels — no source category exists in 2024. Top unmatched names are in the `unclassified_names` sheet; Phase 1 will extend the section-aware name rules to absorb them.
  - pesticides 2024: 1749 rows
  - food_chemistry 2024: 489 rows
  - aflatoxins 2024: 255 rows
  - heavy_metals 2024: 9 rows
  - water_analysis 2024: 7 rows
  - water_analysis 2025: 5 rows
  - heavy_metals 2025: 4 rows
  - pesticides 2025: 1 rows

## D4 — filter-water name merge → «مياه فلتر»

- 461 rows across 189 distinct names. See `merge_filter_water`.

## D5 — شطة name merge → «شطة»

- 132 rows across 47 distinct names. See `merge_shatta`.

## M1 — water failed-test recovery

- 2025: 64 invalid water samples, **54** get failed-tests surfaced from `invalid_test` (10 still empty). See `water_M1_2025`.
- 2024: 46 invalid water samples, **41** recovered from red cells (red-scan: ok). See `water_M1_2024_red`.

## Proposed per-section valid categories (draft — confirm)

- **aflatoxins**: الأطعمة الجاهزة للأكل, البهارات والصوصات, الحبوب والبقوليات, الحلويات والشوكولاتة  _(review: الفواكه والخضار)_
- **food_chemistry**: الأسماك والمأكولات البحرية, الأطعمة الجاهزة للأكل, الأعلاف, البهارات والصوصات, الحبوب والبقوليات, الحلويات والشوكولاتة, الحليب ومنتجات الألبان, الدهون والزيوت, الفواكه والخضار, اللحوم والدواجن, المشروبات, عسل
- **heavy_metals**: الأسماك والمأكولات البحرية, الأطعمة الجاهزة للأكل, الأعلاف, البهارات والصوصات, الحبوب والبقوليات, الحلويات والشوكولاتة, الحليب ومنتجات الألبان, الدهون والزيوت, الفواكه والخضار, اللحوم والدواجن, المشروبات, عسل, مياه الحنفية, مياه شرب/معبأة, مياه فلتر
- **honey**: الأطعمة الجاهزة للأكل, عسل
- **hormones_antibiotics**: الأسماك والمأكولات البحرية, الحليب ومنتجات الألبان, اللحوم والدواجن
- **pesticides**: الأطعمة الجاهزة للأكل, البهارات والصوصات, الحبوب والبقوليات, الحليب ومنتجات الألبان, الدهون والزيوت, الفواكه والخضار
- **water_analysis**: مياه الحنفية, مياه شرب/معبأة, مياه فلتر