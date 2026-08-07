"""Build a self-contained HTML dashboard from the v2 chemistry parquets.

Reads every chem_<section>_<year>.parquet in cleaned/, concatenates per section,
and emits a slim per-row payload. The UI provides:
  - Section selector (chip bar)
  - Year filter (chip bar; "All" + each available year)
  - Search box (live filter on sample_id / sample_name / facility)
  - 6 KPI cards
  - Monthly stacked bar (valid/invalid/unknown)
  - Validity donut
  - Top non-compliant tests bar
  - Top repeat-offender facilities table
  - Sample-category pass/fail breakdown table
  - Drilldown table of invalid / matching samples (first 200)

Run:
    .venv/bin/python scripts/build_dashboard.py
Output: chemistry/reports/chemistry_dashboard.html
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CLEAN_DIR = ROOT / "cleaned"
OUT_HTML  = ROOT / "reports" / "chemistry_dashboard.html"

# Chemistry → GSO 1016 category bridge (spec 2026-06-18 — dashboard parity).
# Maps Arabic sample_category_canonical values to the 15 official GSO 1016
# categories that the microbio dashboard uses, so both dashboards share one
# product-taxonomy vocabulary. Unmapped → "Miscellaneous Foods".
# De-duplicated 2026-07-09 (Muhannad's GSO_bridge merge/delete annotations): one
# canonical Arabic per GSO — the exact spelling categories.py produces. The old
# variant spellings (الحلويات والشكولاته, منتجات الألبان/الحليب ومنتجات الالبان,
# الزيوت والدهون, tap/filter/bottled water, اعلاف, الأطعمة الجاهزه للاكل) and the
# "عينات خاصه" entry were removed — no data row carries them.
CHEM_TO_GSO = {
    "الفواكه والخضار":               "Fruit and Vegetables",
    "الحبوب والبقوليات":             "Cereals; Legumes and their Products",
    "البهارات والصوصات":             "Tomato Concentrates, Sauces, Vinegar, Spices and Herbs",
    "الأطعمة الجاهزة للأكل":         "Ready to Eat Foods",                          # C_RTE
    "اللحوم والدواجن":               "Meat, Poultry and its Products",
    "الحلويات والشوكولاتة":          "Chocolate, Sweets and their Ingredients",     # C_SWEET
    "الحليب ومنتجات الألبان":        "Dairy Products",                              # C_DAIRY
    "المشروبات":                     "Beverages",
    "الأسماك والمأكولات البحرية":     "Fish and Shellfish their Products",
    "البيض ومنتجاته":                "Egg and Egg Products",                        # GSO reference
    "الدهون والزيوت":                "Fats and Oils",                               # C_FAT
    "مياه صالحة للشرب":              "Drinking Water",                              # W_POTABLE (tap/filter/bottled merged)
    "مياه غير صالحة للشرب":          "Non-potable Water",                           # C_NONPOT
    "المربى والجلي":                 "Jelly, Jam and Marmalade",                    # C_JAM
    "أغذية أطفال":                   "Infants, Children and Certain Categories of Dietetic Foods",  # GSO reference
    "الأعلاف":                       "Animal Feed",                                 # C_FEED
    "أغذية متنوعة":                  "Miscellaneous Foods",                         # C_MISC (sesame only)
    "أخرى":                          "Others",                                      # C_OTHER
}
# Fallback name → GSO mapping (added 2026-06-25 because 2024 chemistry xlsx
# have no Sample Category column — without this every 2024 row would collapse
# into "Miscellaneous Foods" and the category panel would be useless).
# Matched as substring against the Arabic sample_name; first hit wins.
NAME_TO_GSO_PATTERNS = [
    # Drinking water — handled first because "موية" and "ماء" overlap others.
    ("Drinking Water",                                    ("موية","مياة","مياه","ماء")),
    ("Fish and Shellfish their Products",                 ("سمك","تونة","تونه","جمبري","روبيان","سلمون","بوري","بلطي","fish")),
    ("Meat, Poultry and its Products",                    ("لحم","لحوم","دجاج","فروج","شاورما","كباب","لحمة","beef","chicken")),
    ("Fruit and Vegetables",                              ("ليمون","برتقال","تفاح","موز","فراولة","فراوله","عنب","رمان","كيوي","يوسف",
                                                            "خس","بصل","طماطم","بندورة","فلفل","خيار","جزر","باذنجان","بقدونس","نعناع","حبق",
                                                            "كزبرة","جرجير","بطاطس","بطاطا","ثوم","ملفوف","قرنبيط","شمندر","بامية","كوسا",
                                                            "كمثرى","مانجو","توت","مشمش","خوخ","دراق","تمر","تين","افوكادو","apple","mango",
                                                            "lemon","orange","kiwi","grape","onion","carrot","tomato")),
    ("Cereals; Legumes and their Products",               ("ارز","أرز","قمح","عدس","حمص","فول","فاصوليا","ذرة","شعير","لوز","فستق","كاجو",
                                                            "بندق","جوز","سمسم","زبيب","رز","al-","pis-","al ","nut","seed","grain")),
    ("Tomato Concentrates, Sauces, Vinegar, Spices and Herbs", (
        "شطة","صلصة","صوص","خل","بهار","فلفل اسود","فلفل أحمر","كركم","زنجبيل","هيل","قرفة","قهوة هرري","sauce","spice","vinegar")),
    ("Chocolate, Sweets and their Ingredients",           ("حلاوة","شوكولا","كاكاو","سكر","حلويات","كنافة","بسكويت","كيك","chocolate","candy")),
    ("Dairy Products",                                    ("حليب","لبن","جبن","زبادي","قشطة","يوغرت","milk","cheese","yogurt")),
    ("Beverages",                                         ("عصير","شاي","كركديه","قهوة","نسكافيه","juice","coffee","tea")),
    ("Egg and Egg Products",                              ("بيض","egg")),
    ("Fats and Oils",                                     ("زيت","سمن","oil","ghee","butter")),
    ("Jelly, Jam and Marmalade",                          ("مربى","جلي","jam","jelly")),
    ("Animal Feed",                                       ("علف","اعلاف","feed","fodder")),
    ("Ready to Eat Foods",                                ("جاهز","شاورما","فطيرة","ساندوتش","معجنات","عسل","honey")),
]

def _gso_from_name(name: str | None) -> str | None:
    if not name: return None
    s = str(name).strip().lower()
    for gso, pats in NAME_TO_GSO_PATTERNS:
        for p in pats:
            if p.lower() in s:
                return gso
    return None

def _to_gso(cat: str | None, sample_name: str | None = None) -> str:
    if cat is not None:
        mapped = CHEM_TO_GSO.get(str(cat).strip())
        if mapped: return mapped
    # Secondary fallback: derive from sample_name (mostly for 2024 rows that
    # have no Sample Category column in the source).
    by_name = _gso_from_name(sample_name)
    if by_name: return by_name
    return "Miscellaneous Foods"

# The cleaner stores `sector` as the Arabic amanah-branch name, but the
# dashboard's sector chips, map pins, and legends are all English. Map to
# English at payload-build time so the filter chips actually match the data
# (fix 2026-07-01 — previously the English chips matched nothing). Unknown /
# None values pass through untouched.
SECTOR_AR_TO_EN = {
    "فرع أمانة في الشرق":            "East",
    "فرع أمانة في الشمال":           "North",
    "فرع أمانة في الغرب":            "West",
    "فرع أمانة في المنطقة الوسطى":   "Central",
    "فرع أمانة في الجنوب":           "South",
}

def _sector_en(sector):
    # Rows with no mapped amanah sector (no municipality, private samples, or
    # unmapped junk) go to an explicit "None" bucket so they remain filterable
    # and visible in the charts instead of silently dropping out (2026-07-04).
    if sector is None:
        return "None"
    return SECTOR_AR_TO_EN.get(str(sector).strip(), sector)

SECTIONS = [
    ("aflatoxins",           "Aflatoxins",            ""),  # section blurb removed 2026-07-04 (Muhannad)
    ("food_chemistry",       "Food chemistry",        "Moisture, ash, acidity, pH, peroxide, sensory tests"),
    ("heavy_metals",         "Heavy metals",          "Up to 25 metals incl. Lead, Arsenic, Cadmium, Mercury"),
    ("honey",                "Honey analysis",        "Sugars profile, HMF, moisture, acidity (each with its own limit)"),
    ("jam",                  "Jam & jelly",           "Sugar profile (Fructose/Glucose/Sucrose), HMF, moisture, pH — display-only, no GSO limits"),
    ("hormones_antibiotics", "Hormones & antibiotics", "Amoxicillin, Sulfamerazine, Sulfamethoxazole, Testosterone, Progesterone"),
    ("pesticides",           "Pesticides",            "One row per (sample, detected pesticide)"),
    ("water_analysis",       "Water analysis",        "Drinking-water tests: pH, electrical conductivity (EC), total dissolved solids (TDS), dissolved oxygen (DO), turbidity, chlorine, metals"),
]

# Sections with no derivable compliance (no limits, essentially no verdicts) —
# their test cells are "not evaluated", never counted compliant (2026-07-16).
DISPLAY_ONLY_SECTIONS = {"jam"}


def _val(x):
    if x is None:
        return None
    try:
        if pd.isna(x):
            return None
    except (TypeError, ValueError):
        pass
    return x


def _safe_date(x):
    if x is None:
        return None
    try:
        if pd.isna(x):
            return None
    except (TypeError, ValueError):
        pass
    try:
        return pd.Timestamp(x).strftime("%Y-%m-%d")
    except Exception:
        return None


def build_payload() -> dict:
    sections = {}
    all_years: set[int] = set()
    for prefix, label, desc in SECTIONS:
        frames = []
        for p in sorted(CLEAN_DIR.glob(f"chem_{prefix}_*.parquet")):
            m = re.search(r"_(\d{4})\.parquet$", p.name)
            if not m:
                continue
            year = int(m.group(1))
            all_years.add(year)
            df = pd.read_parquet(p)
            if "year" not in df.columns:
                df = df.assign(year=year)
            else:
                df["year"] = df["year"].fillna(year).astype(int)
            frames.append(df)
        if not frames:
            sections[prefix] = {"label": label, "desc": desc, "n_total": 0, "years": [], "rows": []}
            continue
        df = pd.concat(frames, ignore_index=True, sort=False)
        section_years = sorted({int(y) for y in df["year"].dropna().unique()})
        rows = []
        for r in df.itertuples(index=False):
            rows.append([
                int(getattr(r, "year", 0)) if pd.notna(getattr(r, "year", None)) else None,
                _safe_date(getattr(r, "sampling_date", None)),
                _val(getattr(r, "sheet_year_month", None)),
                _val(getattr(r, "sample_id", None)),
                _val(getattr(r, "sample_name", None)),
                # Prefer canonical category when available (clean/-pipeline addition),
                # fall back to raw sample_category for sections that don't have it.
                (_val(getattr(r, "sample_category_canonical", None))
                  if "sample_category_canonical" in df.columns and pd.notna(getattr(r, "sample_category_canonical", None))
                  else _val(getattr(r, "sample_category", None))),
                _val(getattr(r, "facility_name", None)),
                # Sectors-only display: emit the sector value in the
                # "municipality" payload slot so the dashboard shows only the
                # 5 sector buckets (Central/East/North/South/West — Central
                # restored 2026-06-25). Rows without a sector (junk values,
                # private-sample placeholders, sections without municipality
                # column like pesticides 2024) get None — no raw fallback.
                # Always emit a location bucket — mapped sector or "None"
                # (sections without a municipality column also fall to "None").
                _sector_en(_val(getattr(r, "sector", None))),
                _val(getattr(r, "district_name", None)),
                (1 if r.is_valid is True else (0 if r.is_valid is False else None))
                  if "is_valid" in df.columns else None,
                _val(getattr(r, "invalid_test", None)),
                _val(getattr(r, "pesticide_name", None)) if "pesticide_name" in df.columns else None,
                (float(getattr(r, "concentration_ppm", None))
                    if "concentration_ppm" in df.columns and pd.notna(getattr(r, "concentration_ppm", None)) else None),
                _val(getattr(r, "failed_tests_derived", None)) if "failed_tests_derived" in df.columns else None,
                _val(getattr(r, "validity_status", None)) if "validity_status" in df.columns else None,
                # GSO 1016 category (bridge from sample_category_canonical;
                # falls back to sample_name pattern matching for 2024 rows
                # whose source xlsx lack a Sample Category column).
                _to_gso(
                    _val(getattr(r, "sample_category_canonical", None))
                      if "sample_category_canonical" in df.columns
                      else _val(getattr(r, "sample_category", None)),
                    _val(getattr(r, "sample_name", None)),
                ),
                _val(getattr(r, "sample_name_group", None))
                  if "sample_name_group" in df.columns else _val(getattr(r, "sample_name", None)),
            ])
        sections[prefix] = {
            "label": label, "desc": desc,
            "n_total": len(df),
            "years": section_years,
            "rows": rows,
        }
    test_counts = _compute_test_counts()
    return {
        "cols": ["year","date","year_month","sample_id","sample_name","sample_category",
                 "facility","municipality","district",
                 "is_valid","invalid_test","pesticide_name","conc_ppm",
                 "failed_tests_derived","validity_status","gso_category","sample_name_group"],
        "all_years": sorted(all_years),
        "sections": sections,
        "test_counts": test_counts,
    }


def _compute_test_counts() -> dict:
    """Total chemistry tests by year, computed from the parquets.
    - Pesticides: per-sample max(num_pesticides) summed across samples
      (long-format has one row per pesticide; num_pesticides is the panel
      size — same value for every row of a given sample).
    - Other sections: count of non-null test result cells per row (each
      *_value / *_text column that isn't a _limit_value).
    """
    by_year: dict[int, int] = {}
    # Per-year compliant / non-compliant test split — proportional allocation:
    # for each row we know its total test count and whether it was compliant
    # (is_valid==1) or non-compliant. Use that to split the test totals into
    # compliant vs non-compliant. The split assumes that a non-compliant
    # sample had ALL its tests non-compliant, which is conservative but
    # acceptable for headline KPI purposes (sample-level verdict comes from
    # the worst test result).
    # Fixed 2026-06-18 — count actual non-compliant TESTS, not all tests
    # belonging to a non-compliant sample. Per the Annual Report 2025 a
    # sample tested for 30 pesticides with 1 failure → 1 non-comp test, 29
    # compliant tests (not 30/0). Previous logic over-counted non-compliant
    # tests by ~75× (58k vs AR's 763).
    split_by_year: dict[int, dict[str, int]] = {}
    # Per-(section, year) breakdown so the dashboard's test KPIs react to the
    # section tab, not just the year (2026-07-04).
    by_section_year: dict[str, dict[int, int]] = {}
    split_by_section_year: dict[str, dict[int, dict[str, int]]] = {}
    for p in sorted(CLEAN_DIR.glob("chem_*.parquet")):
        m = re.match(r"chem_(.+)_(\d{4})\.parquet$", p.name)
        if not m:
            continue
        section = m.group(1)
        year = int(m.group(2))
        df = pd.read_parquet(p)
        if "pesticides" in p.name:
            # Long format: each row = one pesticide × one sample. is_valid
            # on that row tells us whether THAT specific pesticide passed.
            # Total tests = sum of num_pesticides per sample (panel size).
            if "num_pesticides" in df.columns:
                per_sample = df.dropna(subset=["num_pesticides"]) \
                               .groupby("sample_id")["num_pesticides"].max()
                n = int(per_sample.sum())
                # Non-compliant tests = count of long-format rows whose
                # is_valid == False (each row IS one pesticide test result).
                nc = int((df["is_valid"] == False).sum()) if "is_valid" in df.columns else 0
                c  = n - nc
            else:
                n = len(df); c = nc = 0
        else:
            val_cols = [c2 for c2 in df.columns
                        if (c2.endswith("_value") or c2.endswith("_text"))
                        and not c2.endswith("_limit_value")]
            if val_cols:
                row_tests = df[val_cols].notna().sum(axis=1)
                n = int(row_tests.sum())
                # Non-compliant tests = sum of n_failed_tests_derived per row
                # (each row's count of tests that actually exceeded their
                # limit), NOT all tests on the row.
                if "n_failed_tests_derived" in df.columns:
                    nc = int(df["n_failed_tests_derived"].fillna(0).sum())
                    c  = n - nc
                else:
                    c = nc = 0
            else:
                n = c = nc = 0
        # Display-only sections have no meaningful pass/fail — bucket their
        # test cells as 'not_evaluated' instead of compliant (2026-07-16).
        if section in DISPLAY_ONLY_SECTIONS:
            ne = n
            c = nc = 0
        else:
            ne = 0
        by_year[year] = by_year.get(year, 0) + n
        slot = split_by_year.setdefault(year, {"compliant": 0, "non_compliant": 0, "not_evaluated": 0})
        slot["compliant"]     += c
        slot["non_compliant"] += nc
        slot["not_evaluated"] += ne
        by_section_year.setdefault(section, {})[year] = n
        ssl = split_by_section_year.setdefault(section, {}).setdefault(
            year, {"compliant": 0, "non_compliant": 0, "not_evaluated": 0})
        ssl["compliant"]     += c
        ssl["non_compliant"] += nc
        ssl["not_evaluated"] += ne
    grand = sum(by_year.values())
    g_compliant     = sum(v["compliant"]     for v in split_by_year.values())
    g_non_compliant = sum(v["non_compliant"] for v in split_by_year.values())
    g_not_evaluated = sum(v["not_evaluated"] for v in split_by_year.values())
    return {
        "by_year": by_year,
        "grand": grand,
        "compliance_split_by_year": split_by_year,
        "compliance_split": {"compliant": g_compliant, "non_compliant": g_non_compliant, "not_evaluated": g_not_evaluated},
        "by_section_year": by_section_year,
        "compliance_split_by_section_year": split_by_section_year,
    }


TEMPLATE = r"""<!DOCTYPE html>
<html lang="en" dir="ltr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>مختبرات أمانة الرياض</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;900&family=IBM+Plex+Sans+Arabic:wght@300;400;500;600&family=DM+Mono:wght@400;500&family=Cormorant+Garamond:ital,wght@1,500&display=swap" rel="stylesheet">
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js" charset="utf-8"></script>
<style>
/* ═══════════════════════════════════════════════════════════════════
   Riyadh Municipal Editorial — theme system
   Palette: Najdi heritage green + warm sand + burnished gold
   Type:    Tajawal (display) · IBM Plex Sans Arabic (body) · DM Mono (numerics)
   ═══════════════════════════════════════════════════════════════════ */
:root {
  /* Heritage palette */
  --green-900:#0a3d24;     /* deep Najdi / logo seal */
  --green-700:#0e5c36;     /* primary brand */
  --green-500:#22853f;     /* hover / chart series */
  --green-100:#dcefe1;     /* compliant pill bg */

  --gold-700:#9a7b2a;      /* burnished gold ink */
  --gold-500:#c8a85a;      /* primary accent */
  --gold-200:#f0e3bf;      /* accent wash */

  --clay-700:#7a2616;      /* deep clay (non-comp ink) */
  --clay-500:#a8331a;      /* clay red — replaces generic red */
  --clay-100:#f7d9d0;      /* non-comp pill bg */

  --sand-50: #faf6ee;      /* page background — warm paper */
  --sand-100:#f4ecde;      /* card hover / chip rest */
  --sand-200:#e8dcc4;      /* hairline borders, warm */
  --sand-300:#d4c5a4;      /* darker dividers */

  --ink-900: #1a1f2c;      /* primary text — midnight */
  --ink-700: #3d4256;
  --ink-500: #6c6f7e;      /* muted ink */

  /* Legacy aliases so existing code still resolves */
  --bg: var(--sand-50);
  --bg-2: #fffdf8;         /* card paper */
  --bg-3: var(--sand-100);
  --fg: var(--ink-900);
  --muted: var(--ink-500);
  --line: var(--sand-200);
  --accent: var(--green-700);
  --good: var(--green-500);
  --warn: var(--gold-700);
  --bad: var(--clay-500);
  --crit: var(--clay-700);

  --shadow: 0 1px 0 rgba(154,123,42,0.04), 0 4px 12px -4px rgba(10,61,36,0.08);
  --shadow-warm: 0 1px 0 rgba(154,123,42,0.05), 0 8px 24px -8px rgba(122,38,22,0.12);

  --logo: url("__LOGO_DATA_URI__");
  --najdi-pattern: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 60 60' opacity='0.06'><path d='M30 0 L60 30 L30 60 L0 30 Z M30 12 L48 30 L30 48 L12 30 Z' fill='%23faf6ee'/></svg>");
}
* { box-sizing: border-box }
html, body { background: var(--sand-50); color: var(--ink-900); margin: 0;
  font-family: 'IBM Plex Sans Arabic', 'Tajawal', 'Tahoma', system-ui, sans-serif;
  font-size: 14px; font-feature-settings: 'kern', 'liga', 'tnum' }
body { padding: 0 0 60px;
  background-image:
    radial-gradient(ellipse 1200px 600px at 50% -200px, rgba(14,92,54,0.06), transparent 60%),
    var(--najdi-pattern);
}

/* ─── Heritage masthead ──────────────────────────────────────────── */
.masthead { position: relative; padding: 0; margin: 0 0 18px;
  background: linear-gradient(180deg, var(--green-900) 0%, var(--green-700) 100%);
  color: #faf6ee; overflow: hidden; border-bottom: 4px solid var(--gold-500); }
.masthead::before { content: ""; position: absolute; inset: 0;
  background:
    url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 120 40' opacity='0.05'><path d='M0 20 Q15 0 30 20 T60 20 T90 20 T120 20' stroke='%23f0e3bf' stroke-width='1.5' fill='none'/></svg>") repeat-x bottom/120px 40px;
  pointer-events: none; }
.masthead-inner { display: flex; align-items: center; gap: 22px;
  padding: 22px 30px 24px; position: relative; z-index: 1; max-width: 1600px; margin: 0 auto; }
.masthead .logo { width: 72px; height: 72px; border-radius: 50%;
  background: var(--logo) center/cover no-repeat #fffdf8;
  border: 3px solid var(--gold-500); flex-shrink: 0;
  box-shadow: 0 4px 16px rgba(0,0,0,0.25); }
.masthead .titleblock { flex: 1; min-width: 0 }
.masthead .title-ar { font-family: 'Tajawal', sans-serif; font-weight: 700;
  font-size: 22px; letter-spacing: 0.5px; line-height: 1.1; direction: rtl;
  color: #fffdf8; margin: 0; text-shadow: 0 1px 2px rgba(0,0,0,0.2); }
.masthead .title-en { font-family: 'Tajawal', sans-serif; font-weight: 500;
  font-size: 13px; letter-spacing: 4px; text-transform: uppercase;
  color: var(--gold-200); margin: 6px 0 0; opacity: 0.92; }
.masthead .subtitle-block { font-family: 'Cormorant Garamond', 'Tajawal', serif;
  font-style: italic; font-size: 16px; color: var(--gold-500);
  margin-top: 10px; letter-spacing: 0.3px;
  border-top: 1px solid rgba(200,168,90,0.3); padding-top: 8px; }
.masthead .meta-strip { font-family: 'DM Mono', monospace;
  font-size: 11px; color: var(--gold-200); text-align: right;
  letter-spacing: 1px; opacity: 0.75; flex-shrink: 0;
  border-left: 1px solid rgba(200,168,90,0.3); padding-left: 20px; }
.masthead .meta-strip .label { display: block; font-size: 9px;
  text-transform: uppercase; letter-spacing: 2px; opacity: 0.7; margin-bottom: 2px; }
.masthead .meta-strip .val { font-size: 14px; font-weight: 500; color: #fffdf8; }

.page-body { padding: 28px 42px 60px; max-width: 1640px; margin: 0 auto; }

h1 { font-family: 'Tajawal', sans-serif; font-size: 22px; margin: 0 0 6px;
  font-weight: 700; letter-spacing: 0.3px; color: var(--ink-900); display: none; }
h2 { font-family: 'Tajawal', sans-serif; font-size: 12px; margin: 0 0 12px;
  font-weight: 600; color: var(--gold-700); text-transform: uppercase;
  letter-spacing: 2.2px; }
h2::before { content: "۞"; color: var(--gold-500); margin-right: 8px;
  font-size: 14px; opacity: 0.6; }
.subtitle { color: var(--ink-500); font-size: 13px; margin: 0;
  font-family: 'Cormorant Garamond', serif; font-style: italic; }
.control-row { display: flex; flex-wrap: wrap; gap: 12px; align-items: center;
   padding: 14px 22px; min-height: 52px;
   background: var(--bg-2); border: 1px solid var(--sand-200);
   border-radius: 4px; margin-bottom: 18px; box-shadow: var(--shadow) }
.control-row::before { content: ""; display: block; width: 3px; height: 24px;
   background: var(--gold-500); margin-right: 8px; align-self: center; }
.control-label { font-size: 10px; color: var(--gold-700); text-transform: uppercase;
   letter-spacing: 2.5px; font-weight: 600; margin-right: 6px;
   font-family: 'Tajawal', sans-serif }
.chip { padding: 7px 16px; background: var(--sand-100); border: 1px solid var(--sand-200);
   border-radius: 2px; font-size: 12px; cursor: pointer; user-select: none;
   white-space: nowrap; font-family: 'Tajawal', sans-serif; font-weight: 500;
   color: var(--ink-700); transition: all 0.12s ease }
.chip:hover { border-color: var(--green-700); background: #fffdf8; color: var(--green-900) }
.chip.active { background: var(--green-700); border-color: var(--green-700);
   color: #faf6ee; font-weight: 600; box-shadow: 0 2px 4px rgba(14,92,54,0.25) }
.sec-chip { padding: 10px 18px; background: var(--bg-2); border: 1px solid var(--sand-200);
   border-radius: 2px; cursor: pointer; font-size: 13px; user-select: none;
   white-space: nowrap; color: var(--ink-700); font-family: 'Tajawal', sans-serif;
   font-weight: 500; transition: all 0.12s ease; border-left: 3px solid var(--sand-200); }
.sec-chip:hover { border-color: var(--green-700); border-left-color: var(--gold-500); color: var(--green-900) }
.sec-chip.active { background: var(--green-900); border-color: var(--green-900);
   border-left-color: var(--gold-500); color: #faf6ee; font-weight: 600 }
.search { flex: 1; min-width: 200px; padding: 7px 12px; background: #fffdf8;
   border: 1px solid var(--sand-200); border-radius: 2px; color: var(--ink-900);
   font-size: 13px; font-family: 'IBM Plex Sans Arabic', sans-serif }
.search:focus { outline: none; border-color: var(--green-700);
   box-shadow: 0 0 0 3px rgba(14,92,54,0.12) }

.kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
   gap: 18px; margin-bottom: 22px }
.kpi { padding: 16px 20px 14px; background: var(--bg-2);
   border: 1px solid var(--sand-200); border-radius: 4px; position: relative;
   overflow: hidden; box-shadow: var(--shadow);
   background-image: linear-gradient(180deg, #fffefa 0%, var(--bg-2) 100%); }
.kpi::before { content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 3px;
   background: var(--green-700) }
.kpi.good::before { background: var(--green-500) }
.kpi.warn::before { background: var(--gold-500) }
.kpi.bad::before  { background: var(--clay-500) }
.kpi.crit::before { background: var(--clay-700) }
.kpi .label { color: var(--gold-700); font-size: 10px; text-transform: uppercase;
   letter-spacing: 2px; margin-bottom: 8px; font-weight: 600;
   font-family: 'Tajawal', sans-serif }
.kpi .value { font-size: 28px; font-weight: 500; line-height: 1;
   font-family: 'DM Mono', 'Courier New', monospace; color: var(--ink-900);
   font-variant-numeric: tabular-nums; letter-spacing: -0.5px }
.kpi .sub { color: var(--ink-500); font-size: 11px; margin-top: 6px;
   font-family: 'IBM Plex Sans Arabic', sans-serif }

.grid { display: grid; gap: 22px; grid-template-columns: 1fr 1fr }
.grid > .full { grid-column: 1 / -1 }
.card { background: var(--bg-2); border: 1px solid var(--sand-200);
   border-radius: 4px; padding: 26px 28px 24px; box-shadow: var(--shadow);
   position: relative }
.card + .card, .card.full + .card { margin-top: 0; }
.card > h2 { margin-bottom: 18px; }
.card::before { content: ""; position: absolute; top: 0; left: 0; right: 0;
   height: 2px; background: linear-gradient(90deg, var(--gold-500) 0%, transparent 40%); }
.card .chart { width: 100%; min-height: 300px }
@media (max-width: 900px) { .grid { grid-template-columns: 1fr } }
table { width: 100%; border-collapse: collapse; font-size: 13px;
   font-family: 'IBM Plex Sans Arabic', sans-serif }
th, td { padding: 11px 14px; text-align: left;
   border-bottom: 1px solid var(--sand-200); vertical-align: top }
th { color: var(--gold-700); font-size: 10px; text-transform: uppercase;
   letter-spacing: 1.8px; font-weight: 600; background: var(--sand-100);
   border-bottom: 2px solid var(--sand-300); font-family: 'Tajawal', sans-serif }
tbody tr:hover { background: var(--sand-100) }
td { font-variant-numeric: tabular-nums }
.muted { color: var(--ink-500) }
.ar { font-family: 'IBM Plex Sans Arabic', 'Tajawal', sans-serif;
   direction: rtl; unicode-bidi: embed; font-weight: 500 }
.badge { display: inline-block; padding: 3px 10px; border-radius: 2px; font-size: 11px;
   font-weight: 600; font-family: 'Tajawal', sans-serif; letter-spacing: 0.3px }
.badge.y2024 { background: var(--gold-200); color: var(--gold-700) }
.badge.y2025 { background: var(--green-100); color: var(--green-900) }
.badge.valid { background: var(--green-100); color: var(--green-900);
   border-left: 2px solid var(--green-500) }
.badge.invalid { background: var(--clay-100); color: var(--clay-700);
   border-left: 2px solid var(--clay-500) }
.badge.unknown { background: var(--sand-100); color: var(--ink-500) }
.section-desc { color: var(--muted); font-size: 12px; margin: -4px 0 14px }
.error-banner { padding: 12px 16px; background: #fee2e2;
   border: 1px solid var(--crit); border-radius: 12px; color: #991b1b;
   margin-bottom: 14px; display: none }
.global-banner { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
   gap: 22px; padding: 26px 30px; background: var(--bg-2);
   border: 1px solid var(--sand-200); border-radius: 4px; margin-bottom: 22px;
   box-shadow: var(--shadow); position: relative; overflow: hidden;
   background-image: linear-gradient(180deg, #fffefa 0%, var(--bg-2) 100%); }
.global-banner::before { content: ""; position: absolute; top: 0; left: 0; right: 0;
   height: 3px; background: linear-gradient(90deg, var(--green-700) 0%, var(--gold-500) 50%, var(--green-700) 100%); }
.global-banner .gb-item { text-align: left; padding-right: 18px;
   border-right: 1px solid var(--sand-200); }
.global-banner .gb-item:last-child { border-right: none }
.global-banner .gb-label { font-size: 10px; color: var(--gold-700); text-transform: uppercase;
   letter-spacing: 2px; margin-bottom: 10px; font-weight: 600;
   font-family: 'Tajawal', sans-serif }
.global-banner .gb-value { font-size: 28px; font-weight: 500; line-height: 1.05;
   font-family: 'DM Mono', monospace; color: var(--ink-900);
   font-variant-numeric: tabular-nums; letter-spacing: -0.5px }
.global-banner .gb-sub { color: var(--ink-500); margin-top: 10px;
   font-style: italic; font-family: 'Cormorant Garamond', serif; font-size: 13px; line-height: 1.4 }

.btn { padding: 7px 16px; background: var(--bg-2); border: 1px solid var(--green-700);
   border-radius: 2px; color: var(--green-900); font-size: 12px; cursor: pointer;
   font-family: 'Tajawal', sans-serif; font-weight: 500; letter-spacing: 0.3px;
   transition: all 0.12s ease }
.btn:hover { background: var(--green-700); color: #faf6ee }
.btn.primary { background: var(--green-700); border-color: var(--green-700);
   color: #faf6ee; font-weight: 600 }
.btn.primary:hover { background: var(--green-900); border-color: var(--green-900) }

.yoy { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px; align-items: stretch }
.yoy .yoy-cell { padding: 24px 22px; background: var(--sand-100);
   border-radius: 2px; text-align: center; border-top: 3px solid var(--sand-300) }
.yoy .yoy-cell:nth-child(2) { background: #fffdf8; border-top-color: var(--gold-500) }
.yoy .yoy-year { font-size: 10px; color: var(--gold-700); letter-spacing: 2.2px;
   text-transform: uppercase; font-family: 'Tajawal', sans-serif; font-weight: 600 }
.yoy .yoy-fail { font-size: 28px; font-weight: 500; margin: 8px 0;
   font-family: 'DM Mono', monospace; color: var(--ink-900);
   font-variant-numeric: tabular-nums }
.yoy .yoy-detail { font-size: 11px; color: var(--ink-500);
   font-family: 'IBM Plex Sans Arabic', sans-serif }
.yoy .yoy-delta { font-size: 22px; font-weight: 500; font-family: 'Tajawal', sans-serif }
.yoy .yoy-delta.up { color: var(--clay-700) }
.yoy .yoy-delta.down { color: var(--green-700) }
.yoy .yoy-delta.flat { color: var(--ink-500) }
.yoy-delta { font-family: 'Tajawal', sans-serif; font-weight: 600 }

footer { margin-top: 40px; color: var(--ink-500); font-size: 11px; text-align: center;
   font-family: 'Tajawal', sans-serif; letter-spacing: 1.5px; text-transform: uppercase;
   padding: 20px 30px; border-top: 1px solid var(--sand-200);
   background: linear-gradient(180deg, transparent 0%, var(--sand-100) 100%); }
footer::before { content: "۞"; color: var(--gold-500); margin-right: 8px;
   font-size: 14px; opacity: 0.6; }

.section-desc { color: var(--ink-500); font-size: 14px; margin: 4px 0 22px;
   font-family: 'Cormorant Garamond', serif; font-style: italic;
   border-left: 2px solid var(--gold-500); padding: 4px 0 4px 14px; line-height: 1.5 }
</style>
</head>
<body>

<header class="masthead">
  <div class="masthead-inner">
    <div class="logo"></div>
    <div class="titleblock">
      <h2 class="title-ar">مختبرات أمانة الرياض</h2>
      <div class="title-en">Riyadh Municipality · Research &amp; Development</div>
      <div class="subtitle-block">Chemistry Decision Dashboard</div>
    </div>
    <div class="meta-strip">
      <span class="label">Last build</span>
      <span class="val" id="build-stamp">—</span>
    </div>
  </div>
</header>

<div class="page-body">
<h1>Riyadh Municipality Lab</h1>

<div class="error-banner" id="error-banner"></div>

<!-- Global summary across ALL sections -->
<div class="global-banner" id="global-banner"></div>


<!-- Section selector -->
<div class="control-row" id="section-bar">
  <span class="control-label">Section</span>
</div>

<!-- Year + Compliance + Sector + Search -->
<div class="control-row">
  <span class="control-label">Year</span>
  <div id="year-chips" style="display:flex;gap:6px;flex-wrap:wrap"></div>
  <span class="control-label" style="margin-left:18px">Compliance</span>
  <div id="compliance-chips" style="display:flex;gap:6px;flex-wrap:wrap"></div>
  <span class="control-label" style="margin-left:18px">Sector</span>
  <div id="sector-chips" style="display:flex;gap:6px;flex-wrap:wrap"></div>
  <span class="control-label" style="margin-left:18px">Search</span>
  <input type="text" class="search" id="search" placeholder="Filter by sample ID, name, facility…" autocomplete="off">
  <span class="muted" id="filter-status" style="font-size:11px"></span>
  <button class="btn" id="btn-reset">Reset filters</button>
</div>

<!-- GSO 1016 category chips (bridge from chem sample_category_canonical) -->
<div class="control-row">
  <span class="control-label">GSO 1016 category</span>
  <div id="gso-chips" style="display:flex;gap:6px;flex-wrap:wrap"></div>
</div>

<div class="section-desc" id="section-desc"></div>

<!-- Test-level summary (compliant / non-compliant tests). Distinct from
     the sample-level banner above. -->
<div class="global-banner" id="test-banner" style="margin-top:14px"></div>

<!-- Year-over-year card appears only when section has both years -->
<div class="card full" id="card-yoy" style="margin-bottom:14px;display:none">
  <h2>Year-over-year comparison</h2>
  <div id="yoy-grid"></div>
</div>

<div class="grid">
  <div class="card"><h2>Monthly compliance results</h2><div class="chart" id="chart-monthly"></div></div>
  <div class="card"><h2>Validity breakdown</h2><div class="chart" id="chart-validity"></div></div>
  <div class="card full"><h2>Sector breakdown</h2><div class="chart" id="chart-municipalities" style="min-height:300px"></div></div>
  <div class="card full"><h2>GSO 1016 category — volume &amp; non-compliance</h2><div class="chart" id="chart-gso" style="min-height:340px"></div></div>
  <div class="card full"><h2>Top 10 most-contaminated subtypes <span class="muted" style="font-size:11px; font-weight:400; letter-spacing:0; text-transform:none">— grouped by sample_name with parent GSO category. Minimum 20 samples per row.</span></h2><div id="chart-top-subtypes" style="overflow:auto"></div></div>
  <div class="card full"><h2>Riyadh map <span class="muted" style="font-size:11px; font-weight:400; letter-spacing:0; text-transform:none">— samples by sector (marker size = volume, colour = % non-compliance)</span></h2><div id="chart-map" class="chart" style="min-height:480px"></div></div>
  <div class="card full"><h2>Top non-compliant tests</h2><div class="chart" id="chart-fail"></div></div>
  <div class="card"><h2>Top 10 repeat-offender facilities</h2><div id="tbl-facilities" style="overflow:auto;max-height:380px"></div></div>
  <div class="card"><h2>Sample-category breakdown</h2><div id="tbl-categories" style="overflow:auto;max-height:380px"></div></div>
  <div class="card full">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
      <h2 style="margin:0">Drilldown · all matching samples (invalid first)</h2>
      <button class="btn primary" id="btn-csv">Download CSV</button>
    </div>
    <div id="drilldown" style="overflow:auto;max-height:600px"></div>
  </div>
</div>

</div><!-- /.page-body -->
<footer>أمانة منطقة الرياض · Riyadh Municipality Research &amp; Development</footer>

<script>
"use strict";

try {
  const DATA = __DATA_JSON__;
  const COLS = {};
  DATA.cols.forEach((c, i) => COLS[c] = i);

  let currentSection = "__all__";
  let currentYear = "all";
  let searchTerm = "";
  // 3-tier filter additions (spec 2026-06-18): chemistry SCOPE filters now
  // include compliance + sector + GSO category to match microbio's vocabulary.
  let activeCompliance = new Set();   // 'Compliant' / 'Non-compliant'
  let activeSectors    = new Set();   // 'East' / 'North' / 'West' / 'South'
  let activeGso        = new Set();   // GSO 1016 category names

  // Synthetic "All sections" pseudo-section.
  // In this view, rows are deduplicated by (year, sample_id) so each physical
  // sample appears once regardless of how many panels it was tested in. The
  // resulting "merged" row aggregates validity (invalid wins > valid > unknown)
  // and collects the list of sections that tested the sample.
  const ALL_LABEL = "All sections";
  const ALL_DESC  = "Total physical samples across every section. One sample tested in N panels = ONE row; verdict is aggregated (non-compliant if any panel is non-compliant).";

  let _combinedCache = null;
  function getCombinedRows() {
    if (_combinedCache) return _combinedCache;
    const byKey = new Map();
    Object.entries(DATA.sections).forEach(([secKey, sec]) => {
      sec.rows.forEach(r => {
        if (!r[COLS.sample_id]) return;  // skip rows without sample identity
        const key = r[COLS.year] + '|' + r[COLS.sample_id];
        let m = byKey.get(key);
        if (!m) {
          m = r.slice();             // copy base columns
          m._sections = [secKey];
          m._issues = [];
          byKey.set(key, m);
        } else {
          m._sections.push(secKey);
          // Fill in any null fields from this section's row
          for (let i = 0; i < DATA.cols.length; i++) {
            if (m[i] == null && r[i] != null) m[i] = r[i];
          }
          // Validity aggregation: invalid wins, else any valid wins, else unknown
          if (r[COLS.is_valid] === 0) m[COLS.is_valid] = 0;
          else if (m[COLS.is_valid] === null && r[COLS.is_valid] === 1) m[COLS.is_valid] = 1;
        }
        // Collect issue tokens for invalid rows (prefixed with section)
        if (r[COLS.is_valid] === 0) {
          const issue = r[COLS.failed_tests_derived] || r[COLS.invalid_test] || r[COLS.pesticide_name];
          if (issue) {
            // Split pipe-separated failures into individual tests
            String(issue).split('|').map(s => s.trim()).filter(Boolean).forEach(tok => {
              m._issues.push(`[${secKey}] ${tok}`);
            });
          }
        }
      });
    });
    const out = Array.from(byKey.values());
    // Rebuild failed_tests_derived to reflect the union of issues across panels
    out.forEach(m => {
      m[COLS.failed_tests_derived] = m._issues.length ? m._issues.join(' | ') : null;
    });
    _combinedCache = out;
    return out;
  }
  function isAllSections() { return currentSection === "__all__"; }
  function combinedYears() {
    const ys = new Set();
    Object.values(DATA.sections).forEach(s => s.years.forEach(y => ys.add(y)));
    return [...ys].sort();
  }
  // Total unique physical samples across all sections (one per (year, sample_id)).
  function combinedTotal() { return getCombinedRows().length; }

  function escapeHtml(s) {
    if (s === null || s === undefined) return '';
    return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }
  function pct(num, den) { return den > 0 ? (num * 100 / den).toFixed(1) : '0.0'; }
  function lc(x) { return x == null ? '' : String(x).toLowerCase(); }

  // Computed-from-data test counts for the active SECTION + YEAR scope, split
  // into compliant / non-compliant. Precomputed in Python per (section, year),
  // so this reacts to the section tab and the year chip (2026-07-04). It does
  // NOT reflect compliance/sector/GSO/search narrowing (not in the split).
  function testCountsScope() {
    const tc = DATA.test_counts || {};
    let total = 0, compliant = 0, non_compliant = 0, not_evaluated = 0;
    const addSplit = s => { if (s) { compliant += s.compliant || 0; non_compliant += s.non_compliant || 0; not_evaluated += s.not_evaluated || 0; } };
    if (isAllSections()) {
      if (currentYear === 'all') {
        total = tc.grand || 0; addSplit(tc.compliance_split);
      } else {
        total = (tc.by_year || {})[String(currentYear)] || 0;
        addSplit((tc.compliance_split_by_year || {})[String(currentYear)]);
      }
    } else {
      const bsy = (tc.by_section_year || {})[currentSection] || {};
      const ssy = (tc.compliance_split_by_section_year || {})[currentSection] || {};
      const years = currentYear === 'all' ? Object.keys(bsy) : [String(currentYear)];
      years.forEach(y => { total += bsy[y] || 0; addSplit(ssy[y]); });
    }
    return { total, compliant, non_compliant, not_evaluated };
  }
  function totalTestsThisFilter() { return testCountsScope().total; }

  // Scope filters (compliance / sector / GSO / search) — NOT year, NOT section
  // selection. Reused so per-section views can filter their own row arrays.
  function applyScopeFilters(rows) {
    if (activeCompliance.size > 0) {
      const wantC = activeCompliance.has('Compliant');
      const wantN = activeCompliance.has('Non-compliant');
      if (!(wantC && wantN)) {
        rows = rows.filter(r => {
          const v = r[COLS.is_valid];
          if (wantC) return v === 1;
          if (wantN) return v === 0;
          return true;
        });
      }
    }
    if (activeSectors.size > 0) {
      rows = rows.filter(r => r[COLS.municipality] && activeSectors.has(r[COLS.municipality]));
    }
    if (activeGso.size > 0) {
      rows = rows.filter(r => r[COLS.gso_category] && activeGso.has(r[COLS.gso_category]));
    }
    if (searchTerm) {
      const q = searchTerm;
      rows = rows.filter(r =>
        lc(r[COLS.sample_id]).includes(q)
        || lc(r[COLS.sample_name]).includes(q)
        || lc(r[COLS.facility]).includes(q)
        || lc(r[COLS.invalid_test]).includes(q)
        || lc(r[COLS.failed_tests_derived]).includes(q)
        || lc(r[COLS.pesticide_name]).includes(q)
      );
    }
    return rows;
  }

  // Apply year + search filter to current section's rows. When the synthetic
  // "All sections" view is active, rows include a trailing _section element.
  function filteredRows() {
    let rows;
    if (isAllSections()) {
      rows = getCombinedRows();
    } else {
      rows = DATA.sections[currentSection].rows;
    }
    if (currentYear !== "all") {
      const y = parseInt(currentYear, 10);
      rows = rows.filter(r => r[COLS.year] === y);
    }
    return applyScopeFilters(rows);
  }
  function rowSection(r) {
    // For "All sections" rows we append section key at the end.
    return r.length > DATA.cols.length ? r[DATA.cols.length] : currentSection;
  }

  // Global summary across ALL sections — counts UNIQUE PHYSICAL SAMPLES, not
  // test events. The 'combined rows' map is already deduped by (year, sample_id),
  // so each row here = 1 physical sample with verdict aggregated across panels.
  function renderGlobalBanner() {
    let totalSamples = 0, totalValid = 0, totalInvalid = 0, totalUnknown = 0;
    const facSet = new Set(), munSet = new Set();
    // Recompute from the active filtered set so every KPI card reacts to the
    // section / year / compliance / sector / GSO / search filters (U6,
    // 2026-07-01). filteredRows() already applies all active filters.
    filteredRows().forEach(r => {
      totalSamples++;
      if (r[COLS.is_valid] === 1) totalValid++;
      else if (r[COLS.is_valid] === 0) totalInvalid++;
      else totalUnknown++;
      if (r[COLS.facility]) facSet.add(r[COLS.facility]);
      if (r[COLS.municipality] && r[COLS.municipality] !== 'None') munSet.add(r[COLS.municipality]);
    });
    // Also compute total test events (sum across sections) for context.
    let totalEvents = 0;
    Object.values(DATA.sections).forEach(sec => {
      sec.rows.forEach(r => {
        if (currentYear !== "all" && r[COLS.year] !== parseInt(currentYear, 10)) return;
        totalEvents++;
      });
    });
    const failPct = pct(totalInvalid, totalSamples);
    const yrLabel = currentYear === "all" ? "All years" : `Year ${currentYear}`;
    // Compute total tests (computed from data) and split by compliant /
    // non-compliant. The chemistry-test count was computed in Python at
    // build time and shipped in DATA.test_counts.compliance_split.
    // Test-level counts for the active section + year (reacts to the tab).
    const _tsc = testCountsScope();
    const totalTests = _tsc.total;
    const cTests = _tsc.compliant;
    const ncTests = _tsc.non_compliant;
    const neTests = _tsc.not_evaluated;
    // "Without specifications" bucket (added 2026-06-25 per user direction):
    // these samples have no regulatory limit on file (validity_status='no_limit'
    // or 'unknown' or 'rejected'). They were previously dropped silently from
    // the counters, making total ≠ compliant + non-compliant. The bucket
    // surfaces them and lets the three numbers add up correctly.
    const unknownSub = totalUnknown > 0
      ? `<div class="gb-sub">samples with no limit on file</div>` : '';
    document.getElementById('global-banner').innerHTML = `
      <div class="gb-item"><div class="gb-label">${yrLabel} · total samples</div>
        <div class="gb-value" style="color:var(--accent)">${totalSamples.toLocaleString()}</div>
        <div class="gb-sub">${totalTests.toLocaleString()} chemistry tests performed</div></div>
      <div class="gb-item"><div class="gb-label">Compliant samples</div>
        <div class="gb-value" style="color:var(--good)">${totalValid.toLocaleString()}</div>
        <div class="gb-sub">${pct(totalValid, totalSamples)}% pass all panels</div></div>
      <div class="gb-item"><div class="gb-label">Non-compliant samples</div>
        <div class="gb-value" style="color:var(--crit)">${totalInvalid.toLocaleString()}</div>
        <div class="gb-sub">${failPct}% non-compliant in ≥1 panel</div></div>
      <div class="gb-item"><div class="gb-label">Without specifications</div>
        <div class="gb-value" style="color:var(--warn)">${totalUnknown.toLocaleString()}</div>
        ${unknownSub}</div>
      <div class="gb-item"><div class="gb-label">Total facilities</div>
        <div class="gb-value">${facSet.size.toLocaleString()}</div></div>
      <div class="gb-item"><div class="gb-label">Sectors covered</div>
        <div class="gb-value">${munSet.size.toLocaleString()}</div></div>
    `;
    // Separate test-level summary strip — distinct from the sample-level
    // banner above. Tests = individual test results across all samples
    // (e.g. one sample tested for 30 pesticides = 30 tests).
    // The test counts are precomputed per (section, year), so this strip reacts
    // to the section tab and year chip. It cannot reflect compliance/sector/GSO/
    // search narrowing (not in the precomputed split), so hide it only when one
    // of those is active (2026-07-04).
    const testBanner = document.getElementById('test-banner');
    const testBannerValid = activeCompliance.size === 0 && activeSectors.size === 0
      && activeGso.size === 0 && !searchTerm;
    if (!testBannerValid) {
      testBanner.style.display = 'none';
      testBanner.innerHTML = '';
      return;
    }
    testBanner.style.display = '';
    const tFailPct = totalTests > 0 ? (100 * ncTests / totalTests).toFixed(2) : '0';
    const tCompPct = totalTests > 0 ? (100 * cTests / totalTests).toFixed(2) : '0';
    const tNePct = totalTests > 0 ? (100 * neTests / totalTests).toFixed(2) : '0';
    testBanner.innerHTML = `
      <div class="gb-item"><div class="gb-label">${yrLabel} · total chemistry tests</div>
        <div class="gb-value" style="color:var(--accent)">${totalTests.toLocaleString()}</div>
        <div class="gb-sub">distinct test results across all samples</div></div>
      <div class="gb-item"><div class="gb-label">Compliant tests</div>
        <div class="gb-value" style="color:var(--good)">${cTests.toLocaleString()}</div>
        <div class="gb-sub">${tCompPct}% of tests passed</div></div>
      <div class="gb-item"><div class="gb-label">Non-compliant tests</div>
        <div class="gb-value" style="color:var(--crit)">${ncTests.toLocaleString()}</div>
        <div class="gb-sub">${tFailPct}% of tests failed</div></div>
      <div class="gb-item"><div class="gb-label">Not evaluated</div>
        <div class="gb-value" style="color:var(--warn)">${neTests.toLocaleString()}</div>
        <div class="gb-sub">${tNePct}% — no limit on file</div></div>
    `;
  }

  function renderSectionBar() {
    const bar = document.getElementById('section-bar');
    bar.innerHTML = '<span class="control-label">Section</span>';
    // "All sections" combined view first.
    const all = document.createElement('div');
    all.className = 'sec-chip' + (isAllSections() ? ' active' : '');
    const totalAll = combinedTotal();
    all.textContent = `${ALL_LABEL} (${totalAll.toLocaleString()} total)`;
    all.onclick = () => { currentSection = "__all__"; currentYear = "all"; renderAll(); };
    bar.appendChild(all);
    Object.entries(DATA.sections).forEach(([key, sec]) => {
      const c = document.createElement('div');
      c.className = 'sec-chip' + (key === currentSection ? ' active' : '');
      c.textContent = `${sec.label} (${sec.n_total.toLocaleString()})`;
      c.onclick = () => { currentSection = key; currentYear = "all"; renderAll(); };
      bar.appendChild(c);
    });
  }

  function renderYearBar() {
    const wrap = document.getElementById('year-chips');
    wrap.innerHTML = '';
    let total, years, rowsForYear;
    if (isAllSections()) {
      total = combinedTotal();
      years = combinedYears();
      rowsForYear = y => getCombinedRows().filter(r => r[COLS.year] === y).length;
    } else {
      const sec = DATA.sections[currentSection];
      total = sec.n_total;
      years = sec.years;
      rowsForYear = y => sec.rows.filter(r => r[COLS.year] === y).length;
    }
    const opts = [['all', `All years · ${total.toLocaleString()} samples`]];
    years.forEach(y => opts.push([String(y), `${y} · ${rowsForYear(y).toLocaleString()} samples`]));
    opts.forEach(([key, label]) => {
      const c = document.createElement('div');
      c.className = 'chip' + (key === currentYear ? ' active' : '');
      c.textContent = label;
      c.onclick = () => { currentYear = key; renderAll(); };
      wrap.appendChild(c);
    });
  }

  function renderKpis() {
    // KPI strip removed 2026-06-18 — the global-banner above already shows
    // these metrics (no point duplicating). This function is now a no-op
    // so renderAll() can keep calling it harmlessly.
  }

  // New SCOPE-filter chip builders (spec 2026-06-18 — dashboard parity).
  function renderComplianceChips() {
    const wrap = document.getElementById('compliance-chips');
    if (!wrap) return;
    wrap.innerHTML = '';
    ['Compliant','Non-compliant'].forEach(v => {
      const c = document.createElement('div');
      c.className = 'chip' + (activeCompliance.has(v) ? ' active' : '');
      c.textContent = v;
      c.onclick = () => {
        if (activeCompliance.has(v)) activeCompliance.delete(v);
        else activeCompliance.add(v);
        renderAll();
      };
      wrap.appendChild(c);
    });
  }
  function renderSectorChips() {
    const wrap = document.getElementById('sector-chips');
    if (!wrap) return;
    wrap.innerHTML = '';
    // Count rows per sector in the current section/year scope so the chip
    // labels reflect real numbers. "None" = rows with no mapped amanah sector
    // (no municipality, private, or unmapped). 5-sector taxonomy + None
    // (Central restored 2026-06-25; None bucket added 2026-07-04).
    const counts = new Map();
    chipScopeRows().forEach(r => {
      const s = r[COLS.municipality] || 'None';
      counts.set(s, (counts.get(s) || 0) + 1);
    });
    ['Central','East','North','South','West','None'].forEach(v => {
      const n = counts.get(v) || 0;
      const c = document.createElement('div');
      c.className = 'chip' + (activeSectors.has(v) ? ' active' : '');
      c.textContent = `${v} (${n.toLocaleString()})`;
      c.onclick = () => {
        if (activeSectors.has(v)) activeSectors.delete(v);
        else activeSectors.add(v);
        renderAll();
      };
      wrap.appendChild(c);
    });
  }
  // Rows for the active section (combined when "All") narrowed by the active
  // YEAR only. Used to populate option lists (e.g. GSO chips) so they reflect
  // the current section/year instead of the whole dataset (U5, 2026-07-01).
  // Deliberately NOT narrowed by the chip filters themselves, so an option
  // doesn't vanish the moment it's toggled on.
  function chipScopeRows() {
    let rows = isAllSections() ? getCombinedRows() : DATA.sections[currentSection].rows;
    if (currentYear !== 'all') {
      const y = parseInt(currentYear, 10);
      rows = rows.filter(r => r[COLS.year] === y);
    }
    return rows;
  }

  function renderGsoChips() {
    const wrap = document.getElementById('gso-chips');
    if (!wrap) return;
    wrap.innerHTML = '';
    // Rebuild from the currently-scoped rows (section + year), sorted by volume,
    // so the option list tracks the active section/year (U5).
    const counts = new Map();
    chipScopeRows().forEach(r => {
      const g = r[COLS.gso_category];
      if (g) counts.set(g, (counts.get(g) || 0) + 1);
    });
    const sorted = Array.from(counts.entries()).sort((a,b) => b[1] - a[1]);
    sorted.forEach(([g, n]) => {
      const c = document.createElement('div');
      c.className = 'chip' + (activeGso.has(g) ? ' active' : '');
      c.textContent = `${g} (${n.toLocaleString()})`;
      c.onclick = () => {
        if (activeGso.has(g)) activeGso.delete(g);
        else activeGso.add(g);
        renderAll();
      };
      wrap.appendChild(c);
    });
  }

  function renderMonthly() {
    const rows = filteredRows();
    const monthly = {};
    const yearsSeen = new Set();
    // Per user direction 2026-06-18: monthly chart shows only Compliant vs
    // Non-compliant. The "No limit", "Rejected" and "Unknown" buckets are
    // dropped from the visual (still kept in the underlying data for filters).
    rows.forEach(r => {
      const ym = r[COLS.year_month];
      if (!ym) return;
      if (!monthly[ym]) monthly[ym] = {v:0, i:0};
      if (r[COLS.is_valid] === 1) monthly[ym].v++;
      else if (r[COLS.is_valid] === 0) monthly[ym].i++;
      const yr = r[COLS.year];
      if (yr) yearsSeen.add(yr);
    });
    if (!Object.keys(monthly).length) {
      Plotly.purge('chart-monthly');
      document.getElementById('chart-monthly').innerHTML = '<p class="muted">No data.</p>';
      return;
    }
    const months = [];
    Array.from(yearsSeen).sort().forEach(yr => {
      for (let m = 1; m <= 12; m++) {
        const ym = `${yr}-${String(m).padStart(2, '0')}`;
        months.push(ym);
        if (!monthly[ym]) monthly[ym] = {v:0, i:0};
      }
    });
    // Format month labels: '2025-03' → 'Mar 2025'
    const monthAbbr = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    const labels = months.map(ym => {
      const [y, m] = ym.split('-');
      return `${monthAbbr[parseInt(m,10)-1]} ${y}`;
    });
    Plotly.newPlot('chart-monthly', [
      {x: labels, y: months.map(m => monthly[m].v),  name: 'Compliant',     type: 'bar', marker:{color:'#059669', line:{color:'#047857',width:0.5}},
        hovertemplate: '<b>%{x}</b><br>Compliant: %{y:,}<extra></extra>'},
      {x: labels, y: months.map(m => monthly[m].i),  name: 'Non-compliant', type: 'bar', marker:{color:'#dc2626', line:{color:'#991b1b',width:0.5}},
        hovertemplate: '<b>%{x}</b><br>Non-compliant: %{y:,}<extra></extra>'},
    ], {barmode:'stack', paper_bgcolor:'transparent', plot_bgcolor:'transparent',
        font:{color:'#1c2742', family:'Inter, system-ui, sans-serif'},
        margin:{t:10,r:10,b:70,l:55}, height:320,
        xaxis: {tickangle: -45, tickfont:{size:11}, gridcolor:'#e5e7eb', showline:true, linecolor:'#cbd5e1'},
        yaxis: {gridcolor:'#e5e7eb', title:{text:'Samples', font:{size:12}}, zeroline:true, zerolinecolor:'#cbd5e1'},
        legend: {orientation: 'h', y: -0.28, font:{size:11}},
        bargap: 0.18,
        hovermode: 'x unified',
       }, {responsive:true, displayModeBar:false});
  }

  function renderValidity() {
    const rows = filteredRows();
    // Unknown bucket removed per user direction 2026-06-18. Only show
    // Compliant vs Non-compliant. Rows with null verdict are excluded
    // from this chart (they remain in the parquet for forensics).
    const c = {Compliant:0, 'Non-compliant':0};
    rows.forEach(r => {
      if (r[COLS.is_valid] === 1) c.Compliant++;
      else if (r[COLS.is_valid] === 0) c['Non-compliant']++;
    });
    const total = c.Compliant + c['Non-compliant'];
    if (!total) {
      Plotly.purge('chart-validity');
      document.getElementById('chart-validity').innerHTML = '<p class="muted">No data.</p>';
      return;
    }
    Plotly.newPlot('chart-validity', [{
      labels: Object.keys(c), values: Object.values(c),
      type: 'pie', hole: 0.55,
      marker: {colors: ['#059669', '#dc2626']},
      textinfo: 'label+percent', textposition: 'outside',
    }], {paper_bgcolor:'transparent', font:{color:'#1c2742'},
        margin:{t:10,r:10,b:10,l:10}, height:300, showlegend:false}, {responsive:true, displayModeBar:false});
  }

  // Test-name normalisation: maps the cleaner's internal labels (mixed
  // Arabic/English, occasional aliases like "aflatoxin_total" which is the
  // sum-of-aflatoxins panel) to clean English display names. Also flags
  // sensory texture tests for exclusion from the chart (user direction
  // 2026-06-18: sensory results are mostly compliant noise).
  // Case-insensitive lookup. Keys stored lowercased.
  const FAIL_LABEL_MAP = {
    'aflatoxin_total':         'Aflatoxin (total)',
    'aflatoxin total':         'Aflatoxin (total)',
    'aflatoxin b1':            'Aflatoxin B1',
    'aflatoxin b2':            'Aflatoxin B2',
    'aflatoxin g1':            'Aflatoxin G1',
    'aflatoxin g2':            'Aflatoxin G2',
    'الرطوبة':                  'Moisture',
    'الرماد':                   'Ash',
    'الحموضة':                  'Acidity',
    'التزنخ':                   'Rancidity',
    'الرقم الهيدروجيني ph':     'pH',
    'بيروكسيد':                 'Peroxide',
    'الرقم لحامض':              'Acid number',
    'الدهون':                   'Fat',
    'الجوامد الكلية':           'Total solids',
    'الجوامد الكلية اللادهنية': 'Total solids (non-fat)',
    'pb':                       'Lead (Pb)',
    'cd':                       'Cadmium (Cd)',
    // Common pesticide-name title-casing fixes
    'cypermethrin':             'Cypermethrin',
    'imazalil':                 'Imazalil',
    'pyrimethanil':             'Pyrimethanil',
    'penconazole':              'Penconazole',
    'tebuconazole':             'Tebuconazole',
    'fipronil':                 'Fipronil',
    '2-phenylphenol':           '2-Phenylphenol',
    'thpi(tetrahydrophthalimide)': 'THPI (Tetrahydrophthalimide)',
    // #8 — arsenic variants merge to one label
    'arsenic':                  'Arsenic',
    'total arsenic':            'Arsenic',
    'الزرنيخ الكلي':            'Arsenic',
    // #5/#12 — water analytes → canonical English
    'sulphate':                 'Sulphate',
    'الكبريتات':                'Sulphate',
    'chloride':                 'Chloride',
    'nitrate':                  'Nitrate',
    'nitrate(no3)':             'Nitrate',
    'النترات':                  'Nitrate',
    'nitrite':                  'Nitrite',
    'floride':                  'Fluoride',
    'fluorid':                  'Fluoride',
    'fluoride':                 'Fluoride',
    'tds':                      'TDS',
    'total dissolved salt tds': 'TDS',
    't.hardness':               'Total hardness',
    'total hardness':           'Total hardness',
    'sodium':                   'Sodium',
    'ph':                       'pH',
    'turbidity':                'Turbidity',
  };
  // Sensory-only tests are excluded (mostly compliant noise).
  const SENSORY_TOKENS = ['اختبار حسي','sensory','texture','اللون','الرائحة','الطعم','القوام'];
  // Placeholder "names" the lab wrote in pesticide_name to indicate "all
  // pesticides below 0.01 ppm" — drop them too.
  const PLACEHOLDER_TOKENS = ['تراكيز المبيدات أقل','أقل من 0.01','below detection','below 0.01',
                              'مياه فلتر','مياة فلتر','فلتر','مياه','مياة','موية'];
  function normaliseFail(label) {
    if (!label) return null;
    const trimmed = String(label).trim();
    const lc = trimmed.toLowerCase();
    if (lc === 'na' || lc === 'nan' || lc === 'n/a') return null;
    for (const tok of SENSORY_TOKENS)     if (lc.includes(tok.toLowerCase())) return null;
    for (const tok of PLACEHOLDER_TOKENS) if (lc.includes(tok.toLowerCase())) return null;
    return FAIL_LABEL_MAP[lc] || trimmed;
  }

  // Multi-word water analyte names that must survive the space-split.
  const WATER_MULTIWORD = [
    [/total\s+dissolved\s+salt\s+tds/ig, 'TDS'],
    [/t\.?\s*hardness/ig, 'T.Hardness'],
    [/total\s+hardness/ig, 'T.Hardness'],
    [/nitrate\s*\(no3\)/ig, 'Nitrate'],
  ];
  function splitWaterTests(raw) {
    if (!raw) return [];
    let s = String(raw).replace(/\|/g, ' ');
    WATER_MULTIWORD.forEach(([re, tok]) => { s = s.replace(re, ' ' + tok + ' '); });
    return s.split(/\s+/).map(t => t.trim()).filter(Boolean);
  }

  function renderFail() {
    const rows = filteredRows();
    const counts = {};
    function add(label) {
      const n = normaliseFail(label);
      if (n) counts[n] = (counts[n]||0) + 1;
    }
    rows.forEach(r => {
      if (isAllSections()) {
        // Combined view: split the merged issues string into individual tokens
        // (each already prefixed with [section] when created in getCombinedRows).
        const issues = r[COLS.failed_tests_derived];
        if (!issues) return;
        // Strip "[section] " prefix the combined builder adds, normalise each test.
        String(issues).split('|').map(s => s.trim()).filter(Boolean).forEach(tok => {
          const stripped = tok.replace(/^\[[^\]]+\]\s*/, '');
          add(stripped);
        });
        return;
      }
      const sec = rowSection(r);
      if (sec === 'pesticides') {
        // Trace amounts (< 0.01 ppm) are below practical reporting; treat
        // as noise per user direction 2026-06-18.
        const conc = r[COLS.conc_ppm];
        const trace = (conc !== null && conc !== undefined && conc < 0.01);
        if (r[COLS.is_valid] === 0 && r[COLS.pesticide_name] && !trace) add(r[COLS.pesticide_name]);
      } else if (sec === 'water_analysis') {
        // #12 — water lab records several failed analytes as ONE space-joined
        // string (e.g. "TDS T.Hardness Chloride Nitrate Sulphate Sodium").
        // Split into individual analytes so each is counted on its own.
        const raw = r[COLS.failed_tests_derived] || (r[COLS.is_valid] === 0 ? r[COLS.invalid_test] : '');
        splitWaterTests(raw).forEach(add);
      } else if (r[COLS.failed_tests_derived]) {
        // Per-test column may list multiple failures separated by '|'.
        String(r[COLS.failed_tests_derived]).split('|').forEach(t => add(t.trim()));
      } else if (r[COLS.is_valid] === 0 && r[COLS.invalid_test]) {
        add(r[COLS.invalid_test]);
      } else if (r[COLS.is_valid] === 0) {
        // #10 — invalid but the lab recorded no failing test.
        add('Unspecified');
      }
    });
    const entries = Object.entries(counts).sort((a,b) => b[1] - a[1]).slice(0, 25);
    if (!entries.length) {
      Plotly.purge('chart-fail');
      document.getElementById('chart-fail').innerHTML = '<p class="muted">No non-compliant-test data for this filter.</p>';
      return;
    }
    // Gradient: top failures darker red, rest amber → orange so the eye lands
    // on the worst offenders first.
    const grandTotal = entries.reduce((s, e) => s + e[1], 0);
    const top = entries[0][1];
    const colors = entries.map((_, i) => {
      const t = i / Math.max(1, entries.length - 1);
      // interpolate from #b91c1c (dark red) → #f59e0b (amber)
      const lerp = (a, b) => Math.round(a + (b - a) * t);
      return `rgb(${lerp(0xb9, 0xf5)},${lerp(0x1c, 0x9e)},${lerp(0x1c, 0x0b)})`;
    });
    Plotly.newPlot('chart-fail', [{
      x: entries.map(e => e[1]),
      y: entries.map(e => e[0]),
      type: 'bar', orientation: 'h',
      marker: {color: colors, line: {color: '#fff', width: 1}},
      text: entries.map(e => `${e[1]}  ·  ${(e[1]*100/grandTotal).toFixed(1)}%`),
      textposition: 'outside',
      textfont: {size: 11, color: '#1c2742'},
      hovertemplate: '<b>%{y}</b><br>Non-compliant: %{x:,}<br>%{customdata:.1f}% of non-compliant tests<extra></extra>',
      customdata: entries.map(e => e[1]*100/grandTotal),
      cliponaxis: false,
    }], {paper_bgcolor:'transparent', plot_bgcolor:'transparent',
        font:{color:'#1c2742', family:'Inter, system-ui, sans-serif'},
        margin:{t:10, r:80, b:35, l:280},
        height: Math.max(240, entries.length * 26 + 70),
        xaxis: {gridcolor:'#e5e7eb', title: {text:'Non-compliance count', font:{size:12}}, range:[0, top*1.18]},
        yaxis: {automargin: true, autorange: 'reversed', tickfont:{size:12}},
        bargap: 0.25,
       }, {responsive:true, displayModeBar:false});
  }

  // GSO category bar chart (volume stacked by year + non-compliance % line).
  function renderGsoCat() {
    const rows = filteredRows();
    const byCat = {};
    rows.forEach(r => {
      const g = r[COLS.gso_category]; if (!g) return;
      if (!byCat[g]) byCat[g] = { total: 0, inv: 0, byYear: {} };
      byCat[g].total++;
      if (r[COLS.is_valid] === 0) byCat[g].inv++;
      const yr = r[COLS.year];
      if (yr) byCat[g].byYear[yr] = (byCat[g].byYear[yr] || 0) + 1;
    });
    const items = Object.entries(byCat)
      .map(([cat, s]) => ({ cat, total: s.total, inv: s.inv, byYear: s.byYear,
                            rate: s.total ? 100*s.inv/s.total : 0 }))
      .sort((a,b) => b.total - a.total).slice(0, 12);
    if (!items.length) {
      Plotly.purge('chart-gso');
      document.getElementById('chart-gso').innerHTML = '<p class="muted">No GSO-categorised samples in current filter.</p>';
      return;
    }
    const years = Array.from(new Set(items.flatMap(i => Object.keys(i.byYear).map(Number)))).sort();
    const YEAR_COLOR = { 2024: '#9a7b2a', 2025: '#0e5c36' };
    const labels = items.map(i => i.cat);
    const traces = years.map(yr => ({
      type: 'bar', x: labels,
      y: items.map(i => i.byYear[yr] || 0),
      name: String(yr),
      marker: { color: YEAR_COLOR[yr] || '#7a8aa7' },
      hovertemplate: '<b>%{x}</b><br>' + yr + ': %{y:,} samples<extra></extra>',
    }));
    traces.push({
      type: 'scatter', mode: 'lines+markers',
      x: labels, y: items.map(i => i.rate),
      name: 'Non-compliance %', yaxis: 'y2',
      line: { color: '#a8331a', width: 3, shape: 'spline' },
      marker: { size: 9, line: { color: '#fffdf8', width: 1.5 } },
      hovertemplate: '<b>%{x}</b><br>Non-compliance: %{y:.1f}%<extra></extra>',
    });
    Plotly.newPlot('chart-gso', traces, {
      paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
      font: { color: '#1a1f2c', family: 'IBM Plex Sans Arabic, sans-serif' },
      barmode: 'stack', bargap: 0.22,
      margin: { l: 50, r: 60, t: 18, b: 110 },
      xaxis: { tickangle: -25, automargin: true, gridcolor: '#e8dcc4' },
      yaxis: { title: 'Samples', gridcolor: '#e8dcc4' },
      yaxis2: { overlaying: 'y', side: 'right', title: '% non-compliance', range: [0, 100], showgrid: false },
      legend: { orientation: 'h', y: -0.35 },
      hovermode: 'x unified',
    }, { responsive: true, displayModeBar: false });
  }

  // Top 10 most-contaminated subtypes — ranked by ABSOLUTE non-conformity
  // count (user direction 2026-06-25 — matches the lab's annual statistics
  // which count failed samples, not failure rates). Sub-variant grouping
  // (e.g. lemon / orange variants) is computed once, upstream, in the
  // `sample_name_group` payload column (single source of truth — see
  // clean_chemistry.py) rather than duplicated here in JS.
  function renderTopSubtypes() {
    const rows = filteredRows();
    const stats = new Map();
    rows.forEach(r => {
      const n = r[COLS.sample_name_group] || r[COLS.sample_name]; if (!n) return;
      const slot = stats.get(n) || { total: 0, inv: 0, gso: r[COLS.gso_category] };
      slot.total++;
      if (r[COLS.is_valid] === 0) slot.inv++;
      if (!slot.gso && r[COLS.gso_category]) slot.gso = r[COLS.gso_category];
      stats.set(n, slot);
    });
    const items = [];
    for (const [n, s] of stats) {
      if (s.inv === 0) continue;
      items.push({ name: n, total: s.total, inv: s.inv, gso: s.gso || '(uncategorised)', rate: 100*s.inv/s.total });
    }
    // Rank by absolute non-conformity count; tiebreak by rate.
    items.sort((a,b) => b.inv - a.inv || b.rate - a.rate);
    const top = items.slice(0, 10);
    const node = document.getElementById('chart-top-subtypes');
    if (!top.length) {
      node.innerHTML = '<div class="muted" style="padding:20px">No non-compliant subtypes in current filter.</div>';
      return;
    }
    const maxInv = Math.max(1, top[0].inv);
    const tr = top.map((it, i) => {
      const barW = Math.max(20, 200 * it.inv / maxInv);
      const cls = it.rate >= 50 ? '#a8331a' : it.rate >= 30 ? '#c8a85a' : '#7a8aa7';
      return '<tr>'
        + '<td style="text-align:right; color:#6c6f7e; width:30px">' + (i+1) + '</td>'
        + '<td class="ar" style="font-weight:600">' + escapeHtml(it.name) + '</td>'
        + '<td><span style="font-size:11px; color:#6c6f7e">' + escapeHtml(it.gso) + '</span></td>'
        + '<td style="text-align:right; font-variant-numeric:tabular-nums; font-weight:600">' + it.inv + '</td>'
        + '<td style="text-align:right; color:#6c6f7e">/ ' + it.total.toLocaleString() + '</td>'
        + '<td style="text-align:right">' + it.rate.toFixed(1) + '%</td>'
        + '<td style="width:200px"><div style="height:10px; background:#e8dcc4; border-radius:5px; overflow:hidden">'
        +   '<div style="height:100%; width:' + barW + 'px; background:' + cls + '"></div></div></td>'
        + '</tr>';
    }).join('');
    node.innerHTML = '<table style="width:100%; font-size:13px"><thead><tr style="color:#9a7b2a; font-size:11px; text-transform:uppercase; letter-spacing:0.8px">'
      + '<th></th><th>Subtype</th><th>GSO category</th><th style="text-align:right">Non-comp</th><th style="text-align:right">Total</th><th style="text-align:right">Rate</th><th></th></tr></thead>'
      + '<tbody>' + tr + '</tbody></table>';
  }

  // Riyadh map — 5 sector centroids. Marker size = sample volume, colour = %
  // non-compliance; labels + hover carry the numbers (2026-07-04). The "None"
  // bucket has no geographic location so it is not plotted here.
  const SECTOR_PINS = {
    'Central': [24.6877, 46.7219],
    'East':    [24.7275, 46.7840],
    'North':   [24.8400, 46.6900],
    'West':    [24.6300, 46.6033],
    'South':   [24.5470, 46.7800],
  };
  function renderMapPlaceholder() {
    const rows = filteredRows();
    const agg = {};
    rows.forEach(r => {
      const s = r[COLS.municipality];
      if (!s || !(s in SECTOR_PINS)) return;   // skip None / non-geographic
      if (!agg[s]) agg[s] = { total: 0, inv: 0 };
      agg[s].total++;
      if (r[COLS.is_valid] === 0) agg[s].inv++;
    });
    const present = Object.keys(SECTOR_PINS).filter(s => agg[s]);
    const node = document.getElementById('chart-map');
    if (!present.length) {
      Plotly.purge('chart-map');
      node.innerHTML = '<p class="muted" style="padding:30px">No sector-located samples in the current filter.</p>';
      return;
    }
    const maxTotal = Math.max(...present.map(s => agg[s].total));
    const totals = present.map(s => agg[s].total);
    const invs   = present.map(s => agg[s].inv);
    const rates  = present.map((s, i) => totals[i] ? 100 * invs[i] / totals[i] : 0);
    // Marker area ∝ volume (sqrt scale), 22..64 px.
    const sizes  = totals.map(t => 22 + 42 * Math.sqrt(t / maxTotal));
    Plotly.newPlot('chart-map', [{
      type: 'scattermapbox',
      lat: present.map(s => SECTOR_PINS[s][0]),
      lon: present.map(s => SECTOR_PINS[s][1]),
      mode: 'markers+text',
      marker: {
        size: sizes, sizemode: 'diameter',
        color: rates, colorscale: [[0, '#0e5c36'], [0.5, '#c8a85a'], [1, '#a8331a']],
        cmin: 0, cmax: Math.max(10, ...rates), opacity: 0.85,
        showscale: true,
        colorbar: { title: { text: '% non-comp', side: 'right' }, thickness: 12, len: 0.6, x: 1 },
      },
      text: present.map((s, i) => `${s}<br>${totals[i].toLocaleString()}`),
      textposition: 'top center',
      textfont: { size: 13, color: '#1a1f2c', family: 'Tajawal, sans-serif' },
      customdata: present.map((s, i) => [totals[i], invs[i], rates[i]]),
      hovertemplate: '<b>%{text}</b> samples<br>%{customdata[1]:,} non-compliant · %{customdata[2]:.1f}%<extra></extra>',
    }], {
      paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
      margin: { t: 0, r: 0, b: 0, l: 0 },
      mapbox: { style: 'carto-positron', center: { lat: 24.7136, lon: 46.6753 }, zoom: 9.3 },
    }, { responsive: true, displayModeBar: false });
  }

  function renderFacilities() {
    const rows = filteredRows();
    const fac = {};
    rows.forEach(r => {
      const f = r[COLS.facility];
      if (!f) return;
      if (!fac[f]) fac[f] = {total: 0, invalid: 0};
      fac[f].total++;
      if (r[COLS.is_valid] === 0) fac[f].invalid++;
    });
    const arr = Object.entries(fac).filter(([_, v]) => v.invalid >= 1)
      .sort((a,b) => b[1].invalid - a[1].invalid || (b[1].invalid/b[1].total) - (a[1].invalid/a[1].total))
      .slice(0, 10);
    if (!arr.length) {
      document.getElementById('tbl-facilities').innerHTML = '<p class="muted">No facility-level invalid samples.</p>';
      return;
    }
    const tr = arr.map(([f, v]) => {
      const p = v.total > 0 ? (v.invalid * 100 / v.total).toFixed(1) : '0';
      const cls = p >= 50 ? 'invalid' : p >= 25 ? 'unknown' : '';
      return `<tr><td class="ar">${escapeHtml(f)}</td><td>${v.total}</td>
        <td><span class="badge ${cls}">${v.invalid}</span></td><td>${p}%</td></tr>`;
    }).join('');
    document.getElementById('tbl-facilities').innerHTML = `<table>
      <thead><tr><th>Facility</th><th>Total</th><th>Non-compliant</th><th>Non-compliance %</th></tr></thead>
      <tbody>${tr}</tbody></table>`;
  }

  // Year-over-year comparison card. Per-section: 3-cell yoy. All-sections:
  // multi-row table showing each section's 2024→2025 delta.
  function renderYoY() {
    const card = document.getElementById('card-yoy');
    if (currentYear !== "all") {
      card.style.display = 'none';
      return;
    }
    if (isAllSections()) {
      const years = combinedYears();
      if (years.length < 2) { card.style.display = 'none'; return; }
      card.style.display = '';
      const [y1, y2] = years;
      // First: per-section table (using EVENTS per panel — keeps each panel's
      // pass/fail rate visible) plus an aggregate row for total samples.
      // #9 — respect active scope filters at the per-section EVENT level.
      // Combined rows can't be split back per section (a sample may belong to
      // several), so filter each section's own rows directly.
      const tr = Object.entries(DATA.sections).map(([key, sec]) => {
        if (!sec.years.includes(y1) || !sec.years.includes(y2)) return '';
        const secRows = applyScopeFilters(sec.rows);
        const r1 = secRows.filter(r => r[COLS.year] === y1);
        const r2 = secRows.filter(r => r[COLS.year] === y2);
        const i1 = r1.filter(r => r[COLS.is_valid] === 0).length;
        const i2 = r2.filter(r => r[COLS.is_valid] === 0).length;
        const p1 = r1.length ? i1 * 100 / r1.length : 0;
        const p2 = r2.length ? i2 * 100 / r2.length : 0;
        const delta = p2 - p1;
        const cls = Math.abs(delta) < 0.5 ? 'flat' : (delta > 0 ? 'up' : 'down');
        // Worded change-marker — no glyphs/triangles per user direction.
        const word = Math.abs(delta) < 0.5 ? 'Flat' : (delta > 0 ? 'Worse' : 'Better');
        return `<tr>
          <td>${escapeHtml(sec.label)}</td>
          <td>${r1.length.toLocaleString()}</td>
          <td><span class="badge invalid">${i1}</span></td>
          <td>${p1.toFixed(1)}%</td>
          <td>${r2.length.toLocaleString()}</td>
          <td><span class="badge invalid">${i2}</span></td>
          <td>${p2.toFixed(1)}%</td>
          <td><span class="yoy-delta ${cls}" style="font-size:13px">${word} ${delta >= 0 ? '+' : ''}${delta.toFixed(1)} pp</span></td>
        </tr>`;
      }).join('');
      // Aggregate total-sample row at the bottom.
      const a1 = filteredRows().filter(r => r[COLS.year] === y1);
      const a2 = filteredRows().filter(r => r[COLS.year] === y2);
      const ai1 = a1.filter(r => r[COLS.is_valid] === 0).length;
      const ai2 = a2.filter(r => r[COLS.is_valid] === 0).length;
      const ap1 = a1.length ? ai1 * 100 / a1.length : 0;
      const ap2 = a2.length ? ai2 * 100 / a2.length : 0;
      const adelta = ap2 - ap1;
      const acls = Math.abs(adelta) < 0.5 ? 'flat' : (adelta > 0 ? 'up' : 'down');
      const aword = Math.abs(adelta) < 0.5 ? 'Flat' : (adelta > 0 ? 'Worse' : 'Better');
      const aggTr = `<tr style="font-weight:600;border-top:2px solid var(--line)">
        <td>Total samples</td>
        <td>${a1.length.toLocaleString()}</td><td><span class="badge invalid">${ai1}</span></td><td>${ap1.toFixed(1)}%</td>
        <td>${a2.length.toLocaleString()}</td><td><span class="badge invalid">${ai2}</span></td><td>${ap2.toFixed(1)}%</td>
        <td><span class="yoy-delta ${acls}" style="font-size:13px">${aword} ${adelta >= 0 ? '+' : ''}${adelta.toFixed(1)} pp</span></td>
      </tr>`;
      document.getElementById('yoy-grid').innerHTML = `<table>
        <thead><tr><th>Section</th><th>${y1} samples</th><th>${y1} Non-compliant</th><th>${y1} %</th>
          <th>${y2} samples</th><th>${y2} Non-compliant</th><th>${y2} %</th><th>Δ</th></tr></thead>
        <tbody>${tr}${aggTr}</tbody></table>`;
      return;
    }
    const sec = DATA.sections[currentSection];
    if (sec.years.length < 2) { card.style.display = 'none'; return; }
    card.style.display = '';
    const fr = filteredRows();   // #9 — YoY must reflect compliance/sector/GSO/search
    const stats = {};
    sec.years.forEach(y => {
      const sub = fr.filter(r => r[COLS.year] === y);
      const inv = sub.filter(r => r[COLS.is_valid] === 0).length;
      stats[y] = {total: sub.length, invalid: inv,
                  pct: sub.length ? inv * 100 / sub.length : 0};
    });
    const [y1, y2] = sec.years;
    const delta = stats[y2].pct - stats[y1].pct;
    const cls = Math.abs(delta) < 0.5 ? 'flat' : (delta > 0 ? 'up' : 'down');
    const word = Math.abs(delta) < 0.5 ? 'Flat' : (delta > 0 ? 'Worse' : 'Better');
    document.getElementById('yoy-grid').innerHTML = `
      <div class="yoy">
        <div class="yoy-cell"><div class="yoy-year">${y1}</div>
          <div class="yoy-fail">${stats[y1].pct.toFixed(1)}%</div>
          <div class="yoy-detail">${stats[y1].invalid.toLocaleString()} non-compliant / ${stats[y1].total.toLocaleString()} samples</div></div>
        <div class="yoy-cell">
          <div class="yoy-year">${y1} → ${y2}</div>
          <div class="yoy-delta ${cls}">${word} ${delta >= 0 ? '+' : ''}${delta.toFixed(1)} pp</div>
          <div class="yoy-detail">${cls === 'up' ? 'Deteriorating' : (cls === 'down' ? 'Improving' : 'Stable')}</div></div>
        <div class="yoy-cell"><div class="yoy-year">${y2}</div>
          <div class="yoy-fail">${stats[y2].pct.toFixed(1)}%</div>
          <div class="yoy-detail">${stats[y2].invalid.toLocaleString()} non-compliant / ${stats[y2].total.toLocaleString()} samples</div></div>
      </div>
    `;
  }

  function renderMunicipalities() {
    const rows = filteredRows();
    const mun = {};
    rows.forEach(r => {
      const m = r[COLS.municipality];
      if (!m) return;
      if (!mun[m]) mun[m] = {total: 0, valid: 0, invalid: 0, unknown: 0};
      mun[m].total++;
      if (r[COLS.is_valid] === 1) mun[m].valid++;
      else if (r[COLS.is_valid] === 0) mun[m].invalid++;
      else mun[m].unknown++;
    });
    const arr = Object.entries(mun).sort((a, b) => b[1].total - a[1].total);
    if (!arr.length) {
      Plotly.purge('chart-municipalities');
      document.getElementById('chart-municipalities').innerHTML = '<p class="muted">No sector data for this filter.</p>';
      return;
    }
    const names = arr.map(e => e[0]);
    const comp  = arr.map(e => e[1].valid);
    const inv   = arr.map(e => e[1].invalid);
    const unk   = arr.map(e => e[1].unknown);
    const failPcts = arr.map(e => e[1].total > 0 ? (e[1].invalid * 100 / e[1].total) : 0);
    // Outside-bar labels: total · fail %
    const totalLabels = arr.map((e, i) => `${e[1].total.toLocaleString()}  ·  ${failPcts[i].toFixed(1)}%`);
    Plotly.newPlot('chart-municipalities', [
      {x: names, y: comp, name: 'Compliant',     type: 'bar',
        marker:{color:'#059669', line:{color:'#047857',width:0.5}},
        hovertemplate: '<b>%{x}</b><br>Compliant: %{y:,}<extra></extra>'},
      {x: names, y: inv,  name: 'Non-compliant', type: 'bar',
        marker:{color:'#dc2626', line:{color:'#991b1b',width:0.5}},
        hovertemplate: '<b>%{x}</b><br>Non-compliant: %{y:,}<extra></extra>'},
      // Invisible trace to anchor outside-bar text on top of the stack
      {x: names, y: arr.map(e => 0), type: 'bar', showlegend: false, opacity: 0,
        text: totalLabels, textposition: 'outside', textfont:{size:11, color:'#1c2742'},
        hoverinfo: 'skip', cliponaxis: false},
    ], {barmode:'stack', paper_bgcolor:'transparent', plot_bgcolor:'transparent',
        font:{color:'#1c2742', family:'Inter, system-ui, sans-serif'},
        margin:{t:30, r:20, b:60, l:55},
        height: 360,
        xaxis: {tickangle: -25, tickfont:{size:12}, showline:true, linecolor:'#cbd5e1'},
        yaxis: {gridcolor:'#e5e7eb', title:{text:'Samples', font:{size:12}}, zeroline:true, zerolinecolor:'#cbd5e1'},
        legend: {orientation: 'h', y: -0.18, font:{size:11}},
        bargap: 0.30,
        hovermode: 'x unified',
       }, {responsive:true, displayModeBar:false});
  }

  function renderCategories() {
    const rows = filteredRows();
    const cat = {};
    // Fallback to gso_category when sample_category is empty (2024 chemistry
    // xlsx have no Sample Category column; the GSO bridge derives one from
    // sample_name so 2024 still renders).
    rows.forEach(r => {
      const c = r[COLS.sample_category] || r[COLS.gso_category];
      if (!c) return;
      if (!cat[c]) cat[c] = {total: 0, valid: 0, invalid: 0, unknown: 0};
      cat[c].total++;
      if (r[COLS.is_valid] === 1) cat[c].valid++;
      else if (r[COLS.is_valid] === 0) cat[c].invalid++;
      else cat[c].unknown++;
    });
    const arr = Object.entries(cat).sort((a,b) => b[1].invalid - a[1].invalid || b[1].total - a[1].total).slice(0, 20);
    if (!arr.length) {
      document.getElementById('tbl-categories').innerHTML = '<p class="muted">No sample-category data.</p>';
      return;
    }
    const tr = arr.map(([c, v]) => {
      // Use compliant + non-compliant as denominator so Fail % reflects
      // assessable samples only — Unknown / null verdicts are excluded
      // per user direction 2026-06-18.
      const assessable = v.valid + v.invalid;
      const p = assessable > 0 ? (v.invalid * 100 / assessable).toFixed(1) : '0.0';
      const cls = p >= 50 ? 'invalid' : p >= 25 ? 'unknown' : '';
      return `<tr><td>${escapeHtml(c)}</td><td>${v.total}</td>
        <td><span class="badge valid">${v.valid}</span></td>
        <td><span class="badge ${cls}">${v.invalid}</span></td>
        <td>${p}%</td></tr>`;
    }).join('');
    document.getElementById('tbl-categories').innerHTML = `<table>
      <thead><tr><th>Category</th><th>Total</th><th>Compliant</th><th>Non-compliant</th><th>Non-compliance %</th></tr></thead>
      <tbody>${tr}</tbody></table>`;
  }

  function renderDrilldown() {
    const rows = filteredRows();
    // Invalid first, then unknown, then valid
    const ordered = rows.slice().sort((a, b) => {
      const av = a[COLS.is_valid], bv = b[COLS.is_valid];
      const ra = av === 0 ? 0 : (av === null ? 1 : 2);
      const rb = bv === 0 ? 0 : (bv === null ? 1 : 2);
      if (ra !== rb) return ra - rb;
      return (b[COLS.date] || '').localeCompare(a[COLS.date] || '');
    }).slice(0, 300);

    if (!ordered.length) {
      document.getElementById('drilldown').innerHTML = '<p class="muted">No matching rows.</p>';
      return;
    }
    const showSection = isAllSections();
    const tr = ordered.map(r => {
      const v = r[COLS.is_valid];
      const badge = v === 1 ? '<span class="badge valid">Compliant</span>'
                   : v === 0 ? '<span class="badge invalid">Non-compliant</span>'
                   : '<span class="badge unknown">—</span>';
      const yr = r[COLS.year];
      const yrBadge = yr ? `<span class="badge y${yr}">${yr}</span>` : '';
      // Issue cell: clean up the failed-test name(s) using the same
      // FAIL_LABEL_MAP / sensory-skip rule as the chart, so the drilldown
      // and chart agree. Pesticide rows tag the concentration when relevant.
      let issueStr = '';
      const raw = r[COLS.failed_tests_derived] || r[COLS.invalid_test] || '';
      if (raw) {
        if (rowSection(r) === 'water_analysis') {
          // #12 — mirror the chart's space-split (see renderFail) so the
          // drilldown text matches the "Top non-compliant tests" chart.
          issueStr = splitWaterTests(raw).map(normaliseFail).filter(Boolean).join(', ');
        } else {
          issueStr = String(raw).split('|').map(s => s.trim())
            .map(t => t.replace(/^\[[^\]]+\]\s*/, ''))
            .map(normaliseFail)
            .filter(Boolean).join(' · ');
        }
      }
      if (rowSection(r) === 'pesticides' && r[COLS.pesticide_name]) {
        const conc = r[COLS.conc_ppm];
        const trace = (conc !== null && conc !== undefined && conc < 0.01);
        if (!trace) {
          const tag = (conc !== null && conc !== undefined) ? ` (${conc.toFixed(3)} ppm)` : '';
          issueStr = (issueStr ? issueStr + ' · ' : '') + r[COLS.pesticide_name] + tag;
        }
      }
      if (!issueStr && v === 0) issueStr = '<span class="muted">no test details on this row</span>';
      const issue = issueStr;
      // In All-sections mode, each row is a deduped sample with _sections list.
      const sectionCell = showSection
        ? `<td><span class="muted">${escapeHtml((r._sections || [rowSection(r)]).join(', '))}</span></td>`
        : '';
      return `<tr>
        <td>${yrBadge}</td>
        ${sectionCell}
        <td>${escapeHtml(r[COLS.date])}</td>
        <td>${escapeHtml(r[COLS.sample_id])}</td>
        <td class="ar">${escapeHtml(r[COLS.sample_name])}</td>
        <td>${escapeHtml(r[COLS.sample_category])}</td>
        <td class="ar">${escapeHtml(r[COLS.facility])}</td>
        <td class="ar">${escapeHtml(r[COLS.municipality])}</td>
        <td>${badge}</td>
        <td>${issue}</td>
      </tr>`;
    }).join('');
    document.getElementById('drilldown').innerHTML = `<table>
      <thead><tr><th></th>${showSection ? '<th>Tested in</th>' : ''}<th>Date</th><th>Sample ID</th><th>Name</th><th>Category</th>
        <th>Facility</th><th>Municipality</th><th>Verdict</th><th>Issue / test</th></tr></thead>
      <tbody>${tr}</tbody></table>`;
  }

  function renderAll() {
    try {
      const desc = isAllSections() ? ALL_DESC : DATA.sections[currentSection].desc;
      document.getElementById('section-desc').textContent = desc;
      // Muted subtitle line under the masthead removed 2026-07-01 (U3).
      const fRows = filteredRows();
      document.getElementById('filter-status').textContent =
        searchTerm ? `→ ${fRows.length.toLocaleString()} match` : '';
      renderGlobalBanner();
      renderSectionBar();
      renderYearBar();
      renderComplianceChips();
      renderSectorChips();
      renderGsoChips();
      renderKpis();
      renderYoY();
      renderMonthly();
      renderValidity();
      renderGsoCat();
      renderTopSubtypes();
      renderMapPlaceholder();
      renderFail();
      renderFacilities();
      renderCategories();
      renderMunicipalities();
      renderDrilldown();
    } catch (err) {
      console.error('renderAll failed:', err);
      const eb = document.getElementById('error-banner');
      eb.style.display = 'block';
      eb.textContent = 'Render error: ' + err.message;
    }
  }

  // Search input — live filter, debounced.
  let searchTimeout = null;
  document.getElementById('search').addEventListener('input', (e) => {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
      searchTerm = e.target.value.trim().toLowerCase();
      renderAll();
    }, 150);
  });

  // Reset filters → clears search box + year selection + section back to All.
  document.getElementById('btn-reset').addEventListener('click', () => {
    document.getElementById('search').value = '';
    searchTerm = '';
    currentYear = 'all';
    currentSection = '__all__';
    activeCompliance.clear();
    activeSectors.clear();
    activeGso.clear();
    renderAll();
  });

  // CSV export of the currently-filtered drilldown.
  document.getElementById('btn-csv').addEventListener('click', () => {
    const rows = filteredRows();
    const baseHeaders = ['year','date','year_month','sample_id','sample_name','sample_category',
                         'facility','municipality','district','is_valid','invalid_test',
                         'pesticide_name','conc_ppm','failed_tests_derived'];
    const headers = isAllSections() ? ['section'].concat(baseHeaders) : baseHeaders;
    const csvEscape = v => {
      if (v == null) return '';
      const s = String(v);
      if (s.includes(',') || s.includes('"') || s.includes('\n')) {
        return '"' + s.replace(/"/g, '""') + '"';
      }
      return s;
    };
    const lines = [headers.join(',')];
    rows.forEach(r => {
      const cells = baseHeaders.map(h => csvEscape(r[COLS[h]]));
      if (isAllSections()) cells.unshift(csvEscape(rowSection(r)));
      lines.push(cells.join(','));
    });
    const blob = new Blob(['﻿' + lines.join('\n')], {type: 'text/csv;charset=utf-8;'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    const yr = currentYear === 'all' ? 'all' : currentYear;
    const sec = isAllSections() ? 'ALL' : currentSection;
    const search = searchTerm ? '_' + searchTerm.replace(/[^a-z0-9]/g, '_').slice(0, 20) : '';
    a.href = url;
    a.download = `chemistry_${sec}_${yr}${search}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  });

  renderAll();
} catch (err) {
  console.error('Dashboard init failed:', err);
  const eb = document.getElementById('error-banner');
  eb.style.display = 'block';
  eb.textContent = 'Init error: ' + err.message;
}
</script>
</body></html>
"""


def _logo_data_uri() -> str:
    """Embed the Riyadh Municipality logo as a base64 data URI (in-tree asset,
    with a fallback to the legacy absolute path)."""
    import base64
    p = ROOT / "assets" / "riyadh_emblem.jpg"
    if not p.exists():
        p = Path("/home/bioinfo/Documents/Data-Analysis-Muhannad/amana.jpg")
    if not p.exists():
        return ""
    return "data:image/jpeg;base64," + base64.b64encode(p.read_bytes()).decode("ascii")


def main():
    from datetime import datetime
    payload = build_payload()
    html = TEMPLATE.replace("__DATA_JSON__", json.dumps(payload, ensure_ascii=False))
    html = html.replace("__LOGO_DATA_URI__", _logo_data_uri())
    # Stamp the build date + time into the masthead's meta strip
    stamp = datetime.now().strftime("%d %b %Y · %H:%M")
    html = html.replace(
        '<span class="val" id="build-stamp">—</span>',
        f'<span class="val" id="build-stamp">{stamp}</span>'
    )
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(html, encoding="utf-8")
    total = sum(s["n_total"] for s in payload["sections"].values())
    size_kb = OUT_HTML.stat().st_size // 1024
    yrs = payload["all_years"]
    print(f"wrote {OUT_HTML}  ({size_kb} KB, {total} rows across {len(payload['sections'])} sections, years {yrs})")


if __name__ == "__main__":
    main()
