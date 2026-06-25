"""Phase 3 cleaner — applies schemas/lab_data_2025_v1.yaml to Data 2025.xlsx.

Public API:
    clean_2025(path) -> pd.DataFrame
    clean_2025_with_audit(path) -> tuple[pd.DataFrame, dict]

CLI:
    python clean_2025.py <input.xlsx> <output.parquet> <diff.md>
"""
from __future__ import annotations

import re
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import yaml


SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schemas" / "lab_data_2025_v1.yaml"

ZERO_WIDTH = "​‌‍﻿"
RTL_MARKS = "‎‏‪‫‬‭‮⁦⁧⁨⁩"
NBSP = " "

ENGLISH_PARENS_AFTER  = re.compile(r"^(.+?)\s*\(\s*([A-Za-z][A-Za-z0-9 &/,.\-']*?)\s*\)\s*$")
ENGLISH_PARENS_BEFORE = re.compile(r"^\(\s*([A-Za-z][A-Za-z0-9 &/,.\-']*?)\s*\)\s*(.+?)$")
LATIN_RUN_RE = re.compile(r"[A-Za-z][A-Za-z0-9 &,.\-']{2,}")
ARABIC_CHAR_RE = re.compile(r"[؀-ۿ]")

DATE_TEXT = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")
SAMPLE_ID_RE = re.compile(r"^([A-Za-z]+)-(\d+)-([Rr])(\d+)$")
# Match a chain/branch separator: a hyphen, en-dash, or em-dash with whitespace
# on AT LEAST one side (so legitimate intra-name dashes like '7-Eleven' don't split).
FACILITY_SPLIT_RE = re.compile(r"\s+[-–—]\s*|\s*[-–—]\s+")

NOMINAL_YEAR = 2025

CATEGORY_CANONICAL_MERGES = {
    'المياه الغير المعبأة (Unbottled water)': 'المياه الغير معبأة (Unbottled water)',
    '"المياه الغير معبأة (Unbottled water)': 'المياه الغير معبأة (Unbottled water)',
    '(Cooked meat )لحوم مطبوخة': 'اللحوم المطبوخة (Cooked meat)',
    '(الكولسلو (الملفوف (Coleslaw) (cabbage)': 'الملفوف (cabbage)',
    'القشطة (cream)': '(cream) قشطة',
    '(cream) كريمة': '(cream) قشطة',
    '(Biscuits) بسكوت': 'البسكويت (Biscuits)',
    '(yogurt) زبادي': 'اللبان (yogurt)',
}


class SchemaValidationError(Exception):
    pass


def load_schema() -> dict:
    with SCHEMA_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------
