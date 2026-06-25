"""Apply the canonical 5-sector × 16-sub-municipality taxonomy to all chemistry
and microbiology parquets.

Adds two new columns:
  - municipality_canonical: Arabic canonical name (e.g. الروضة)
  - sector:                 English sector name (e.g. East, Central)

Original `municipality` column is preserved (rollback-safe).

Rules:
  1. Map every spelling variant (with/without بلدية prefix, typos, etc.) to its
     canonical Arabic name.
  2. 35 junk values (placeholders, numeric IDs, product names that leaked into
     the municipality column) → municipality_canonical = NULL, sector = NULL.
  3. Sector-only entries (وسط الرياض → Central, قطاع الشمال → North) roll up
     to their sector, but municipality_canonical is left NULL because the
     specific sub-municipality is unknown.
  4. "عينة خاصة" placeholder → preserved as canonical, but sector = NULL.

Output: clean/chemistry/chem_*_2025.parquet (and *_2024 where municipality
exists) and clean/microbiology/data*.parquet (each gets the canonical columns).
"""
from __future__ import annotations

from pathlib import Path
import pandas as pd

CLEAN = Path(__file__).resolve().parent.parent
# Updated 2026-06-25 — chemistry dashboard reads from chemistry/cleaned/, so
# canonical columns must be applied there too. We process both the joint
# clean/chemistry/ copy (for the joint dashboard) and the authoritative
# chemistry/cleaned/ originals (for the chemistry dashboard).
PROJECT_ROOT = CLEAN.parent
CHEM_DIRS = [CLEAN / "chemistry", PROJECT_ROOT / "chemistry" / "cleaned"]
MICRO = CLEAN / "microbiology"

# ─── Canonical taxonomy ──────────────────────────────────────────────────────
# 5 sectors × 16 sub-municipalities (restored 2026-06-25 per user direction —
# the prior 4-sector compression dropped the Central bucket which matches the
# lab's annual statistics). Five Central sub-municipalities reinstated.
SECTOR_OF: dict[str, str] = {
    # North
    "الشمال":   "North",
    # Central (restored 2026-06-25)
    "العليا":   "Central",
    "الشميسي":  "Central",
    "الملز":    "Central",
    "المعذر":   "Central",
    "البطحاء":  "Central",
    # East
    "الروضة":   "East",
    "الشرق":    "East",
    # West
    "عرقة":     "West",
    "نمار":     "West",
    "العريجاء": "West",
    # South
    "الشفا":    "South",
    "العزيزية": "South",
    "الحاير":   "South",
    "النسيم":   "South",
    "السلي":    "South",
}

