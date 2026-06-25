"""Enrichment layer for a year's wide parquet — adds the 6 columns that
data2025.parquet has but the year's wide parquet doesn't:

    failed_pathogens, failed_indicators, has_pathogen_failure,
    severity_tier, chain_invalid_count_90d, is_repeat_offender_90d

Reads classification taxonomies + repeat-offender rules from the 2025 YAML
(shared across years). Reads facility_name for chain/branch split.

Run:
    .venv/bin/python scripts/enrich_2024.py              # default year=2024
    .venv/bin/python scripts/enrich_2024.py --year 2023  # 2023
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_2025 = ROOT / "schemas" / "lab_data_2025_v1.yaml"

FACILITY_SPLIT_RE = re.compile(r"\s+[-–—]\s*|\s*[-–—]\s+")


def load_2025_schema() -> dict:
    with SCHEMA_2025.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def split_facility_name(v):
    if not isinstance(v, str) or not v.strip():
        return None, None
    parts = FACILITY_SPLIT_RE.split(v, maxsplit=1)
    if len(parts) == 2:
        return (parts[0].strip() or None), (parts[1].strip() or None)
    return v.strip() or None, None


def classify_failed(failed: list[str], pathogens: set[str], indicators: set[str]):
    p, i, u = [], [], []
    for t in failed or []:
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
    distinct = len(set(failed_pathogens))
    if distinct >= 2:
        return "multi_pathogen"
    if distinct == 1:
        return "pathogen"
    return "indicator_only"


def compute_repeat_offender(df: pd.DataFrame, window_days: int, threshold: int) -> tuple[list[int], list[bool]]:
    """Per row: count failures at the same facility_chain in the trailing
    window ending on this row's date (inclusive). Returns (counts, flags)."""
    df_sorted = df.sort_values(["facility_chain", "sampling_date"], kind="mergesort", na_position="last")
    # Normalise NA → None so equality comparisons stay boolean.
    chains = [None if (c is None or pd.isna(c)) else c for c in df_sorted["facility_chain"].tolist()]
    dates = df_sorted["sampling_date"].tolist()
    is_fail = [bool(v) if pd.notna(v) else False for v in df_sorted["is_failure"].tolist()]
    counts_sorted = [0] * len(df_sorted)
    for i in range(len(df_sorted)):
        chain_i = chains[i]
        date_i = dates[i]
        if chain_i is None or pd.isna(date_i):
            continue
        cutoff = date_i - pd.Timedelta(days=window_days)
        c = 0
        for j in range(i, -1, -1):
            if chains[j] != chain_i:
                continue
            d_j = dates[j]
            if pd.isna(d_j):
                continue
            if d_j < cutoff:
                break
            if is_fail[j]:
                c += 1
        counts_sorted[i] = c
    flags_sorted = [c >= threshold for c in counts_sorted]
    # Re-align to the original index.
    out_counts = pd.Series(counts_sorted, index=df_sorted.index).reindex(df.index).fillna(0).astype(int).tolist()
    out_flags = pd.Series(flags_sorted, index=df_sorted.index).reindex(df.index).fillna(False).astype(bool).tolist()
    return out_counts, out_flags


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2024)
    args = ap.parse_args()
    wide_path = ROOT / "cleaned" / f"data{args.year}.parquet"
    if not wide_path.exists():
        print(f"missing {wide_path}", file=sys.stderr)
        return 2

    schema = load_2025_schema()
    pathogen_set = set(schema["test_classification"]["pathogen"])
    indicator_set = set(schema["test_classification"]["indicator"])
    ro = schema["repeat_offender_rules"]
    window_days = int(ro["window_days"])
    threshold = int(ro["invalid_threshold"])

    df = pd.read_parquet(wide_path)
    print(f"loaded {wide_path}: {df.shape}")

    # 1. Facility chain/branch split (will be null for 2024 — source has no facility data).
    chains, branches = [], []
    for v in df["facility_name"]:
        c, b = split_facility_name(v if isinstance(v, str) else None)
        chains.append(c)
        branches.append(b)
    df["facility_chain"] = pd.array(chains, dtype="string")
    df["facility_branch"] = pd.array(branches, dtype="string")

    # 2. Pathogen / indicator / severity classification.
    failed_pathogens_col: list[list[str]] = []
    failed_indicators_col: list[list[str]] = []
    severity_col: list[str] = []
    has_pathogen_col: list[bool] = []
    unclassified_count = 0
    unclassified_examples: dict[str, int] = {}
    for failed in df["invalid_tests"]:
        ps, idx, unknown = classify_failed(list(failed) if failed is not None else [],
                                            pathogen_set, indicator_set)
        failed_pathogens_col.append(ps)
        failed_indicators_col.append(idx)
        severity_col.append(severity_tier(ps, idx))
        has_pathogen_col.append(bool(ps))
        for t in unknown:
            unclassified_count += 1
            unclassified_examples[t] = unclassified_examples.get(t, 0) + 1
    df["failed_pathogens"] = failed_pathogens_col
    df["failed_indicators"] = failed_indicators_col
    df["severity_tier"] = pd.Series(severity_col, dtype="string")
    df["has_pathogen_failure"] = pd.array(has_pathogen_col, dtype="boolean")

    # 3. Repeat-offender rolling window (90-day, chain-level, threshold ≥ 2).
    counts, flags = compute_repeat_offender(df, window_days, threshold)
    df["chain_invalid_count_90d"] = pd.array(counts, dtype="int32")
    df["is_repeat_offender_90d"] = pd.array(flags, dtype="boolean")

    # 3b. Sector column — null for 2024 (source has no municipality data).
    # Kept for schema parity with 2025 so the two parquets stack cleanly.
    df["sector"] = pd.array([None] * len(df), dtype="string")

    # 4. Write back, preserving the same path.
    df.to_parquet(wide_path, compression="zstd", index=False)
    print(f"wrote {wide_path}: {df.shape}")

    # ----- Summary -----
    print("\n--- Enrichment summary ---")
    print(f"  has_pathogen_failure=True: {int(df['has_pathogen_failure'].sum())} / {len(df)}")
    print(f"  severity_tier distribution:")
    print(df["severity_tier"].value_counts(dropna=False).to_string())
    print(f"  is_repeat_offender_90d=True: {int(df['is_repeat_offender_90d'].sum())} / {len(df)}")
    facility_known = df["facility_chain"].notna().sum()
    print(f"  facility_chain non-null: {int(facility_known)} / {len(df)}  "
          f"(repeat-offender flag is meaningless when this is 0)")
    if unclassified_count:
        print(f"\n  ⚠ {unclassified_count} failed-test occurrences could not be classified:")
        for t, n in sorted(unclassified_examples.items(), key=lambda kv: -kv[1])[:10]:
            print(f"    {t!r}: {n}")
        print("  → add these to schemas/lab_data_2025_v1.yaml → test_classification.{pathogen|indicator}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