def normalise_text(v):
    if v is None:
        return None
    if isinstance(v, float) and pd.isna(v):
        return None
    if not isinstance(v, str):
        return v
    s = unicodedata.normalize("NFKC", v)
    for ch in ZERO_WIDTH + RTL_MARKS:
        s = s.replace(ch, "")
    s = s.replace(NBSP, " ").replace("\t", " ")
    s = s.replace("\\t", " ").replace("\\n", " ").replace("\\r", " ")
    s = s.replace("\\", "/")
    s = re.sub(r"/{2,}", "/", s)
    s = re.sub(r"^[\s\n]+", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s if s != "" else None


def parse_sampling_date(v) -> tuple[date | None, list[str]]:
    """Returns (date_or_None, list_of_flags). Multiple flags possible
    (e.g. parsed-from-text AND year-coerced)."""
    if v is None:
        return None, ["date_missing"]
    if isinstance(v, datetime):
        return _coerce_year(v.date())
    if isinstance(v, date):
        return _coerce_year(v)
    if isinstance(v, float) and pd.isna(v):
        return None, ["date_missing"]
    if isinstance(v, str):
        s = v.strip()
        m = DATE_TEXT.match(s)
        if m:
            d, mo, y = m.groups()
            try:
                d_obj, flags = _coerce_year(date(int(y), int(mo), int(d)))
                return d_obj, ["date_parsed_from_text"] + flags
            except ValueError:
                return None, ["date_unparseable"]
        return None, ["date_unparseable"]
    return None, ["date_unparseable"]


def _coerce_year(d: date) -> tuple[date, list[str]]:
    """If year > NOMINAL_YEAR, replace with NOMINAL_YEAR and flag.
    User confirmed all 2026/2027/2028 entries are typos for 2025."""
    if d.year > NOMINAL_YEAR:
        try:
            return d.replace(year=NOMINAL_YEAR), ["date_year_coerced_to_2025"]
        except ValueError:
            return d.replace(year=NOMINAL_YEAR, day=28), ["date_year_coerced_to_2025"]
    return d, []


def split_municipality(v) -> tuple[str | None, str | None, list[str]]:
    """Returns (municipality_name, municipality_type, flags)."""
    flags: list[str] = []
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None, None, flags
    if not isinstance(v, str):
        return None, "unknown", ["municipality_unrecognised"]
    if v.strip() == "-":
        return None, None, ["municipality_was_dash_placeholder"]
    if "Private Sample" in v or v == "عينة خاصة":
        return "عينة خاصة", "خاص", []
    if v.startswith("بلدية"):
        name = v[len("بلدية"):].strip()
        return name or None, "بلدية", []
    if v.startswith("القطاع"):
        name = v[len("القطاع"):].strip()
        return name or None, "قطاع", []
    if v.startswith("قطاع"):
        name = v[len("قطاع"):].strip()
        return name or None, "قطاع", []
    return v, "unknown", ["municipality_unrecognised"]


def extract_category(v) -> tuple[str | None, str | None]:
    """Returns (category_canonical, category_en).

    Strategy: try (1) parens-after `<AR> (<EN>)`, (2) parens-before `(<EN>) <AR>`,
    (3) bilingual fallback — when the string contains both Arabic and a Latin
    run ≥ 3 chars, extract the longest Latin run as the English label.
    """
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None, None
    if not isinstance(v, str):
        return None, None
    canonical = v
    en = None
    m = ENGLISH_PARENS_AFTER.match(v)
    if m:
        en = m.group(2).strip()
    else:
        m = ENGLISH_PARENS_BEFORE.match(v)
        if m:
            en = m.group(1).strip()
    if en is None and ARABIC_CHAR_RE.search(v):
        runs = LATIN_RUN_RE.findall(v)
        if runs:
            longest = max(runs, key=len).strip(" ,/.")
            if len(longest) >= 3:
                en = longest
    return canonical, en


def classify_sample_type(category_canonical: str | None,
                         category_en: str | None,
                         buckets: list[dict]) -> str:
    """Match against bucket keywords (casefold substring) on category_canonical
    + category_en. First bucket whose any keyword hits wins. Default 'other'."""
    parts = []
    if isinstance(category_canonical, str):
        parts.append(category_canonical.casefold())
    if isinstance(category_en, str):
        parts.append(category_en.casefold())
    if not parts:
        return "other"
    blob = " | ".join(parts)
    for bucket in buckets:
        for kw in bucket["keywords"]:
            if kw.casefold() in blob:
                return bucket["id"]
    return "other"


def classify_failed_tests(failed: list[str],
                          pathogens: set[str],
                          indicators: set[str]) -> tuple[list[str], list[str], list[str]]:
    """Returns (pathogens_found, indicators_found, unknown_found)."""
    p, i, u = [], [], []
    for t in failed:
        if t in pathogens:
            p.append(t)
        elif t in indicators:
            i.append(t)
        else:
            u.append(t)
    return p, i, u


def severity_tier(failed_pathogens: list[str], failed_indicators: list[str]) -> str:
    if not failed_pathogens and not failed_indicators:
        return "none"
    distinct_pathogens = len(set(failed_pathogens))
    if distinct_pathogens >= 2:
        return "multi_pathogen"
    if distinct_pathogens == 1:
        return "pathogen"
    return "indicator_only"


def split_facility_name(v) -> tuple[str | None, str | None]:
    """Split 'chain - branch' (typical pattern). Returns (chain, branch).
    If no separator, the whole name is the chain and branch is None."""
    if not isinstance(v, str) or not v.strip():
        return None, None
    parts = FACILITY_SPLIT_RE.split(v, maxsplit=1)
    if len(parts) == 2:
        chain = parts[0].strip() or None
        branch = parts[1].strip() or None
        return chain, branch
    return v.strip() or None, None


def normalise_sample_id(v) -> str | None:
    if v is None or (isinstance(v, float) and pd.isna(v)) or not isinstance(v, str):
        return None
    s = v.strip()
    m = SAMPLE_ID_RE.match(s)
    if not m:
        return s
    prefix, digits, r, vnum = m.groups()
    return f"{prefix.lower()}-{digits}-r{vnum}"


def map_validity(v, mapping: dict) -> tuple[bool | None, str | None]:
    """Returns (boolean_or_none, flag_or_none). Flag is set when the value
    couldn't be mapped — caller should record it on the row but not abort.
    Aligns with the 2024 cleaner's flag-keep-null policy."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None, "validity_missing"
    if v in mapping:
        return mapping[v], None
    return None, "validity_unknown"


def parse_invalid_tests(raw, sentinel: str, sep: str,
                        aliases: dict, canonical: set) -> tuple[list[str], list[str]]:
    """Returns (canonical_test_list, flags)."""
    flags: list[str] = []
    if raw is None or (isinstance(raw, float) and pd.isna(raw)) or not isinstance(raw, str) or raw == sentinel:
        return [], flags
    parts = [p.strip() for p in raw.split(sep) if p and p.strip()]
    out = []
    for p in parts:
        canon = aliases.get(p, p)
        if canon not in canonical:
            flags.append(f"invalid_test_unmapped:{canon}")
        out.append(canon)
    return out, flags


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def clean_2025_with_audit(path: Path) -> tuple[pd.DataFrame, dict]:
    schema = load_schema()
    audit: dict = {
        "source_file": str(path),
        "schema_name": schema["schema_name"],
        "schema_version": schema["schema_version"],
        "rows_in_raw": 0,
        "rows_after_dropna": 0,
        "rows_out": 0,
        "drops": [],
        "changes_per_column": Counter(),
        "flags": [],
        "remaps_sample_categories": [],
        "remaps_test_aliases": Counter(),
        "warnings": [],
    }

    # Read with header=0; preserve types via dtype=object
    df = pd.read_excel(path, sheet_name=schema["workbook"]["expected_sheet_name"],
                        header=0, dtype=object)

    audit["rows_in_raw"] = len(df)

    # Rename columns to canonical names per schema
    rename_map: dict[str, str] = {}
    headers_seen = list(df.columns)
    for raw, info in zip(headers_seen, schema["raw_columns"]):
        rename_map[raw] = info["canonical"]
    df = df.rename(columns=rename_map)

    expected_canonical = [c["canonical"] for c in schema["raw_columns"]]
    if list(df.columns) != expected_canonical:
        raise SchemaValidationError(
            f"header_mismatch: got {list(df.columns)} expected {expected_canonical}"
        )

    df.insert(0, "row_excel", df.index.to_series().add(2).astype("int32"))

    # Drop fully empty rows (excluding row_excel)
    data_cols = expected_canonical
    keep_mask = df[data_cols].notna().any(axis=1)
    drops = df[~keep_mask]["row_excel"].tolist()
    for r in drops:
        audit["drops"].append({"row_excel": int(r), "reason": "all_data_columns_empty"})
    df = df[keep_mask].reset_index(drop=True)
    audit["rows_after_dropna"] = len(df)

    # 04. Parse sampling_date (with year coercion for known typos)
    parsed_dates: list[date | None] = []
    for r_excel, v in zip(df["row_excel"], df["sampling_date"]):
        d, flags = parse_sampling_date(v)
        parsed_dates.append(d)
        for fl in flags:
            audit["flags"].append({"row_excel": int(r_excel), "flag": fl,
                                   "value": str(v)[:40] if v is not None else None})
    df["sampling_date"] = parsed_dates
    audit["changes_per_column"]["sampling_date"] = sum(
        1 for f in audit["flags"] if f["flag"] == "date_parsed_from_text"
    )

    # 05. Normalise text for the str-typed columns
    text_cols = ["category_raw", "sample_name_raw", "facility_name_raw",
                 "municipality_raw", "validity_raw", "invalid_tests_raw"]
    for col in text_cols:
        before_vals = df[col].copy()
        df[col] = df[col].map(normalise_text)
        changed = sum(1 for b, a in zip(before_vals, df[col])
                      if b != a and not (b is None and a is None))
        audit["changes_per_column"][col] = changed

    # 06. Split municipality into name + type
    mun_names: list[str | None] = []
    mun_types: list[str | None] = []
    for r_excel, v in zip(df["row_excel"], df["municipality_raw"]):
        name, mtype, flags = split_municipality(v)
        mun_names.append(name)
        mun_types.append(mtype)
        for fl in flags:
            audit["flags"].append({"row_excel": int(r_excel), "flag": fl, "value": v})
    df["municipality"] = mun_names
    df["municipality_type"] = mun_types

    # 06b. Sector lookup (canonical Riyadh amanah structure from schema)
    sub_to_sector: dict[str, str] = {}
    for sec in schema["sector_taxonomy"]["sectors"]:
        for sub in sec["sub_municipalities"]:
            sub_to_sector[sub] = sec["name"]
    sector_raw_aliases: dict[str, str] = schema["sector_taxonomy"]["sector_raw_aliases"]
    sectors_out: list[str | None] = []
    for r_excel, name, mtype in zip(df["row_excel"], mun_names, mun_types):
        if mtype == "بلدية" and name:
            sec = sub_to_sector.get(name)
            if sec is None:
                audit["flags"].append({
                    "row_excel": int(r_excel),
                    "flag": "sub_municipality_unmapped_to_sector",
                    "value": name,
                })
            sectors_out.append(sec)
        elif mtype == "قطاع":
            sec = sector_raw_aliases.get(name) if name else None
            if sec is None and name:
                audit["flags"].append({
                    "row_excel": int(r_excel),
                    "flag": "sector_raw_unmapped",
                    "value": name,
                })
            sectors_out.append(sec)
        else:
            sectors_out.append(None)
    df["sector"] = sectors_out

    # 07. Category canonical + en extraction, then merge near-duplicate clusters
    cat_canonical: list[str | None] = []
    cat_en: list[str | None] = []
    merge_count = 0
    for r_excel, v in zip(df["row_excel"], df["category_raw"]):
        canon, en = extract_category(v)
        if canon in CATEGORY_CANONICAL_MERGES:
            merged = CATEGORY_CANONICAL_MERGES[canon]
            audit["flags"].append({
                "row_excel": int(r_excel),
                "flag": "category_merged_to_canonical",
                "value": f"{canon!r} → {merged!r}",
            })
            canon = merged
            merge_count += 1
            # Re-extract EN from the merged canonical for consistency
            _, en = extract_category(canon)
        cat_canonical.append(canon)
        cat_en.append(en)
    df["category_canonical"] = cat_canonical
    df["category_en"] = cat_en
    audit["changes_per_column"]["category_canonical_merged"] = merge_count

    # Track distinct category remappings (raw → canonical)
    raw_to_canon = {}
    for raw_v, canon_v in zip(df["category_raw"], df["category_canonical"]):
        if not isinstance(raw_v, str) or not isinstance(canon_v, str):
            continue
        if raw_v != canon_v:
            raw_to_canon[raw_v] = canon_v
    audit["remaps_sample_categories"] = sorted(raw_to_canon.items())

    # 08. Sample ID normalisation
    df["sample_id"] = df["sample_id_raw"].map(normalise_sample_id)
    sid_changes = sum(1 for a, b in zip(df["sample_id_raw"], df["sample_id"]) if a != b)
    audit["changes_per_column"]["sample_id"] = sid_changes

    # 09. Sample ID duplicate resolution.
    # Two cases per duplicate cluster:
    #   (a) all key fields match across rows  → true duplicate; drop the later row.
    #   (b) any key field differs              → ID collision (different physical
    #       samples that happen to share an ID). Keep both rows but suffix
    #       sample_id with -a/-b/... so downstream joins don't merge them.
    sid_counts = df["sample_id"].value_counts()
    dup_ids = sid_counts[sid_counts > 1].index.tolist()
    key_cols = ["sample_name_raw", "sampling_date", "category_canonical",
                "facility_name_raw", "municipality", "validity_raw", "invalid_tests_raw"]
    rows_to_drop: list[int] = []
    sid_overrides: dict[int, str] = {}    # df-index → new sample_id
    for sid in dup_ids:
        rows = df[df["sample_id"] == sid].sort_values("row_excel")
        idx = rows.index.tolist()
        diffs = [c for c in key_cols if rows[c].astype(str).nunique() > 1]
        if not diffs:
            for i in idx[1:]:
                rows_to_drop.append(i)
                audit["flags"].append({
                    "row_excel": int(df.at[i, "row_excel"]),
                    "flag": "sample_id_duplicate_dropped",
                    "value": sid,
                })
        else:
            for j, i in enumerate(idx):
                suffix = chr(ord("a") + j)
                new_sid = f"{sid}-{suffix}"
                sid_overrides[i] = new_sid
                audit["flags"].append({
                    "row_excel": int(df.at[i, "row_excel"]),
                    "flag": "sample_id_collision",
                    "value": f"{sid} → {new_sid} (differs in: {','.join(diffs)})",
                })
    if sid_overrides:
        for i, new_sid in sid_overrides.items():
            df.at[i, "sample_id"] = new_sid
    if rows_to_drop:
        df = df.drop(index=rows_to_drop).reset_index(drop=True)

    # 10. Validity mapping → boolean (FAIL on unknown)
    vmap = schema["validity_mapping"]
    vmap_clean = {k: v for k, v in vmap.items() if k != "on_unknown"}
    is_valid_list: list[bool | None] = []
    for r_excel, v in zip(df["row_excel"], df["validity_raw"]):
        bool_val, flag = map_validity(v, vmap_clean)
        is_valid_list.append(bool_val)
        if flag is not None:
            audit["flags"].append({"row_excel": int(r_excel), "flag": flag, "value": v})
    df["is_valid"] = is_valid_list

    # 11. Invalid tests parsing
    sentinel = schema["invalid_tests_handling"]["no_failure_sentinel"]
    sep = schema["invalid_tests_handling"]["separator"]
    aliases = schema["invalid_tests_handling"]["test_name_aliases"]
    canonical_set = set(schema["invalid_tests_handling"]["canonical_test_names"])
    invalid_tests_lists: list[list[str]] = []
    for r_excel, raw in zip(df["row_excel"], df["invalid_tests_raw"]):
        canon_list, flags = parse_invalid_tests(raw, sentinel, sep, aliases, canonical_set)
        invalid_tests_lists.append(canon_list)
        for fl in flags:
            audit["flags"].append({"row_excel": int(r_excel), "flag": fl, "value": raw})
        # Track remapping counts
        if raw and raw != sentinel:
            for p in [x.strip() for x in raw.split(sep) if x.strip()]:
                if p in aliases:
                    audit["remaps_test_aliases"][f"{p} → {aliases[p]}"] += 1
    df["invalid_tests"] = invalid_tests_lists

    # 12. n_failed_tests + is_failure composite
    # is_failure is the decision-maker-grade "this sample had a problem" signal.
    # It captures EITHER signal: the validity column says invalid, OR the
    # invalid_tests column lists failed tests. This stops the 9 inconsistent
    # rows (where is_valid disagrees with invalid_tests) from skewing rates
    # depending on which column the consumer happens to read.
    df["n_failed_tests"] = [len(x) for x in invalid_tests_lists]
    # is_failure: True if EITHER lab marked invalid OR at least one failed test
    # was listed. When validity was unparseable (v is None) and no tests are
    # listed, is_failure is also None (unknown), not False.
    df["is_failure"] = [
        None if (v is None and n == 0) else ((v is False) or (n > 0))
        for v, n in zip(df["is_valid"], df["n_failed_tests"])
    ]

    # 13. Facility chain/branch split
    chains: list[str | None] = []
    branches: list[str | None] = []
    for v in df["facility_name_raw"]:
        c, b = split_facility_name(v)
        chains.append(c)
        branches.append(b)
    df["facility_chain"] = chains
    df["facility_branch"] = branches

    # 14. Sample-type rollup (config-driven, YAML)
    buckets = schema["sample_type_buckets"]
    df["sample_type"] = [
        classify_sample_type(cc, ce, buckets)
        for cc, ce in zip(df["category_canonical"], df["category_en"])
    ]

    # 15. Pathogen / indicator classification + severity tier
    pathogen_set = set(schema["test_classification"]["pathogen"])
    indicator_set = set(schema["test_classification"]["indicator"])
    failed_pathogens_col: list[list[str]] = []
    failed_indicators_col: list[list[str]] = []
    severity_col: list[str] = []
    has_pathogen_col: list[bool] = []
    for r_excel, failed in zip(df["row_excel"], df["invalid_tests"]):
        ps, idx, unknown = classify_failed_tests(failed, pathogen_set, indicator_set)
        failed_pathogens_col.append(ps)
        failed_indicators_col.append(idx)
        severity_col.append(severity_tier(ps, idx))
        has_pathogen_col.append(bool(ps))
        for t in unknown:
            audit["flags"].append({
                "row_excel": int(r_excel),
                "flag": "test_unclassified",
                "value": t,
            })
    df["failed_pathogens"] = failed_pathogens_col
    df["failed_indicators"] = failed_indicators_col
    df["severity_tier"] = severity_col
    df["has_pathogen_failure"] = has_pathogen_col

    # Post-enrichment validation. Flag rows that need human review but don't
    # auto-fix — the cleaner's policy is flag-and-keep.
    for r_excel, valid, n_failed in zip(df["row_excel"], df["is_valid"], df["n_failed_tests"]):
        if valid is True and n_failed > 0:
            audit["flags"].append({
                "row_excel": int(r_excel),
                "flag": "validity_says_valid_but_has_failures",
                "value": f"is_valid=true, n_failed_tests={n_failed}",
            })
        elif valid is False and n_failed == 0:
            audit["flags"].append({
                "row_excel": int(r_excel),
                "flag": "validity_says_invalid_but_no_failures",
                "value": "is_valid=false, n_failed_tests=0",
            })
    for r_excel, st, cat in zip(df["row_excel"], df["sample_type"], df["category_canonical"]):
        if st == "other":
            audit["flags"].append({
                "row_excel": int(r_excel),
                "flag": "sample_type_unbucketed",
                "value": cat if isinstance(cat, str) else None,
            })

    # ---- Build final output frame ----
    # Coerce sampling_date to datetime64[ns] with NaT for missing — avoids
    # mixed object dtype that breaks date comparisons / min / max.
    sampling_date_series = pd.to_datetime(df["sampling_date"], errors="coerce")

    # Derived time dimensions for dashboards. Computed on the cleaned series so
    # NaT propagates as NA in each derived column.
    sd = sampling_date_series
    year_month = sd.dt.strftime("%Y-%m")
    iso_year_week = sd.dt.strftime("%G-W%V")     # ISO year + ISO week
    quarter = sd.dt.quarter.astype("Int8")
    day_of_week = sd.dt.dayofweek.astype("Int8")  # Mon=0, Sun=6

    out = pd.DataFrame({
        "source_file": path.name,
        "row_excel": df["row_excel"].astype("int32"),
        "sampling_date": sampling_date_series,
        "year_month": year_month.astype("string"),
        "iso_year_week": iso_year_week.astype("string"),
        "quarter": quarter,
        "day_of_week": day_of_week,
        "sample_id": df["sample_id"].astype("string"),
        "sample_id_raw": df["sample_id_raw"].astype("string"),
        "sample_name": df["sample_name_raw"].astype("string"),
        "category_canonical": df["category_canonical"].astype("string"),
        "category_en": df["category_en"].astype("string"),
        "category_raw": df["category_raw"].astype("string"),
        "sample_type": pd.Series(df["sample_type"], dtype="string"),
        "facility_name": df["facility_name_raw"].astype("string"),
        "facility_chain": pd.Series(df["facility_chain"], dtype="string"),
        "facility_branch": pd.Series(df["facility_branch"], dtype="string"),
        "facility_name_raw": df["facility_name_raw"].astype("string"),
        "municipality": pd.Series(df["municipality"], dtype="string"),
        "municipality_type": pd.Series(df["municipality_type"], dtype="string"),
        "municipality_raw": df["municipality_raw"].astype("string"),
        "sector": pd.Series(df["sector"], dtype="string"),
        "is_valid": pd.array(df["is_valid"].tolist(), dtype="boolean"),
        "is_failure": pd.array(df["is_failure"].tolist(), dtype="boolean"),
        "invalid_tests_raw": df["invalid_tests_raw"].astype("string"),
        "invalid_tests": df["invalid_tests"],
        "n_failed_tests": df["n_failed_tests"].astype("int32"),
        "failed_pathogens": df["failed_pathogens"],
        "failed_indicators": df["failed_indicators"],
        "has_pathogen_failure": pd.array(df["has_pathogen_failure"].tolist(), dtype="boolean"),
        "severity_tier": pd.Series(df["severity_tier"], dtype="string"),
    })

    # data_quality_flags
    flags_per_row: dict[int, list[str]] = defaultdict(list)
    for f in audit["flags"]:
        flags_per_row[int(f["row_excel"])].append(f["flag"])
    out["data_quality_flags"] = pd.array(
        ["|".join(sorted(set(flags_per_row.get(int(r), [])))) or None for r in out["row_excel"]],
        dtype="string",
    )

    # 16. Repeat-offender rolling-window flag (chain-level).
    # For each row, count invalid samples at the same facility_chain in the
    # trailing window ending on this sample's date (inclusive of this row).
    ro_cfg = schema["repeat_offender_rules"]
    window_days = int(ro_cfg["window_days"])
    threshold = int(ro_cfg["invalid_threshold"])
    out = out.sort_values(by=["facility_chain", "sampling_date"], kind="mergesort",
                          na_position="last").reset_index(drop=True)
    counts = [0] * len(out)
    chains_arr = out["facility_chain"].tolist()
    dates_arr = out["sampling_date"].tolist()
    invalid_arr = [bool(v) if pd.notna(v) else False for v in out["is_failure"].tolist()]
    for i in range(len(out)):
        chain_i = chains_arr[i]
        date_i = dates_arr[i]
        if chain_i is None or pd.isna(chain_i) or pd.isna(date_i):
            continue
        cutoff = date_i - pd.Timedelta(days=window_days)
        c = 0
        for j in range(i, -1, -1):
            if chains_arr[j] != chain_i:
                continue
            d_j = dates_arr[j]
            if pd.isna(d_j) or d_j < cutoff:
                if d_j is not None and not pd.isna(d_j) and d_j < cutoff:
                    break
                continue
            if invalid_arr[j]:
                c += 1
        counts[i] = c
    out["chain_invalid_count_90d"] = pd.array(counts, dtype="int32")
    out["is_repeat_offender_90d"] = pd.array(
        [c >= threshold for c in counts], dtype="boolean"
    )

    # 17. Deterministic sort for output
    out = out.sort_values(by=["sampling_date", "sample_id"], kind="mergesort",
                          na_position="last", ignore_index=True)

    audit["rows_out"] = len(out)
    return out, audit


def clean_2025(path: Path) -> pd.DataFrame:
    df, _ = clean_2025_with_audit(Path(path))
    return df


# ---------------------------------------------------------------------------
# Diff report
# ---------------------------------------------------------------------------
def write_diff_report(audit: dict, df: pd.DataFrame, out_path: Path) -> None:
    lines: list[str] = []
    lines.append(f"# Cleaning diff report: {Path(audit['source_file']).name}\n")
    lines.append(f"- **Schema:** `{audit['schema_name']}` v{audit['schema_version']}")
    lines.append(f"- **Rows in (raw, below header):** {audit['rows_in_raw']}")
    lines.append(f"- **Rows after empty-row drop:** {audit['rows_after_dropna']}")
    lines.append(f"- **Rows out (canonical):** {audit['rows_out']}")
    lines.append(f"- **Rows dropped:** {len(audit['drops'])}")
    lines.append(f"- **Flags raised (total):** {len(audit['flags'])}")
    lines.append("")

    lines.append("## Cells changed per column")
    lines.append("")
    lines.append("| column | changed |")
    lines.append("|---|---:|")
    for col, n in sorted(audit["changes_per_column"].items(), key=lambda kv: -kv[1]):
        lines.append(f"| `{col}` | {n} |")
    lines.append("")

    lines.append("## Flags raised (per flag)")
    lines.append("")
    flag_counts: Counter = Counter(f["flag"] for f in audit["flags"])
    if flag_counts:
        lines.append("| flag | count | sample value |")
        lines.append("|---|---:|---|")
        for flag, n in flag_counts.most_common():
            sample = next((f["value"] for f in audit["flags"] if f["flag"] == flag), "")
            sample_repr = repr(sample) if sample is not None else ""
            sample_repr = sample_repr[:80].replace("|", "\\|")
            lines.append(f"| `{flag}` | {n} | {sample_repr} |")
    else:
        lines.append("_no flags_")
    lines.append("")

    lines.append("## Sample-Category remappings (raw → canonical)")
    lines.append("")
    if audit["remaps_sample_categories"]:
        lines.append("| raw | → | canonical |")
        lines.append("|---|---|---|")
        for raw, canon in audit["remaps_sample_categories"][:200]:
            lines.append(f"| `{repr(raw)[:80].replace('|','\\|')}` | → | `{repr(canon)[:80].replace('|','\\|')}` |")
        if len(audit["remaps_sample_categories"]) > 200:
            lines.append(f"\n_… +{len(audit['remaps_sample_categories'])-200} more_")
    else:
        lines.append("_none_")
    lines.append("")

    lines.append("## Test-name alias remappings (count)")
    lines.append("")
    if audit["remaps_test_aliases"]:
        lines.append("| alias → canonical | count |")
        lines.append("|---|---:|")
        for k, v in audit["remaps_test_aliases"].most_common():
            lines.append(f"| {k} | {v} |")
    else:
        lines.append("_none_")
    lines.append("")

    lines.append("## Output column summary")
    lines.append("")
    lines.append("| column | dtype | non-null | nulls | unique |")
    lines.append("|---|---|---:|---:|---:|")
    for col in df.columns:
        s = df[col]
        try:
            uniq = s.nunique(dropna=True)
        except TypeError:
            uniq = "n/a"
        lines.append(f"| `{col}` | `{s.dtype}` | {int(s.notna().sum())} | {int(s.isna().sum())} | {uniq} |")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Review report — surfaces edge cases needing human review.
# Distinct from the diff report, which logs what the cleaner did. The review
# report tells the user *what to look at next* and how to resolve.
# ---------------------------------------------------------------------------
REVIEW_SECTIONS = [
    {
        "flag": "validity_says_valid_but_has_failures",
        "title": "Source-data conflict: marked VALID but has failed tests",
        "resolution": "Open the source xlsx at the row, decide which field is correct (validity column or invalid-tests column), and patch the source. The cleaner won't auto-pick a winner.",
    },
    {
        "flag": "validity_says_invalid_but_no_failures",
        "title": "Source-data conflict: marked INVALID but no failed tests listed",
        "resolution": "Same as above — manual reconciliation against the source xlsx.",
    },
    {
        "flag": "sample_type_unbucketed",
        "title": "Categories not yet covered by sample_type_buckets (sample_type='other')",
        "resolution": "Add the category's distinguishing keyword(s) to the right bucket in `schemas/lab_data_2025_v1.yaml` → `sample_type_buckets`. Re-run the cleaner.",
    },
    {
        "flag": "test_unclassified",
        "title": "Failed tests not classified as pathogen or indicator",
        "resolution": "Add the test name to `schemas/lab_data_2025_v1.yaml` → `test_classification.pathogen` or `.indicator`.",
    },
    {
        "flag": "municipality_unrecognised",
        "title": "Municipality values that didn't match any split rule",
        "resolution": "Add a rule in `schemas/lab_data_2025_v1.yaml` → `municipality_typing.rules`.",
    },
    {
        "flag": "invalid_test_unmapped",
        "title": "Failed tests not in the canonical test-name list",
        "resolution": "Add the spelling to `schemas/lab_data_2025_v1.yaml` → `invalid_tests_handling.test_name_aliases` or `.canonical_test_names`.",
    },
    {
        "flag": "sample_id_collision",
        "title": "Sample IDs reused for different physical samples (suffixed -a/-b/...)",
        "resolution": "These are kept with disambiguating suffixes. If an ID was reused at the lab, no fix needed — the suffix handles it. If a true bug, fix at source.",
    },
]


def write_review_report(audit: dict, df: pd.DataFrame, out_path: Path) -> None:
    lines: list[str] = []
    src_name = Path(audit['source_file']).name
    lines.append(f"# Review report: {src_name}\n")
    lines.append("This report surfaces edge cases the cleaner flagged but did NOT auto-fix.")
    lines.append("Resolve each section by editing the source xlsx or extending the YAML schema.\n")

    flag_to_rows: dict[str, list[dict]] = defaultdict(list)
    for f in audit["flags"]:
        flag_to_rows[f["flag"]].append(f)

    # Summary at top
    lines.append("## Summary\n")
    lines.append("| issue | count | resolution path |")
    lines.append("|---|---:|---|")
    total_review_items = 0
    for sec in REVIEW_SECTIONS:
        n = len(flag_to_rows.get(sec["flag"], []))
        total_review_items += n
        lines.append(f"| {sec['title']} | {n} | {sec['flag']} |")
    lines.append(f"\n**Total review items:** {total_review_items}\n")

    # Lookup table: row_excel → row dict for context
    df_idx = {int(r): df[df['row_excel'] == r].iloc[0].to_dict()
              for r in df['row_excel'].unique()}

    for sec in REVIEW_SECTIONS:
        rows = flag_to_rows.get(sec["flag"], [])
        if not rows:
            continue
        lines.append(f"## {sec['title']}\n")
        lines.append(f"_Count: {len(rows)}_  ·  _Flag: `{sec['flag']}`_\n")
        lines.append(f"**How to resolve:** {sec['resolution']}\n")

        if sec["flag"] in ("sample_type_unbucketed", "test_unclassified",
                            "municipality_unrecognised", "invalid_test_unmapped"):
            # Aggregate by value (which category / test / municipality is recurring)
            agg: Counter = Counter()
            for r in rows:
                v = r.get("value")
                if v is not None:
                    agg[str(v)] += 1
            lines.append("| value | count |")
            lines.append("|---|---:|")
            for v, n in agg.most_common(50):
                vr = repr(v).replace("|", "\\|")
                lines.append(f"| {vr[:120]} | {n} |")
            if len(agg) > 50:
                lines.append(f"\n_…+{len(agg)-50} more distinct values_")
        else:
            # Per-row listing with full context
            lines.append("| row_excel | sample_id | sampling_date | facility_chain | category_canonical | is_valid | n_failed_tests | invalid_tests |")
            lines.append("|---:|---|---|---|---|---|---:|---|")
            for r in rows[:200]:
                ctx = df_idx.get(int(r["row_excel"]), {})
                inv_tests = ctx.get('invalid_tests', [])
                inv_tests_str = ", ".join(inv_tests) if inv_tests else ""
                fields = [
                    str(r["row_excel"]),
                    str(ctx.get('sample_id', '')),
                    str(ctx.get('sampling_date', ''))[:10],
                    str(ctx.get('facility_chain', '') or '')[:40],
                    str(ctx.get('category_canonical', '') or '')[:50],
                    str(ctx.get('is_valid', '')),
                    str(ctx.get('n_failed_tests', '')),
                    inv_tests_str[:60],
                ]
                fields = [f.replace("|", "\\|") for f in fields]
                lines.append("| " + " | ".join(fields) + " |")
            if len(rows) > 200:
                lines.append(f"\n_…+{len(rows)-200} more rows_")
        lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    if len(sys.argv) not in (4, 5):
        print("Usage: python clean_2025.py <input.xlsx> <output.parquet> <diff.md> [<review.md>]",
              file=sys.stderr)
        sys.exit(2)
    in_path = Path(sys.argv[1]).resolve()
    parquet_path = Path(sys.argv[2]).resolve()
    diff_path = Path(sys.argv[3]).resolve()
    review_path = Path(sys.argv[4]).resolve() if len(sys.argv) == 5 else (
        diff_path.parent / diff_path.name.replace("_diff.md", "_review.md")
    )

    df, audit = clean_2025_with_audit(in_path)
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(parquet_path, compression="zstd", index=False)
    write_diff_report(audit, df, diff_path)
    write_review_report(audit, df, review_path)

    print(f"wrote {parquet_path} ({len(df)} rows × {df.shape[1]} cols)")
    print(f"wrote {diff_path}")
    print(f"wrote {review_path}")
    print(f"flags: {len(audit['flags'])}, drops: {len(audit['drops'])}")


if __name__ == "__main__":
    main()
