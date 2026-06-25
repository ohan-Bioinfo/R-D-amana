"""Apply user's canonical category mapping to chemistry 2025 parquets.

Rules (all confirmed by user 2026-06-11):
  1. Section-aware overrides — 19 explicit user mappings from column B of
     chemistry_categories_by_section.xlsx take priority.
  2. Manual global mapping for known incomplete variants (e.g. "Fruit and
     Vegetables" missing its Arabic half).
  3. Otherwise: auto-strip the English half, keep only the Arabic portion.
  4. Junk values (NA, 11 عينة, 18 عينة, 20 عينة, 3 عينات, dISCARD) → drop the row.

Output:
  - Adds new column `sample_category_canonical` to each chem_*_2025.parquet
  - Original `sample_category` is preserved (rollback-safe)
  - Junk rows are dropped from the parquet entirely
  - Prints before/after row counts and the canonical vocabulary

Run:
    .venv/bin/python clean/scripts/apply_category_canonical.py
"""
from __future__ import annotations

import re
from pathlib import Path
import pandas as pd

CLEAN = Path(__file__).resolve().parent.parent
CHEM = CLEAN / "chemistry"

# 1. SECTION-AWARE OVERRIDES (from user's column B fills, 19 entries)
OVERRIDES: dict[tuple[str, str], str] = {
    # aflatoxins_2025: 3 fills
    ("aflatoxins_2025", "Cereal and Legume products الحبوب والبقوليات\""): "الحبوب والبقوليات",
    ("aflatoxins_2025", "الحبوب والبقوليات\""): "الحبوب والبقوليات",
    ("aflatoxins_2025", "Cereal and Legume products"): "الحبوب والبقوليات",
    # food_chemistry_2025: 3 fills
    ("food_chemistry_2025", "Cereal and Legume products الحبوب والبقوليات\""): "الحبوب والبقوليات",
    ("food_chemistry_2025", "Ready to Eat Foods الأطعمة الجاهزه للاكل"): "الأطعمة الجاهزه للاكل",
    ("food_chemistry_2025", '"Ready to Eat Foods الأطعمة الجاهزه للاكل"'): "الأطعمة الجاهزه للاكل",
    # heavy_metals_2025: 5 fills
    ("heavy_metals_2025", "Tap water مياه الحنفية"): "مياه الحنفية",
    ("heavy_metals_2025", "المياه الغير المعبأة (Unbottled water)"): "مياه الحنفية",
    ("heavy_metals_2025", "المياه المعبأة (bot water)"): "مياه شرب",
    ("heavy_metals_2025", "مياه شرب"): "مياه شرب",
    ("heavy_metals_2025", "مياه فلتر لغسيل الأدوات"): "مياه الحنفية",
    # water_analysis_2025: 8 fills (fully reviewed)
    ("water_analysis_2025", "مياه الحنفية"): "مياه الحنفية",
    ("water_analysis_2025", "مياة حنفية غسيل الادوات"): "مياه الحنفية",
    ("water_analysis_2025", "مياه متحركة"): "عينات خاصه",
    ("water_analysis_2025", "المياه الغير المعبأة (Unbottled water)"): "مياه الحنفية",
    ("water_analysis_2025", "المياه المعبأة (bot water)"): "مياه شرب",
    ("water_analysis_2025", "Meat and Poultry products اللحوم والدواجن"): "مياه الحنفية",
    ("water_analysis_2025", "Drinking water مياه الشرب"): "مياه شرب",
    ("water_analysis_2025", "مياه شرب"): "مياه شرب",
}

# 2. MANUAL GLOBAL — for variants that the auto-strip would fail
MANUAL_GLOBAL: dict[str, str] = {
    "Fruit and Vegetables": "الفواكه والخضار",  # missing Arabic half (1 row in pesticides_2025)
}

# 3. DISCARD set — rows with these category values are removed entirely
DISCARD: set[str] = {
    "Tap water مياه الحنفية dISCARD",
    "NA",
    "11 عينة",
    "18 عينة",
    "20 عينة",
    "3 عينات",
}

# 4. SECTION DEFAULTS for NULL category — applied when sample_category is null
# (user-confirmed: water-analysis NULLs are all water samples by sample_name evidence;
# other sections default to the section's dominant canonical category).
NULL_DEFAULT_BY_SECTION: dict[str, str] = {
    "water_analysis_2025":       "مياه الحنفية",
    "aflatoxins_2025":           "الحبوب والبقوليات",
    "heavy_metals_2025":         "اللحوم والدواجن",
    "pesticides_2025":           "الفواكه والخضار",
}

# 5. FORCE_ALL_TO — for sections where ALL samples should collapse into one
# canonical regardless of the raw sample_category text. (No section uses
# this currently — left as the hook for future overrides.)
FORCE_ALL_TO: dict[str, str] = {}

# Arabic-character segment regex (for auto-strip fallback)
_ARABIC_SEG = re.compile(r"[؀-ۿ][؀-ۿ\s]*")