# ─── Variant → canonical map ─────────────────────────────────────────────────
# Every chemistry / microbiology variant we observed in the data.
VARIANT_MAP: dict[str, str] = {
    # Al Rawdah → الروضة
    "بلدية الروضة": "الروضة",
    "الروضة": "الروضة",
    "البلدية/ الروضة": "الروضة",
    # Al Olaya → العليا
    "بلدية العليا": "العليا",
    "العليا": "العليا",
    "بلدية لعليا": "العليا",
    "- بلدية العليا": "العليا",
    # Al Shamal → الشمال
    "بلدية الشمال": "الشمال",
    "بلدية شمال": "الشمال",
    "بلدبة الشمال": "الشمال",
    "البلدية/ الشمال": "الشمال",
    "الشمال": "الشمال",
    # Al Maaadher → المعذر
    "بلدية المعذر": "المعذر",
    "المعذر": "المعذر",
    # Nimar → نمار
    "بلدية نمار": "نمار",
    "نمار": "نمار",
    # Arqah → عرقة
    "بلدية عرقة": "عرقة",
    "البلدية/ عرقة": "عرقة",
    "عرقة": "عرقة",
    # Al Naseem → النسيم
    "بلدية النسيم": "النسيم",
    "بلدية/ النسيم": "النسيم",
    "النسيم": "النسيم",
    # Al Uraija → العريجاء
    "بلدية العريجاء": "العريجاء",
    "العريجاء": "العريجاء",
    # Al Shumaisi → الشميسي
    "بلدية الشميسي": "الشميسي",
    "الشميسي": "الشميسي",
    # Al Bathaa → البطحاء
    "بلدية البطحاء": "البطحاء",
    "بلدية بطحاء": "البطحاء",
    "البطحاء": "البطحاء",
    # Al Malaz → الملز
    "بلدية الملز": "الملز",
    "البلدية/ الملز": "الملز",
    "بلدية اللملز": "الملز",
    "الملز": "الملز",
    # Al Shifa → الشفا (canonical) — both الشفا and الشفاء are accepted spellings
    "بلدية الشفاء": "الشفا",
    "بلدية الشفا": "الشفا",
    "الشفا": "الشفا",
    "الشفاء": "الشفا",
    # Al Sharq → الشرق
    "بلدية الشرق": "الشرق",
    "الشرق": "الشرق",
    # Al Aziziya → العزيزية
    "العزيزية": "العزيزية",
    "بلدية العزيزية": "العزيزية",
    # Al Suli → السلي
    "بلدية السلي": "السلي",
    "السلي": "السلي",
    # Al Haier → الحاير
    "بلدية الحاير": "الحاير",
    "الحاير": "الحاير",
    # Private Sample placeholder (not a real municipality — kept as-is)
    "عينة خاصة": "عينة خاصة",
    "( Private Sample) عينة خاصة": "عينة خاصة",
    ") عينة خاصة": "عينة خاصة",
}

# Sector-only entries — roll up to sector but no sub-municipality.
SECTOR_ONLY: dict[str, str | None] = {
    "وسط الرياض":          "Central",
    "القطاع وسط الرياض":   "Central",
    "قطاع الشمال":         "North",
}

# Arabic sector names (from microbiology source) → canonical English.
SECTOR_TRANSLATE: dict[str, str | None] = {
    "فرع أمانة في الشرق":            "East",
    "فرع أمانة في الشمال":           "North",
    "فرع أمانة في الغرب":            "West",
    "فرع أمانة في المنطقة الوسطى":   "Central",
    "فرع أمانة في الجنوب":           "South",
}

# Junk values — set both columns to NULL
JUNK = {
    "-", "460718156294.0",
    "هيل امريكي رقم ٣", "بهارات مشكل", "كمون سوري", "فلفل اسود",
    "حلاوة طحينة - سائل", "شطة شامية حارة",
    "قهوة تركي غامق", "قهوة هرري وسط",
    "فستق سادة", "لوز امريكي ني",
    "زبيب طبخ ذهبي", "زبيب اسود افغاني",
    "سمسم ني", "سلطة حمراء حارة",
}


def map_municipality(raw):
    """Returns (municipality_canonical, sector). NULL+NULL for junk / unknown."""
    if raw is None:
        return None, None
    try:
        if pd.isna(raw): return None, None
    except Exception:
        pass
    s = str(raw).strip()
    if not s or s in JUNK:
        return None, None
    if s in VARIANT_MAP:
        canon = VARIANT_MAP[s]
        return canon, SECTOR_OF.get(canon)
    if s in SECTOR_ONLY:
        # Sector-only — keep municipality NULL but assign sector
        return None, SECTOR_ONLY[s]
    # Unknown — return as-is, no sector
    return s, None


