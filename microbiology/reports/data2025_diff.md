# Cleaning diff report: Data 2025.xlsx

- **Schema:** `lab_data_2025_v1` v1
- **Rows in (raw, below header):** 11571
- **Rows after empty-row drop:** 11571
- **Rows out (canonical):** 11564
- **Rows dropped:** 0
- **Flags raised (total):** 4485

## Cells changed per column

| column | changed |
|---|---:|
| `sample_id` | 10066 |
| `sampling_date` | 4227 |
| `category_raw` | 2122 |
| `municipality_raw` | 1191 |
| `facility_name_raw` | 981 |
| `category_canonical_merged` | 153 |
| `sample_name_raw` | 0 |
| `validity_raw` | 0 |
| `invalid_tests_raw` | 0 |

## Flags raised (per flag)

| flag | count | sample value |
|---|---:|---|
| `date_parsed_from_text` | 4227 | '13/4/2025' |
| `category_merged_to_canonical` | 153 | "'القشطة (cream)' → '(cream) قشطة'" |
| `sample_type_unbucketed` | 62 | 'ايدام مصقع' |
| `sample_id_collision` | 22 | 'so-0004-r01 → so-0004-r01-a (differs in: sample_name_raw,sampling_date,category |
| `validity_says_valid_but_has_failures` | 8 | 'is_valid=true, n_failed_tests=1' |
| `sample_id_duplicate_dropped` | 7 | 'sw-2725-r01' |
| `date_year_coerced_to_2025` | 3 | '30/4/2026' |
| `date_missing` | 1 | 'nan' |
| `municipality_was_dash_placeholder` | 1 | '-' |
| `validity_says_invalid_but_no_failures` | 1 | 'is_valid=false, n_failed_tests=0' |

## Sample-Category remappings (raw → canonical)

| raw | → | canonical |
|---|---|---|
| `'"المياه الغير معبأة (Unbottled water)'` | → | `'المياه الغير معبأة (Unbottled water)'` |
| `'(Biscuits) بسكوت'` | → | `'البسكويت (Biscuits)'` |
| `'(Cooked meat )لحوم مطبوخة'` | → | `'اللحوم المطبوخة (Cooked meat)'` |
| `'(cream) كريمة'` | → | `'(cream) قشطة'` |
| `'(yogurt) زبادي'` | → | `'اللبان (yogurt)'` |
| `'(الكولسلو (الملفوف (Coleslaw) (cabbage)'` | → | `'الملفوف (cabbage)'` |
| `'القشطة (cream)'` | → | `'(cream) قشطة'` |
| `'المياه الغير المعبأة (Unbottled water)'` | → | `'المياه الغير معبأة (Unbottled water)'` |

## Test-name alias remappings (count)

| alias → canonical | count |
|---|---:|
| خمائر → الخمائر والاعفان | 276 |
| اعفان → الخمائر والاعفان | 27 |

## Output column summary

| column | dtype | non-null | nulls | unique |
|---|---|---:|---:|---:|
| `source_file` | `str` | 11564 | 0 | 1 |
| `row_excel` | `int32` | 11564 | 0 | 11564 |
| `sampling_date` | `datetime64[s]` | 11563 | 1 | 196 |
| `year_month` | `string` | 11563 | 1 | 12 |
| `iso_year_week` | `string` | 11563 | 1 | 51 |
| `quarter` | `Int8` | 11563 | 1 | 4 |
| `day_of_week` | `Int8` | 11563 | 1 | 7 |
| `sample_id` | `string` | 11564 | 0 | 11564 |
| `sample_id_raw` | `string` | 11564 | 0 | 11556 |
| `sample_name` | `string` | 11564 | 0 | 5034 |
| `category_canonical` | `string` | 11562 | 2 | 353 |
| `category_en` | `string` | 11181 | 383 | 182 |
| `category_raw` | `string` | 11562 | 2 | 361 |
| `sample_type` | `string` | 11564 | 0 | 12 |
| `facility_name` | `string` | 11549 | 15 | 656 |
| `facility_chain` | `string` | 11549 | 15 | 620 |
| `facility_branch` | `string` | 7379 | 4185 | 71 |
| `facility_name_raw` | `string` | 11549 | 15 | 656 |
| `municipality` | `string` | 11562 | 2 | 13 |
| `municipality_type` | `string` | 11562 | 2 | 3 |
| `municipality_raw` | `string` | 11563 | 1 | 16 |
| `sector` | `string` | 11495 | 69 | 5 |
| `is_valid` | `boolean` | 11564 | 0 | 2 |
| `is_failure` | `boolean` | 11564 | 0 | 2 |
| `invalid_tests_raw` | `string` | 11564 | 0 | 63 |
| `invalid_tests` | `object` | 11564 | 0 | n/a |
| `n_failed_tests` | `int32` | 11564 | 0 | 5 |
| `failed_pathogens` | `object` | 11564 | 0 | n/a |
| `failed_indicators` | `object` | 11564 | 0 | n/a |
| `has_pathogen_failure` | `boolean` | 11564 | 0 | 2 |
| `severity_tier` | `string` | 11564 | 0 | 4 |
| `data_quality_flags` | `string` | 4427 | 7137 | 13 |
| `chain_invalid_count_90d` | `int32` | 11564 | 0 | 30 |
| `is_repeat_offender_90d` | `boolean` | 11564 | 0 | 2 |