def auto_strip_arabic(s: str) -> str:
    """Return the longest contiguous Arabic-character run from s (no English)."""
    s = str(s).strip().strip('"').strip("'")
    segments = _ARABIC_SEG.findall(s)
    if not segments:
        return s
    return max(segments, key=len).strip()


def canonical_for(section_year: str, raw):
    """Return canonical category, or '__DISCARD__' if the row should be dropped.
    NULL raw is mapped to the section's default (if defined) — keeps the
    user's rule that water-section NULLs are مياه الحنفية, etc.
    FORCE_ALL_TO trumps everything: aflatoxin samples collapse to one bucket."""
    # FORCE rule applies regardless of raw value
    if section_year in FORCE_ALL_TO:
        # But still discard junk rows (NA, count-in-wrong-column)
        if raw is not None and not (isinstance(raw, float) and pd.isna(raw)):
            if str(raw).strip() in DISCARD:
                return "__DISCARD__"
        return FORCE_ALL_TO[section_year]
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        # NULL raw → fall back to section default if available
        return NULL_DEFAULT_BY_SECTION.get(section_year)
    raw_str = str(raw).strip()
    if not raw_str:
        return NULL_DEFAULT_BY_SECTION.get(section_year)
    if raw_str in DISCARD:
        return "__DISCARD__"
    if (section_year, raw_str) in OVERRIDES:
        return OVERRIDES[(section_year, raw_str)]
    if raw_str in MANUAL_GLOBAL:
        return MANUAL_GLOBAL[raw_str]
    return auto_strip_arabic(raw_str)


def main():
    print("=" * 90)
    print("APPLYING CANONICAL CATEGORY MAPPING TO CHEMISTRY 2025 PARQUETS")
    print("=" * 90)
    print(f"Section-aware overrides: {len(OVERRIDES)} entries")
    print(f"Manual global mappings:  {len(MANUAL_GLOBAL)} entries")
    print(f"Discard list:            {len(DISCARD)} values\n")

    sections_2025 = [
        "aflatoxins_2025", "food_chemistry_2025", "heavy_metals_2025",
        "honey_2025", "hormones_antibiotics_2025",
        "pesticides_2025", "water_analysis_2025",
    ]
    print(f'{"section":<30}  {"rows before":>11}  {"rows after":>10}  {"dropped":>7}  {"distinct canonical":>18}')
    print("-" * 90)

    all_canonicals = set()
    for sy in sections_2025:
        p = CHEM / f"chem_{sy}.parquet"
        if not p.exists():
            continue
        df = pd.read_parquet(p)
        before = len(df)

        # Compute canonical
        df["sample_category_canonical"] = df["sample_category"].apply(
            lambda r: canonical_for(sy, r)
        )
        # Catch the literal '<NA>' string that the pandas Nullable String dtype
        # sometimes round-trips through parquet — re-apply the section default.
        default_cat = NULL_DEFAULT_BY_SECTION.get(sy)
        if default_cat is not None:
            df.loc[df["sample_category_canonical"].astype(str) == "<NA>",
                   "sample_category_canonical"] = default_cat

        # Drop discarded rows
        discarded_mask = df["sample_category_canonical"] == "__DISCARD__"
        n_dropped = int(discarded_mask.sum())
        df = df.loc[~discarded_mask].copy()

        # Track canonical vocabulary
        for v in df["sample_category_canonical"].dropna().unique():
            all_canonicals.add(str(v))

        # Save back
        df.to_parquet(p, compression="zstd", index=False)

        after = len(df)
        distinct = df["sample_category_canonical"].dropna().nunique()
        print(f"{sy:<30}  {before:>11,}  {after:>10,}  {n_dropped:>7}  {distinct:>18}")

    print()
    print("=" * 90)
    print(f"CANONICAL VOCABULARY ({len(all_canonicals)} distinct categories)")
    print("=" * 90)
    for c in sorted(all_canonicals):
        print(f"  - {c}")

    # Also need to re-check / report which categories were auto-stripped
    print()
    print("=" * 90)
    print("MAPPING REPORT (raw → canonical, by section)")
    print("=" * 90)
    for sy in sections_2025:
        p = CHEM / f"chem_{sy}.parquet"
        if not p.exists():
            continue
        df = pd.read_parquet(p)
        if "sample_category_canonical" not in df.columns:
            continue
        sub = df[df["sample_category"].notna()]
        if sub.empty:
            continue
        # Group by raw → canonical
        groups = sub.groupby(["sample_category", "sample_category_canonical"]).size().reset_index(name="n")
        groups = groups.sort_values("n", ascending=False)
        if groups.empty:
            continue
        print(f"\n{sy}")
        for _, r in groups.iterrows():
            raw = str(r["sample_category"])[:60]
            canon = str(r["sample_category_canonical"])
            marker = " (user override)" if (sy, str(r["sample_category"]).strip()) in OVERRIDES else ""
            print(f"  {raw:<62} → {canon:<35}  ({r['n']} rows){marker}")


if __name__ == "__main__":
    main()
