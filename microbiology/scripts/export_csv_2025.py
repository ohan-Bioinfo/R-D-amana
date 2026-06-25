"""Export the enriched 2025 parquet to CSVs under 2025/.

Writes:
  2025/data2025_full.csv         — all 11,564 rows, sorted by sampling_date then sample_id
  2025/by_month/2025-MM.csv      — one CSV per year_month, sorted within
  2025/non_compliant_only.csv    — convenience subset (is_failure==True)

CSVs use utf-8-sig (BOM) so Arabic text opens correctly in Excel.
List columns (invalid_tests, failed_pathogens, failed_indicators) are
serialized as pipe-separated strings.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PARQUET = ROOT / "cleaned" / "data2025.parquet"
OUT_ROOT = ROOT / "2025"


def serialize_lists(df: pd.DataFrame) -> pd.DataFrame:
    """Convert list-typed columns into pipe-separated strings."""
    out = df.copy()
    for col in ["invalid_tests", "failed_pathogens", "failed_indicators"]:
        if col in out.columns:
            out[col] = out[col].apply(
                lambda lst: " | ".join(lst) if lst is not None and len(lst) > 0 else ""
            )
    return out


def main() -> None:
    df = pd.read_parquet(PARQUET)

    # Deterministic sort: by date, then sample_id
    df = df.sort_values(by=["sampling_date", "sample_id"], na_position="last")
    df = serialize_lists(df)

    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    by_month_dir = OUT_ROOT / "by_month"
    by_month_dir.mkdir(parents=True, exist_ok=True)

    # Master file
    full_path = OUT_ROOT / "data2025_full.csv"
    df.to_csv(full_path, index=False, encoding="utf-8-sig")
    print(f"wrote {full_path.relative_to(ROOT)}  ({len(df)} rows × {df.shape[1]} cols)")

    # Per-month split
    months = sorted(df["year_month"].dropna().unique().tolist())
    for m in months:
        sub = df[df["year_month"] == m]
        out = by_month_dir / f"{m}.csv"
        sub.to_csv(out, index=False, encoding="utf-8-sig")
        print(f"wrote {out.relative_to(ROOT)}  ({len(sub)} rows)")

    # Convenience subset
    nc = df[df["is_failure"] == True]
    nc_path = OUT_ROOT / "non_compliant_only.csv"
    nc.to_csv(nc_path, index=False, encoding="utf-8-sig")
    print(f"wrote {nc_path.relative_to(ROOT)}  ({len(nc)} rows)")


if __name__ == "__main__":
    main()