def process_parquet(p: Path, label: str):
    df = pd.read_parquet(p)
    if "municipality" not in df.columns:
        return None
    before_distinct = df["municipality"].dropna().astype(str).nunique()
    # Apply mapping
    mapped = df["municipality"].apply(map_municipality)
    df["municipality_canonical"] = [m for m, _ in mapped]
    sectors_from_municipality = [s for _, s in mapped]
    if "sector" not in df.columns:
        df["sector"] = sectors_from_municipality
    else:
        # Microbiology 2025 has its own sector column (Arabic). Translate to
        # English using SECTOR_TRANSLATE. Fill any gaps using the
        # municipality-derived sector — sub-municipality is authoritative
        # for chemistry where this script previously populated the column.
        def _translate(v):
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return None
            s = str(v).strip()
            return SECTOR_TRANSLATE.get(s, v)
        df["sector"] = df["sector"].apply(_translate)
        df["sector"] = df["sector"].fillna(pd.Series(sectors_from_municipality, index=df.index))
    df.to_parquet(p, compression="zstd", index=False)

    # Stats
    n_rows = len(df)
    n_canon = int(df["municipality_canonical"].notna().sum())
    n_sector = int(df["sector"].notna().sum())
    n_junk = int(df["municipality"].astype(str).isin(JUNK).sum())
    canon_distinct = int(df["municipality_canonical"].dropna().nunique())
    return {
        "label": label,
        "rows": n_rows,
        "raw_distinct": before_distinct,
        "canon_distinct": canon_distinct,
        "n_canon": n_canon,
        "n_sector": n_sector,
        "n_junk": n_junk,
    }


def main():
    print("=" * 90)
    print("APPLYING MUNICIPALITY CANONICAL TAXONOMY  (5 sectors × 16 sub-municipalities)")
    print("  (Central restored 2026-06-25)")
    print("=" * 90)
    print(f"Variant map size:  {len(VARIANT_MAP)} entries → 16 + 1 placeholder canonical")
    print(f"Sector-only map:   {len(SECTOR_ONLY)} entries")
    print(f"Junk set:          {len(JUNK)} values\n")

    results = []
    seen = set()
    for chem_dir in CHEM_DIRS:
        if not chem_dir.exists():
            continue
        for p in sorted(chem_dir.glob("chem_*.parquet")):
            label_key = (chem_dir.name + "/" + p.stem)
            if label_key in seen:
                continue
            seen.add(label_key)
            label = p.stem.replace("chem_", "") + (f" [{chem_dir.parent.name}/{chem_dir.name}]")
            r = process_parquet(p, label)
            if r is not None:
                results.append(r)
    for p in sorted(MICRO.glob("data*.parquet")):
        if "_long" in p.name:  # skip long-format parquets
            continue
        label = "microbio_" + p.stem.replace("data", "")
        r = process_parquet(p, label)
        if r is not None:
            results.append(r)

    print(f'{"section":<32}  {"rows":>5}  {"raw_distinct":>13}  {"canon_distinct":>15}  {"n_canon":>8}  {"n_sector":>9}  {"n_junk":>7}')
    print("-" * 100)
    for r in results:
        print(f'  {r["label"]:<30}  {r["rows"]:>5,}  {r["raw_distinct"]:>13}  {r["canon_distinct"]:>15}  {r["n_canon"]:>8,}  {r["n_sector"]:>9,}  {r["n_junk"]:>7}')

    # Combined vocabulary across all sources
    print()
    print("=" * 90)
    print("FINAL MUNICIPALITY VOCABULARY (canonical, all sources combined)")
    print("=" * 90)
    from collections import Counter
    total = Counter()
    sectors_count = Counter()
    chem_files = []
    for d in CHEM_DIRS:
        if d.exists():
            chem_files.extend(d.glob("chem_*.parquet"))
            break  # avoid double-counting (identical files)
    for p in chem_files + [MICRO/f"data{y}.parquet" for y in (2023,2024,2025)]:
        if not p.exists(): continue
        df = pd.read_parquet(p)
        if "municipality_canonical" in df.columns:
            for v in df["municipality_canonical"].dropna():
                total[str(v)] += 1
        if "sector" in df.columns:
            for v in df["sector"].dropna():
                sectors_count[str(v)] += 1

    print(f"\nDistinct municipality_canonical values: {len(total)}")
    for m, n in total.most_common():
        sec = SECTOR_OF.get(m, "(special)")
        print(f"  {n:>6,}  {m:<14}  [{sec}]")

    print(f"\nSector distribution (across all rows that have a sector):")
    for s in ("Central","East","North","South","West"):
        print(f"  {sectors_count.get(s, 0):>6,}  {s}")


if __name__ == "__main__":
    main()
