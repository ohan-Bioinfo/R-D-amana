"""Build a self-contained interactive HTML dashboard from BOTH years stacked.

Reads:  cleaned/data2024.parquet + cleaned/data2025.parquet
Writes: reports/microbiology_dashboard.html

Adds a Year filter on top of the 2025 dashboard's chip set. 2024-only and
2025-only rows are both fully supported; columns missing in 2024 (sample_type,
facility_chain, municipality, etc.) just render as '—' / 'other' for those rows.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_2025 = ROOT / "schemas" / "lab_data_2025_v1.yaml"
OUT_HTML = ROOT / "reports" / "microbiology_dashboard.html"

# Canonical test names used by the exclude toggles. Both 2024 and 2025 spellings
# are listed so the toggle catches every sample regardless of which year it came
# from. The cleaner already canonicalises spelling variants to these forms.
TBC_NAMES = ["العد الكلي للبكتيريا", "العدد الكلي للبكتيريا"]
YEAST_MOULD_NAMES = ["الخمائر والاعفان"]
EXCLUDE_RAW_MEAT_SAMPLE_TYPES = ["raw_meat", "cooked_meat_poultry"]
EXCLUDE_ANIMAL_FEED_SAMPLE_TYPES = ["animal_feed"]

# Sector centroids — used as the bubble location for sector-only rows that
# have no specific sub-municipality. Keyed by the 5-sector English labels
# that derive_sector produces.
SECTOR_CENTROIDS: dict[str, tuple[float, float]] = {
    "East":    (24.7275, 46.7840),
    "North":   (24.8400, 46.6900),
    "West":    (24.6300, 46.6033),
    "Central": (24.6740, 46.6950),
    "South":   (24.5470, 46.7800),
    "Special": (24.6877, 46.7219),   # private samples (العينات الخاصة) — Riyadh centre
}


# 5-sector canonical mapping (user direction 2026-07-09): mirrors the chemistry
# taxonomy — the five central districts form their own Central sector rather
# than being redistributed into the compass sectors.
#   الملز / المعذر / العليا / الشميسي / البطحاء → Central
SECTOR_5_OF_SUBMUNI: dict[str, str] = {
    # North
    "الشمال":   "North",
    # East
    "الروضة":   "East",
    "الشرق":    "East",
    # West
    "عرقة":     "West",
    "نمار":     "West",
    "العريجاء": "West",
    # Central
    "الملز":    "Central",
    "المعذر":   "Central",
    "العليا":   "Central",
    "الشميسي":  "Central",
    "البطحاء":  "Central",
    # South
    "الشفا":    "South",
    "العزيزية": "South",
    "الحاير":   "South",
    "النسيم":   "South",
    "السلي":    "South",
}
# Arabic sector-only labels (no sub-municipality) → 5-sector English. The
# Central sector ('فرع أمانة في المنطقة الوسطى', 'وسط الرياض') now maps to
# Central (restored to match the chemistry 5-sector taxonomy).
SECTOR_5_OF_RAW_SECTOR: dict[str, str | None] = {
    "فرع أمانة في الشرق":           "East",
    "فرع أمانة في الشمال":          "North",
    "فرع أمانة في الغرب":           "West",
    "فرع أمانة في الجنوب":          "South",
    "فرع أمانة في المنطقة الوسطى":  "Central",
    "قطاع الشمال":                  "North",
    "وسط الرياض":                   "Central",
    "القطاع وسط الرياض":            "Central",
}

# Map sector to English label everywhere downstream. Order = canonical
# taxonomy order used by sector selectors and KPI charts.
SECTORS_5 = ["East", "North", "West", "Central", "South", "Special"]


def derive_sector_5(municipality, raw_sector):
    """Return one of East/West/North/Central/South/Special or None.
    Priority: sub-municipality (precise) over sector-only label; private
    samples (عينة خاصة) form the Special sector."""
    if municipality is not None and not (isinstance(municipality, float) and pd.isna(municipality)):
        s = str(municipality).strip()
        if s == "عينة خاصة":
            return "Special"
        if s in SECTOR_5_OF_SUBMUNI:
            return SECTOR_5_OF_SUBMUNI[s]
    if raw_sector is not None and not (isinstance(raw_sector, float) and pd.isna(raw_sector)):
        s = str(raw_sector).strip()
        if s in SECTOR_5_OF_RAW_SECTOR:
            return SECTOR_5_OF_RAW_SECTOR[s]
    return None


# 2025-source rows have a `sample_type` but no GSO classification (the 2025
# pipeline doesn't carry gso_code). To put 2024 and 2025 on equal footing for
# product-level analysis, derive a pseudo-GSO category for 2025 from
# sample_type — using the same English category names as the 2024 GSO
# vocabulary so both years line up in the same chart/filter.
# (User-confirmed mapping 2026-06-14.)
# Arabic organism / test transliteration variants — merge spellings so the
# chip filter and bar charts treat them as a single organism. Map every
# observed variant to its canonical form (= the cleaner Arabic spelling).
# User direction 2026-06-14: "بايلس سيريس (29)" and "بايلص سيرز (31)" are
# the same Bacillus cereus and should be one chip.
ORGANISM_NORMALIZE: dict[str, str] = {
    # Bacillus cereus
    "باصلص سيرز":         "باسيلس سيريس",
    # Total bacterial count — العدد (correct) vs العد (typo missing د)
    "العد الكلي للبكتيريا": "العدد الكلي للبكتيريا",
    # Yeasts & moulds — multiple spacings + one orphan fragment
    "خمائر و اعفان":      "الخمائر والاعفان",
    "خمائر واعفان":       "الخمائر والاعفان",
    "والاعفان":           "الخمائر والاعفان",
    # Enterobacteriaceae — missing ي variant
    "انتروباكتريسي":      "انتيروباكتريسي",
    # Pseudomonas — typo extra م
    "سيدومومناس":         "سيدوموناس",
    # E. coli — missing space
    "ايشريشياكولاي":      "ايشيريشيا كولاي",
}


def normalize_organism(name):
    """Map a raw organism / test name to its canonical Arabic spelling."""
    if name is None:
        return None
    return ORGANISM_NORMALIZE.get(name, name)


# Reverse bridge: GSO category → sample_type. Many sample_types map to one
# GSO category; for the reverse we pick the most representative single type
# (e.g. Meat & Poultry → cooked_meat_poultry, the more common 2025 form).
# Used to derive a sample_type proxy for 2024 rows so the Severity-by-
# sample-type heatmap spans both years.
GSO_TO_SAMPLE_TYPE: dict[str, str] = {
    "Fruit and Vegetables":                                 "produce",
    "Dairy Products":                                       "dairy",
    "Tomato Concentrates, Sauces, Vinegar, Spices and Herbs": "sauce_condiment",
    "Ready to Eat Foods":                                   "prepared_meal",
    "Meat, Poultry and its Products":                       "cooked_meat_poultry",
    "Chocolate, Sweets and their Ingredients":              "sweets_bakery",
    "Beverages":                                            "beverage",
    "Drinking Water":                                       "water",
    "Cereals; Legumes and their Products":                  "sweets_bakery",
    "Jelly, Jam and Marmalade":                             "sweets_bakery",
    "Fish and Shellfish their Products":                    "cooked_meat_poultry",
    "Egg and Egg Products":                                 "dairy",
    "Fats and Oils":                                        "other",
    "Miscellaneous Foods":                                  "other",
    "Infants, Children and Certain Categories of Dietetic Foods": "other",
    "Animal Feed":                                          "animal_feed",
    "Environmental Swabs":                                  "swab",
}


# Arabic-keyword → GSO 1016 category lookup, used as a 3rd-tier fallback
# when a row has neither native GSO nor a sample_type bridge. ORDER MATTERS —
# the first matching keyword wins (so equipment-swab tokens are checked before
# food tokens that might appear in equipment names).
NAME_KEYWORDS_TO_GSO: list[tuple[list[str], str]] = [
    # equipment / environmental — check first so "طاولة تقطيع اجبان" doesn't
    # match "جبن" before "طاولة"
    (['مسحة','مسح ','طاولة','ثلاجة','فرامة','قطاعة','عصارة','خلاط','مفرمة'], 'Environmental Swabs'),
    (['ماء','مياه','مياة'], 'Drinking Water'),
    (['علف','أعلاف'], 'Animal Feed'),
    (['بيض','بيوض'], 'Egg and Egg Products'),
    (['سمك','تونة','كابوريا','جمبري','ربيان','روبيان','سبيط','حبار','محار','أسماك','اسماك'], 'Fish and Shellfish their Products'),
    (['حليب','لبن','زبادي','جبن','جبنة','أجبان','زبدة','قشطة','لبنة','جبنه','مرتديلا','حلوم','كريمة','كريم','قشدة','تشيز','شيدر'], 'Dairy Products'),
    (['لحم','لحوم','دجاج','كباب','شاورما','هامبرغر','نقانق','سجق','ديك رومي','بسطرمة','كفتة'], 'Meat, Poultry and its Products'),
    (['عصير','مشروب','شاي','قهوة','كوكا','بيبسي','كركدية','نسكافيه'], 'Beverages'),
    (['شوكولا','بسكويت','كعك','كيك','حلوى','حلويات','حلا','معمول','بقلاوة','كنافة','بسبوسة','حلويه','بقلاوه','صنوبر','شيرة','مهلبية','بيتي فور'], 'Chocolate, Sweets and their Ingredients'),
    (['مربى','جلي','مرملاد'], 'Jelly, Jam and Marmalade'),
    (['عسل الأطفال','حلويات الأطفال','حليب اطفال','حليب أطفال'], 'Infants, Children and Certain Categories of Dietetic Foods'),
    (['زيت','زيوت','سمن','دهن'], 'Fats and Oils'),
    (['خبز','عجين','معكرون','مكرون','رز','أرز','ارز','عدس','فاصوليا','فول','بقول','حبوب','شوفان','نشا','قمح','طحين','بليلة','ذرة','فشار','فريكة','شابور','وافل'], 'Cereals; Legumes and their Products'),
    (['طماطم','خيار','خس','بصل','فلفل','جزر','بطاطا','بطاطس','ثوم','بقدونس','نعناع','كزبرة','خضار','خضروات','فواكه','تفاح','موز','برتقال','عنب','مانجو','مانجا','فراولة','ليمون','رمان','بطيخ','شمام','تين','مشمش','كرز','أناناس','افوكادو','بروكلي','قرنبيط','زعتر','جرجير','جيرجير','بنجر','شمر','ملفوف','كرنب','قرع','كوسا','شمندر','باذنجان','هلابينو','فجل','كرفس','خوخ','بامية'], 'Fruit and Vegetables'),
    (['صوص','شطة','مايونيز','كاتشب','خل','بهارات','توابل','مخلل','معجون طماطم','كركم','قرفة','صوصات','تتبيلة','باربكيو'], 'Tomato Concentrates, Sauces, Vinegar, Spices and Herbs'),
    (['ايدام','مصقع','ملوخية','حواوش','ممبار','تبولة','سلطة','حمص','متبل','بابا غنوج','باباغنوج','محمرة','محشي','منسف','مقلوبة','كبة','ورق عنب','فطيرة','معجنات','شوربة','شربة','صيادية','وجبة','وجبه','فلافل','شكشوكة','مكدوس'], 'Ready to Eat Foods'),
]


def classify_sample_name(name) -> str | None:
    """Map an Arabic sample_name to a GSO 1016 category (or None)."""
    if name is None: return None
    try:
        if pd.isna(name): return None
    except Exception: pass
    s = str(name).strip()
    if not s: return None
    for kws, cat in NAME_KEYWORDS_TO_GSO:
        for kw in kws:
            if kw in s: return cat
    return None


SAMPLE_TYPE_TO_GSO: dict[str, str] = {
    "produce":             "Fruit and Vegetables",
    "dairy":               "Dairy Products",
    "sauce_condiment":     "Tomato Concentrates, Sauces, Vinegar, Spices and Herbs",
    "prepared_meal":       "Ready to Eat Foods",
    "raw_meat":            "Meat, Poultry and its Products",
    "cooked_meat_poultry": "Meat, Poultry and its Products",
    "fish":                "Fish and Shellfish their Products",
    "egg":                 "Egg and Egg Products",
    "cereals":             "Cereals; Legumes and their Products",
    "sweets_bakery":       "Chocolate, Sweets and their Ingredients",
    "beverage":            "Beverages",
    "water":               "Drinking Water",
    "swab":                "Environmental Swabs",
    "animal_feed":         "Animal Feed",
    # "other" deliberately unmapped (was → Miscellaneous) so those rows fall
    # through to classify_sample_name() and get a real category by name where
    # possible (Muhannad 2026-07-09).
}


# Per-sample_id GSO-category overrides — Muhannad's micro sheet-8 targets
# (2026-07-09). Authoritative: applied BEFORE the native/sample_type/name
# derivation. Handles categories sample_type cannot express (Fish, Cereals,
# Fats) and his specific per-sample calls. Keyed by lowercased sample_id.
def _load_gso_corrections() -> dict:
    import csv
    p = ROOT / "scripts" / "gso_category_corrections.csv"
    out = {}
    if p.exists():
        with p.open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                sid = (row.get("sample_id") or "").strip().lower()
                cat = (row.get("gso_category") or "").strip()
                if sid and cat:
                    out[sid] = cat
    return out

GSO_CORRECTIONS = _load_gso_corrections()


def load_test_classification() -> dict:
    """Read pathogen/indicator sets from the 2025 schema YAML."""
    with SCHEMA_2025.open("r", encoding="utf-8") as f:
        schema = yaml.safe_load(f)
    tc = schema["test_classification"]
    return {"pathogen": list(tc["pathogen"]), "indicator": list(tc["indicator"])}


DATA_COLS = [
    "year",          # 0  2024 / 2025
    "date",          # 1
    "year_month",    # 2
    "quarter",       # 3
    "dow",           # 4
    "chain",         # 5
    "facility",      # 6
    "municipality",  # 7
    "mun_type",      # 8
    "sector",        # 9
    "valid",         # 10
    "failure",       # 11
    "pathogen",      # 12
    "severity",      # 13
    "n_failed",      # 14
    "ro_count",      # 15
    "failed_tests",  # 16
    "gso_category",  # 17  English category name (e.g., 'Dairy Products') — also the sample vocabulary
    "gso_product",   # 18  English product name (e.g., 'Hard and semi–hard cheese')
    "gso_code",      # 19  canonical code (e.g., 'A-13')
    "panel_complete",# 20  True/False/null — was the full GSO panel run? (2024-only)
    "lab_disagree",  # 21  True/False/null — does lab verdict disagree with GSO limit?
    "sample_name",   # 22  Specific sample name (e.g. تبولة, جبنة فيتا) for subtype rankings
]


def _val(x):
    if x is None:
        return None
    try:
        if pd.isna(x):
            return None
    except (TypeError, ValueError):
        pass
    return x


def build_data(df: pd.DataFrame) -> dict:
    # Re-derive severity from the YAML test_classification at dashboard-build
    # time so reclassifications (e.g. Pseudomonas → pathogen per the
    # 2026-06-18 user direction) take effect without re-running the cleaner.
    # The cleaner's stored severity_tier is used as a fallback only when
    # no failed_tests list exists on the row.
    tc = load_test_classification()
    pathogen_set = {normalize_organism(t) for t in tc["pathogen"]}

    def _derive_severity(failed_list):
        if not failed_list:
            return "none", False
        path_distinct = {t for t in failed_list if t in pathogen_set}
        has_pathogen = bool(path_distinct)
        if len(path_distinct) >= 2:
            return "multi_pathogen", True
        if len(path_distinct) == 1:
            return "pathogen", True
        return "indicator_only", False

    rows: list[list] = []
    for r in df.itertuples(index=False):
        # severity_tier='none' = fully compliant samples. We KEEP these in
        # the payload so the headline KPIs (Total Samples, Compliance Rate,
        # etc.) can count them. The charts auto-filter them out via the
        # `filteredActive` set in applyFilters, so the visual behaviour
        # stays focused on severity events as per the 2026-06-14 directive.
        sev_raw = _val(r.severity_tier) or "none"
        sd = r.sampling_date
        date_str = sd.strftime("%Y-%m-%d") if pd.notna(sd) else None
        valid = None
        if pd.notna(r.is_valid):
            valid = 1 if bool(r.is_valid) else 0
        failure_b = 0
        if pd.notna(r.is_failure):
            failure_b = 1 if bool(r.is_failure) else 0
        pathogen_b = 0
        if pd.notna(r.has_pathogen_failure):
            pathogen_b = 1 if bool(r.has_pathogen_failure) else 0
        # Normalize Arabic organism variants (typos / spacing) to canonical
        # spellings, then dedupe so a row that listed both 'باصلص سيرز' and
        # 'باسيلس سيريس' counts once, not twice.
        if r.invalid_tests is not None:
            seen, failed = set(), []
            for t in r.invalid_tests:
                tn = normalize_organism(t)
                if tn not in seen:
                    seen.add(tn)
                    failed.append(tn)
        else:
            failed = []
        # Re-derive severity from the current YAML classification (overrides
        # whatever the cleaner stored). When failed_tests is empty, fall
        # back to the cleaner's stored value (handles edge cases where the
        # cleaner had richer info than the dashboard payload).
        if failed:
            sev_raw, pathogen_bool = _derive_severity(failed)
            pathogen_b = 1 if pathogen_bool else 0
        # 3-tier GSO classification (applied to every year for consistency):
        #   1. Native GSO category from the parquet (best — direct from source)
        #   2. Bridge from sample_type (2025 — derived from category mapping)
        #   3. Keyword-classify the Arabic sample_name (catches 2023/2024 gaps)
        # 0. Per-sample_id override (Muhannad's targets) — wins over everything.
        _sid = _val(getattr(r, "sample_id", None))
        gso_cat = GSO_CORRECTIONS.get(str(_sid).strip().lower()) if _sid is not None else None
        if gso_cat is None:
            gso_cat = _val(getattr(r, "gso_category_name_en", None))
        if gso_cat is None:
            st = _val(getattr(r, "sample_type", None))
            if st is not None:
                gso_cat = SAMPLE_TYPE_TO_GSO.get(st)
        if gso_cat is None:
            gso_cat = classify_sample_name(_val(getattr(r, "sample_name", None)))
        # Truly-unclassified rows go to Miscellaneous so they don't disappear
        # from any chart's denominator. The unclassified count is tracked
        # via the data_quality_flags column already.
        if gso_cat is None:
            gso_cat = 'Miscellaneous Foods'
        # The GSO category IS the sample vocabulary now — one column (was
        # duplicated as `sample_type`; consolidated 2026-07-16).
        rows.append([
            int(r.year),
            date_str,
            _val(r.year_month),
            int(r.quarter) if pd.notna(r.quarter) else None,
            int(r.day_of_week) if pd.notna(r.day_of_week) else None,
            _val(r.facility_chain),
            _val(r.facility_name),
            _val(r.municipality),
            _val(r.municipality_type),
            # 5-sector taxonomy (East/North/West/Central/South). Derived from the
            # sub-municipality when present, else from the raw sector label.
            derive_sector_5(_val(r.municipality), _val(r.sector)),
            valid,
            failure_b,
            pathogen_b,
            sev_raw,
            int(r.n_failed_tests) if pd.notna(r.n_failed_tests) else 0,
            int(r.chain_invalid_count_90d) if pd.notna(r.chain_invalid_count_90d) else 0,
            failed,
            gso_cat,
            _val(getattr(r, "gso_product_name_en", None)),
            _val(getattr(r, "gso_code_canonical", None)),
            (None if pd.isna(getattr(r, "gso_panel_complete", None))
             else (1 if bool(getattr(r, "gso_panel_complete")) else 0)),
            (None if pd.isna(getattr(r, "gso_lab_vs_gso_disagree", None))
             else (1 if bool(getattr(r, "gso_lab_vs_gso_disagree")) else 0)),
            _val(getattr(r, "sample_name", None)),  # specific subtype name
        ])
    return {"cols": DATA_COLS, "rows": rows}


def build_facets(df: pd.DataFrame) -> dict:
    months = sorted([m for m in df["year_month"].dropna().unique().tolist()])
    # sample_types is now the same vocabulary as the GSO 1016 categories
    # (see build_data — sample_type slot carries the GSO category name so
    # all years share one taxonomy). Built later, sorted by combined
    # volume, so a single list serves both the heatmap and any sample-type
    # filter that gets re-added later.
    sample_types = []  # populated below once gso_cats is computed
    # Severity = "none" dropped per user direction 2026-06-14 — fully
    # compliant samples are excluded from the dashboard entirely, so the
    # filter offers only the 3 actual severity tiers.
    severity = ["indicator_only", "pathogen", "multi_pathogen"]
    years = sorted([int(y) for y in df["year"].dropna().unique().tolist()])
    # 5-sector canonical order (East → North → West → Central → South).
    # All 5 sectors are always listed so empty ones still appear (at zero).
    sectors = list(SECTORS_5)
    # GSO categories — combine the 15 real 2024 categories with the 12
    # 2025-derived categories (from sample_type) for one cross-year list.
    cat_counts: dict[str, int] = {}
    if "gso_category_name_en" in df.columns:
        for c, n in df["gso_category_name_en"].dropna().value_counts().items():
            cat_counts[c] = cat_counts.get(c, 0) + int(n)
    if "sample_type" in df.columns:
        for st, n in df["sample_type"].dropna().value_counts().items():
            mapped = SAMPLE_TYPE_TO_GSO.get(st)
            if mapped:
                cat_counts[mapped] = cat_counts.get(mapped, 0) + int(n)
    gso_cats = [c for c, _ in sorted(cat_counts.items(), key=lambda x: -x[1])]
    # GSO products list, sorted alphabetically, with code in label for clarity.
    gso_products = []
    if "gso_product_name_en" in df.columns and "gso_code_canonical" in df.columns:
        pair = df[["gso_product_name_en", "gso_code_canonical"]].dropna().drop_duplicates()
        pair = pair.sort_values("gso_code_canonical")
        gso_products = [
            {"name": p, "code": c, "label": f"{c} · {p}"}
            for p, c in zip(pair["gso_product_name_en"], pair["gso_code_canonical"])
        ]
    audit_counts = {
        "panel_incomplete": (
            int((df.get("gso_panel_complete", pd.Series([])) == False).sum())
            if "gso_panel_complete" in df.columns else 0
        ),
        "lab_disagree": (
            int((df.get("gso_lab_vs_gso_disagree", pd.Series([])) == True).sum())
            if "gso_lab_vs_gso_disagree" in df.columns else 0
        ),
    }
    # Default date range clamps to the year boundaries of years actually present
    # so a stray 2022 typo from the source doesn't widen the picker by 14 months.
    sensible_min = pd.Timestamp(f"{min(years)}-01-01")
    sensible_max = pd.Timestamp(f"{max(years)}-12-31")
    actual_min = df["sampling_date"].min()
    actual_max = df["sampling_date"].max()
    default_min = max(actual_min, sensible_min) if pd.notna(actual_min) else sensible_min
    default_max = min(actual_max, sensible_max) if pd.notna(actual_max) else sensible_max
    # Pathogen chips, sorted by failure-count in actual data (most common first).
    # Zero-failure pathogens still appear at the tail so the taxonomy is complete.
    # Variants from the YAML schema get collapsed via ORGANISM_NORMALIZE so each
    # organism is offered as a single chip (no more Bacillus-cereus duplicates).
    test_classes = load_test_classification()
    canonical_pathogens: list[str] = []
    canonical_indicators: list[str] = []
    seen_p, seen_i = set(), set()
    for t in test_classes["pathogen"]:
        c = normalize_organism(t)
        if c not in seen_p:
            seen_p.add(c); canonical_pathogens.append(c)
    for t in test_classes["indicator"]:
        c = normalize_organism(t)
        if c not in seen_i:
            seen_i.add(c); canonical_indicators.append(c)
    test_classes = {"pathogen": canonical_pathogens, "indicator": canonical_indicators}
    pathogen_set = set(canonical_pathogens)
    indicator_set = set(canonical_indicators)

    # Count failures per organism (pathogen + indicator). DEDUPE per-row
    # using a set, so a row that listed two spelling variants of the same
    # organism (e.g. 'خمائر و اعفان' + 'خمائر واعفان') counts once — matching
    # the row-deduped behaviour of build_data so the chip count = the click
    # result exactly.
    failure_counts: dict[str, int] = {}
    for failed_list in df.get("invalid_tests", pd.Series([], dtype=object)):
        if failed_list is None:
            continue
        seen = set()
        for t in failed_list:
            tn = normalize_organism(t)
            if tn in seen: continue
            seen.add(tn)
            if tn in pathogen_set or tn in indicator_set:
                failure_counts[tn] = failure_counts.get(tn, 0) + 1
    pathogens_ordered = sorted(canonical_pathogens,
                                key=lambda t: (-failure_counts.get(t, 0), t))
    indicators_ordered = sorted(canonical_indicators,
                                 key=lambda t: (-failure_counts.get(t, 0), t))
    pathogen_chips = [
        {"name": t, "count": failure_counts.get(t, 0), "class": "pathogen"}
        for t in pathogens_ordered
    ]
    indicator_chips = [
        {"name": t, "count": failure_counts.get(t, 0), "class": "indicator"}
        for t in indicators_ordered
    ]
    return {
        "years": years,
        "months": months,
        "severity": severity,
        "sectors": sectors,
        "test_classes": test_classes,
        "pathogen_chips": pathogen_chips,
        "indicator_chips": indicator_chips,
        "gso_categories": gso_cats,
        "gso_products": gso_products,
        "audit_counts": audit_counts,
        "map_centroids": {
            "sectors":        {name: list(coords) for name, coords in SECTOR_CENTROIDS.items()},
            "default_center": [24.7000, 46.7000],
            "default_zoom":   9.5,
        },
        "exclude_constants": {
            "tbc_names": TBC_NAMES,
            "yeast_mould_names": YEAST_MOULD_NAMES,
            "raw_meat_sample_types": EXCLUDE_RAW_MEAT_SAMPLE_TYPES,
            "animal_feed_sample_types": EXCLUDE_ANIMAL_FEED_SAMPLE_TYPES,
        },
        "date_min": default_min.strftime("%Y-%m-%d"),
        "date_max": default_max.strftime("%Y-%m-%d"),
        "row_count": len(df),
    }


TEMPLATE = r"""<!DOCTYPE html>
<html lang="en" dir="ltr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>أمانة منطقة الرياض · R&amp;D Microbiology Decision Dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;900&family=IBM+Plex+Sans+Arabic:wght@300;400;500;600&family=DM+Mono:wght@400;500&family=Cormorant+Garamond:ital,wght@1,500&display=swap" rel="stylesheet">
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js" charset="utf-8"></script>
<style>
/* ═══════════════════════════════════════════════════════════════════
   Riyadh Municipal Editorial — theme system
   Palette: Najdi heritage green + warm sand + burnished gold
   Type:    Tajawal · IBM Plex Sans Arabic · DM Mono · Cormorant Garamond
   ═══════════════════════════════════════════════════════════════════ */
:root {
  --green-900:#0a3d24; --green-700:#0e5c36; --green-500:#22853f; --green-100:#dcefe1;
  --gold-700:#9a7b2a;  --gold-500:#c8a85a;  --gold-200:#f0e3bf;
  --clay-700:#7a2616;  --clay-500:#a8331a;  --clay-100:#f7d9d0;
  --sand-50:#faf6ee;   --sand-100:#f4ecde;  --sand-200:#e8dcc4;  --sand-300:#d4c5a4;
  --ink-900:#1a1f2c;   --ink-700:#3d4256;   --ink-500:#6c6f7e;

  --bg: var(--sand-50); --bg-2: #fffdf8; --bg-3: var(--sand-100);
  --fg: var(--ink-900); --muted: var(--ink-500); --line: var(--sand-200);
  --accent: var(--green-700); --good: var(--green-500); --warn: var(--gold-700);
  --bad: var(--clay-500); --crit: var(--clay-700); --pathogen: var(--clay-500);

  /* Year accents — heritage palette */
  --year23: #b96f3a;   /* copper */
  --year24: var(--gold-500);  /* gold */
  --year25: var(--green-700); /* green */

  --shadow: 0 1px 0 rgba(154,123,42,0.04), 0 4px 12px -4px rgba(10,61,36,0.08);
  --logo: url("__LOGO_DATA_URI__");
  --najdi-pattern: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 60 60' opacity='0.06'><path d='M30 0 L60 30 L30 60 L0 30 Z M30 12 L48 30 L30 48 L12 30 Z' fill='%23faf6ee'/></svg>");
}
* { box-sizing: border-box; }
html, body { background: var(--sand-50); color: var(--ink-900); margin: 0;
  font-family: 'IBM Plex Sans Arabic', 'Tajawal', 'Tahoma', system-ui, sans-serif;
  font-size: 14px; font-feature-settings: 'kern', 'liga', 'tnum'; }
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
.masthead .titleblock { flex: 1; min-width: 0; }
.masthead .title-ar { font-family: 'Tajawal', sans-serif; font-weight: 700;
  font-size: 22px; letter-spacing: 0.5px; line-height: 1.1; direction: rtl;
  color: #fffdf8; margin: 0; text-shadow: 0 1px 2px rgba(0,0,0,0.2); }
.masthead .title-en { font-family: 'Tajawal', sans-serif; font-weight: 500;
  font-size: 13px; letter-spacing: 4px; text-transform: uppercase;
  color: var(--gold-200); margin: 6px 0 0; opacity: 0.92; }
.masthead .subtitle-block { font-family: 'Cormorant Garamond', serif;
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

.page-body { padding: 0 30px; max-width: 1600px; margin: 0 auto; }

h1 { font-family: 'Tajawal', sans-serif; font-size: 22px; margin: 0 0 6px;
  font-weight: 700; letter-spacing: 0.3px; display: none; }
h2 { font-family: 'Tajawal', sans-serif; font-size: 12px; margin: 0 0 12px;
  font-weight: 600; color: var(--gold-700); text-transform: uppercase;
  letter-spacing: 2.2px; }
h2::before { content: "۞"; color: var(--gold-500); margin-right: 8px;
  font-size: 14px; opacity: 0.6; }
.subtitle { color: var(--ink-500); font-size: 13px; margin: 0 0 18px;
  font-family: 'Cormorant Garamond', serif; font-style: italic; }
.year-bar { display: flex; align-items: center; gap: 14px; padding: 12px 18px;
  background: var(--bg-2); border: 1px solid var(--line); border-radius: 12px;
  margin-bottom: 14px; position: sticky; top: 8px; z-index: 100;
  backdrop-filter: blur(8px); background: rgba(248,250,252,0.95); }
.year-bar-label { font-size: 12px; color: var(--muted); text-transform: uppercase;
  letter-spacing: 1.5px; font-weight: 600; }
.year-bar .chips .chip { padding: 6px 16px; font-size: 13px; font-weight: 500; }
.year-bar .filter-pill { padding: 4px 10px; background: var(--bg-3);
  border-radius: 999px; font-size: 11px; color: var(--muted);
  border: 1px solid var(--line); }
.year-bar .filter-pill.active { background: #fef3c7; color: #92400e;
  border-color: #fbbf24; font-weight: 600; }
.year-bar .btn-reset { padding: 7px 16px; background: var(--accent); color: #fff;
  border: none; font-weight: 600; letter-spacing: 0.3px; cursor: pointer;
  border-radius: 8px; font-size: 12px; transition: all 0.15s; }
.year-bar .btn-reset:hover { background: #0f1a3d; transform: translateY(-1px); }
.year-bar .btn-reset:disabled { background: #cbd5e1; cursor: not-allowed; transform: none; }
.card.hidden-by-year { display: none; }
.year-required-badge { display: inline-block; margin-left: 8px; padding: 2px 8px;
  background: #ede9fe; color: #5b21b6; border-radius: 999px;
  font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }

.filter-section { margin-bottom: 14px; background: var(--bg-2);
  border: 1px solid var(--line); border-radius: 12px; overflow: hidden;
  box-shadow: var(--shadow); }
.filter-section .section-title { padding: 10px 18px; font-size: 11px;
  text-transform: uppercase; letter-spacing: 1.5px; font-weight: 600;
  color: var(--muted); background: var(--bg-3);
  border-bottom: 1px solid var(--line); }
.filter-section .section-title .section-note { font-weight: 400; letter-spacing: 0.5px;
  text-transform: none; color: var(--muted); opacity: 0.7; margin-left: 6px; }
.filter-section .filters { margin-bottom: 0; padding: 14px 18px;
  border: none; background: transparent; }

.badge-count { display: inline-block; margin-left: 6px; padding: 1px 7px;
  background: var(--bg-3); border-radius: 10px; font-size: 11px;
  font-weight: 500; color: var(--fg); }
.toggle.active .badge-count { background: rgba(255,255,255,0.3); color:#fff; }
.filters { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 14px; padding: 16px; background: var(--bg-2); border: 1px solid var(--line);
  border-radius: 12px; margin-bottom: 22px; box-shadow: var(--shadow); }
.filter-group label { display: block; font-size: 11px; color: var(--muted);
  text-transform: uppercase; letter-spacing: 1px; margin-bottom: 6px; font-weight: 500; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; }
.chip { padding: 4px 11px; background: var(--bg-3); border: 1px solid var(--line);
  border-radius: 999px; font-size: 12px; cursor: pointer; user-select: none;
  transition: all 0.15s; color: var(--fg); }
.chip:hover { border-color: var(--accent); background:#fff; }
.chip.active { background: var(--accent); border-color: var(--accent); color: #fff;
  font-weight: 600; }
.chip[data-value="2023"].active { background: var(--year23); border-color: var(--year23); color:#fff; }
.chip[data-value="2024"].active { background: var(--year24); border-color: var(--year24); color:#fff; }
.chip[data-value="2025"].active { background: var(--year25); border-color: var(--year25); color:#fff; }
.toggle-row { display: flex; gap: 12px; flex-wrap: wrap; }
.toggle { padding: 6px 12px; background: #fff; border: 1px solid var(--line);
  border-radius: 8px; font-size: 12px; cursor: pointer; user-select: none; color: var(--fg); }
.toggle.active { background: var(--pathogen); border-color: var(--pathogen); color: #fff; }
select { width: 100%; padding: 7px 10px; background: #fff; color: var(--fg);
  border: 1px solid var(--line); border-radius: 8px; font-size: 13px; font-family: inherit; }
select[multiple] { height: 90px; }
input[type=date] { width: 100%; padding: 7px 10px; background: #fff;
  color: var(--fg); border: 1px solid var(--line); border-radius: 8px;
  font-size: 13px; font-family: inherit; }
.date-range { display: flex; gap: 8px; }
.date-range input { flex: 1; }
.btn { padding: 6px 12px; background: #fff; border: 1px solid var(--line);
  border-radius: 8px; color: var(--fg); cursor: pointer; font-size: 12px; }
.btn:hover { border-color: var(--accent); background: var(--bg-3); }
.kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 14px; margin-bottom: 22px; }
.kpi { padding: 16px 18px; background: var(--bg-2); border: 1px solid var(--line);
  border-radius: 12px; position: relative; overflow: hidden; box-shadow: var(--shadow); }
.kpi::before { content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 4px; background: var(--accent); }
.kpi.good::before { background: var(--good); }
.kpi.warn::before { background: var(--warn); }
.kpi.bad::before { background: var(--bad); }
.kpi.crit::before { background: var(--crit); }
.kpi .label { color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 6px; }
.kpi .value { font-size: 28px; font-weight: 600; line-height: 1; }
.kpi .sub { color: var(--muted); font-size: 11px; margin-top: 4px; }
.kpi .yearly { display: flex; gap: 10px; margin-top: 6px; font-size: 11px; }
.kpi .yearly span { padding: 1px 6px; border-radius: 4px; }
.kpi .y23 { background: #fce7f3; color: var(--year23); }
.kpi .y24 { background: #ede9fe; color: var(--year24); }
.kpi .y25 { background: #dbeafe; color: var(--year25); }
.grid { display: grid; gap: 16px; grid-template-columns: 1fr 1fr; }
.grid > .full { grid-column: 1 / -1; }
.card { background: var(--bg-2); border: 1px solid var(--line); border-radius: 12px; padding: 16px;
  box-shadow: var(--shadow); }
.card .chart { width: 100%; min-height: 280px; }
.card.tall .chart { min-height: 420px; }
@media (max-width: 900px) { .grid { grid-template-columns: 1fr; } }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { padding: 8px 10px; text-align: left; border-bottom: 1px solid var(--line); }
th { color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: 1px; cursor: pointer; user-select: none; background: var(--bg-3); font-weight: 600; }
th:hover { color: var(--fg); }
tbody tr:hover { background: var(--bg-3); }
tr.row-bad { background: #fef2f2; }
tr.row-warn { background: #fffbeb; }
.bar-inline { display: inline-block; height: 6px; background: var(--accent); border-radius: 3px; vertical-align: middle; margin-right: 6px; }
td.r, th.r { text-align: right; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 11px; font-weight: 600; }
.badge.none { background: #d1fae5; color: #065f46; }
.badge.indicator_only { background: #fef3c7; color: #92400e; }
.badge.pathogen { background: #ffedd5; color: #9a3412; }
.badge.multi_pathogen { background: #fee2e2; color: #991b1b; }
.badge.y23 { background: #fce7f3; color: var(--year23); }
.badge.y24 { background: #ede9fe; color: var(--year24); }
.badge.y25 { background: #dbeafe; color: var(--year25); }
.muted { color: var(--ink-500); }
.ar { font-family: 'IBM Plex Sans Arabic', 'Tajawal', sans-serif;
   direction: rtl; unicode-bidi: embed; font-weight: 500; }
footer { margin-top: 40px; color: var(--ink-500); font-size: 11px; text-align: center;
   font-family: 'Tajawal', sans-serif; letter-spacing: 1.5px; text-transform: uppercase;
   padding: 20px 30px; border-top: 1px solid var(--sand-200);
   background: linear-gradient(180deg, transparent 0%, var(--sand-100) 100%); }
footer::before { content: "۞"; color: var(--gold-500); margin-right: 8px;
   font-size: 14px; opacity: 0.6; }

/* Chip / KPI / Card refinements */
.kpi { background-image: linear-gradient(180deg, #fffefa 0%, var(--bg-2) 100%);
   border-color: var(--sand-200); border-radius: 4px; box-shadow: var(--shadow); }
.kpi .label { color: var(--gold-700); font-family: 'Tajawal', sans-serif;
   text-transform: uppercase; letter-spacing: 2px; font-weight: 600; font-size: 10px; }
.kpi .value { font-family: 'DM Mono', monospace; color: var(--ink-900);
   font-weight: 500; font-variant-numeric: tabular-nums; letter-spacing: -0.5px; }
.kpi .sub { color: var(--ink-500); font-family: 'IBM Plex Sans Arabic', sans-serif; }
.card { background: var(--bg-2); border: 1px solid var(--sand-200);
   border-radius: 4px; box-shadow: var(--shadow); position: relative; }
.card::before { content: ""; position: absolute; top: 0; left: 0; right: 0;
   height: 2px; background: linear-gradient(90deg, var(--gold-500) 0%, transparent 40%); }
.chip { font-family: 'Tajawal', sans-serif; font-weight: 500; border-radius: 2px;
   background: var(--sand-100); border-color: var(--sand-200); color: var(--ink-700); }
.chip:hover { border-color: var(--green-700); background: #fffdf8; color: var(--green-900); }
.chip.active { background: var(--green-700); border-color: var(--green-700);
   color: #faf6ee; box-shadow: 0 2px 4px rgba(14,92,54,0.25); }
.chip[data-value="2023"].active { background: var(--year23); border-color: var(--year23); }
.chip[data-value="2024"].active { background: var(--year24); border-color: var(--year24); color: var(--ink-900); }
.chip[data-value="2025"].active { background: var(--year25); border-color: var(--year25); }
.btn-reset { font-family: 'Tajawal', sans-serif; background: var(--green-700);
   border-radius: 2px; }
.btn-reset:hover { background: var(--green-900); }
.filter-pill { font-family: 'Tajawal', sans-serif; border-radius: 2px;
   background: var(--sand-100); border-color: var(--sand-200); color: var(--ink-500); }
.filter-pill.active { background: var(--gold-200); color: var(--gold-700);
   border-color: var(--gold-500); font-weight: 600; }
table { font-family: 'IBM Plex Sans Arabic', sans-serif; }
th { color: var(--gold-700); background: var(--sand-100);
   font-family: 'Tajawal', sans-serif; letter-spacing: 1.8px; font-size: 10px;
   border-bottom: 2px solid var(--sand-300); }
td { font-variant-numeric: tabular-nums; }
tbody tr:hover { background: var(--sand-100); }
.year-bar { background: rgba(255,253,248,0.95); border-color: var(--sand-200);
   border-radius: 4px; backdrop-filter: blur(8px); }
.year-bar-label { color: var(--gold-700); font-family: 'Tajawal', sans-serif;
   letter-spacing: 2px; font-weight: 600; }
.filter-section { background: var(--bg-2); border-color: var(--sand-200);
   border-radius: 4px; box-shadow: var(--shadow); }
.filter-section .section-title { background: var(--sand-100); color: var(--gold-700);
   font-family: 'Tajawal', sans-serif; letter-spacing: 2px;
   border-bottom-color: var(--sand-200); }
</style>
</head>
<body>

<header class="masthead">
  <div class="masthead-inner">
    <div class="logo"></div>
    <div class="titleblock">
      <h2 class="title-ar">أمانة منطقة الرياض · مختبر صحة الغذاء والمياه</h2>
      <div class="title-en">Riyadh Municipality · Research &amp; Development</div>
      <div class="subtitle-block">Microbiology Decision Dashboard</div>
    </div>
    <div class="meta-strip">
      <span class="label">Last build</span>
      <span class="val" id="build-stamp">—</span>
    </div>
  </div>
</header>

<div class="page-body">
<h1>Riyadh Municipality Lab</h1>

<div class="year-bar" id="year_bar">
  <span class="year-bar-label">Year</span>
  <div class="chips" id="f_year"></div>
  <span class="filter-pill" id="filter_status">All filters cleared</span>
  <button class="btn-reset" id="btn_reset" style="margin-left:auto" disabled>Reset all filters</button>
</div>

<div class="filter-section">
  <div class="section-title">Time & Compliance</div>
  <div class="filters">
    <div class="filter-group">
      <label>Date range</label>
      <div class="date-range">
        <input type="date" id="f_date_from">
        <input type="date" id="f_date_to">
      </div>
    </div>
    <div class="filter-group">
      <label>Compliance</label>
      <div class="chips" id="f_compliance"></div>
    </div>
    <div class="filter-group">
      <label>Severity tier</label>
      <div class="chips" id="f_severity"></div>
    </div>
  </div>
</div>

<div class="filter-section">
  <div class="section-title">Location <span class="section-note">— filter by sector (قطاع): 5 sectors + Special, matching the Annual Report</span></div>
  <div class="filters">
    <div class="filter-group">
      <label>Sector (قطاع)</label>
      <div class="chips ar" id="f_sector"></div>
    </div>
  </div>
</div>

<div class="filter-section">
  <div class="section-title">Sample product <span class="section-note">— GSO 1016 categories span both years (2025 derived from sample_type)</span></div>
  <div class="filters">
    <div class="filter-group" style="grid-column: 1 / -1;">
      <label>GSO 1016 category</label>
      <div class="chips" id="f_gso_category"></div>
    </div>
  </div>
</div>

<div class="filter-section">
  <div class="section-title">Microbe — by organism / class</div>
  <div class="filters">
    <div class="filter-group" style="grid-column: 1 / -1;">
      <label>Click chips to include failures involving that organism (OR semantics)</label>
      <div class="chips ar" id="f_microbe"></div>
    </div>
  </div>
</div>

<div class="filter-section">
  <div class="section-title">Severity quick filters</div>
  <div class="filters">
    <div class="filter-group" style="grid-column: 1 / -1;">
      <div class="toggle-row">
        <div class="toggle" id="t_pathogen">Pathogen only <span class="section-note">(any year)</span></div>
        <div class="toggle" id="t_repeat">Repeat offender (≥2 non-compliant in 90d) <span class="section-note">(any year)</span></div>
        <div class="toggle" id="x_raw_meat">Exclude meat &amp; poultry <span class="section-note">(reduces noise on Salmonella etc.)</span></div>
      </div>
    </div>
  </div>
</div>


<div class="kpis" id="kpis"></div>

<!-- Top-contaminated subtypes list — replaces the single-pick "most
     contaminated" card with a ranked list at the specific sample-name
     level (e.g. Tabouleh, Feta cheese, refrigerator swab), so the GSO
     category isn\'t the only granularity. -->
<div class="card full" style="margin-bottom:14px">
  <h2>Top 10 most-contaminated subtypes <span style="font-weight:400; text-transform:none; letter-spacing:0; color:var(--muted); font-size:11px">— grouped by the specific <code>sample_name</code> (e.g. تبولة, جبنة فيتا) with its GSO 1016 parent category. Minimum 20 samples per row (5 when a microbe/severity filter is active).</span></h2>
  <div id="top-subtypes" style="overflow:auto"></div>
</div>

<div class="grid">
  <div class="card full">
    <h2>Riyadh map — bubble size = total samples · colour = metric</h2>
    <div class="toggle-row" style="margin-bottom:10px; flex-wrap:wrap; align-items:center">
      <span class="muted" style="font-size:11px; text-transform:uppercase; letter-spacing:1px">Metric</span>
      <div class="toggle active" data-metric="failure_rate">% non-compliance</div>
      <div class="toggle" data-metric="pathogen_rate">% pathogen</div>
      <div class="toggle" data-metric="volume">Total samples</div>
      <span style="width:18px"></span>
      <span class="muted" style="font-size:11px; text-transform:uppercase; letter-spacing:1px">Tiles</span>
      <div class="toggle active" data-tiles="light">Light</div>
      <div class="toggle" data-tiles="streets">Streets</div>
      <div class="toggle" data-tiles="dark">Dark</div>
    </div>
    <div id="chart_map" class="chart" style="min-height:560px"></div>
  </div>

  <div class="card full">
    <h2>Non-compliance rate &amp; per-microbe rate over time (click legend to toggle organisms)</h2>
    <div id="chart_trend" class="chart"></div>
  </div>

  <div class="card">
    <h2>Year-on-year comparison</h2>
    <div id="chart_yoy" class="chart"></div>
  </div>

  <!-- Slice-active banner — appears only when severity / microbe / pathogen-only /
       repeat-offender filter is active. Tells the user which downstream charts
       are narrowed by their slice, and that KPIs above are scope-wide. -->
  <div id="slice-banner" style="display:none; grid-column:1/-1; background:#fef3c7; border:1px solid #fbbf24; border-radius:10px; padding:10px 14px; font-size:12px; color:#92400e; margin-bottom:6px"></div>

  <div class="card">
    <h2>Severity breakdown by month</h2>
    <div id="chart_severity_month" class="chart"></div>
  </div>

  <div class="card tall" data-needs-year="2025">
    <h2>Top 15 chains by non-compliant samples <span class="year-required-badge">2025 source</span></h2>
    <div id="chart_chains" class="chart tall"></div>
  </div>

  <div class="card full">
    <h2>Non-compliant tests · pathogens vs indicators   <span class="section-note" style="font-size:11px">(click a bar to drill down)</span></h2>
    <div style="display:grid; grid-template-columns: 1fr 1fr; gap:18px">
      <div>
        <div style="font-size:11px; text-transform:uppercase; letter-spacing:1px; color:var(--muted); margin-bottom:6px">Pathogens</div>
        <div id="chart_tests_pathogen" class="chart"></div>
      </div>
      <div>
        <div style="font-size:11px; text-transform:uppercase; letter-spacing:1px; color:var(--muted); margin-bottom:6px">Indicators</div>
        <div id="chart_tests_indicator" class="chart"></div>
      </div>
    </div>
    <div id="tests_drilldown" style="margin-top:14px"></div>
  </div>

  <div class="card" data-needs-year="2025">
    <h2>Sectors — total samples &amp; non-compliance <span class="year-required-badge">2025 source</span></h2>
    <div id="chart_sector" class="chart"></div>
  </div>

  <div class="card full">
    <h2>GSO 1016 categories — total samples &amp; non-compliance</h2>
    <div id="chart_gso_cat" class="chart" style="min-height:480px"></div>
  </div>

  <div class="card full">
    <h2>Severity tier × GSO 1016 category</h2>
    <div id="chart_heatmap" class="chart"></div>
  </div>

  <div class="card">
    <h2>Sampling cadence by day-of-week</h2>
    <div id="chart_dow" class="chart"></div>
  </div>

  <div class="card full" data-needs-year="2025">
    <h2>Repeat-offender chains <span class="year-required-badge">2025 source</span></h2>
    <div class="muted" style="margin-bottom:8px; font-size:12px">
      "Max non-compliance streak (90d)" = the highest count of non-compliant samples this chain ever
      accumulated in any rolling 90-day window. A chain that hit 8 means it had 8 non-compliant samples
      within a single 90-day stretch — a sustained problem, not just a one-off bad sample.
    </div>
    <div id="repeat_table"></div>
  </div>

</div>

<footer>Generated from data&lt;YEAR&gt;.parquet (auto-discovered) — <span id="meta_rows">…</span> rows · date range <span id="meta_range">…</span></footer>

<script>
const PAYLOAD = __PAYLOAD__;
const COLS = {};
PAYLOAD.data.cols.forEach((c, i) => { COLS[c] = i; });
const ROWS = PAYLOAD.data.rows;
const FACETS = PAYLOAD.facets;

// Severity = 'none' was dropped at data-load (user direction 2026-06-14).
// Only the 3 actual severity tiers remain. Colors picked for strong visual
// separation: bright yellow → orange → deep red, so each tier is obvious
// even in stacked bars at small sizes.
const SEVERITY_COLOR = {
  indicator_only: '#facc15',   // bright yellow — lowest severity
  pathogen:       '#f97316',   // orange — single pathogen
  multi_pathogen: '#b91c1c'    // deep red — most serious
};
const SEVERITY_ORDER = ['indicator_only', 'pathogen', 'multi_pathogen'];
// Per-year accent colours. Any year not listed here falls back to '#3b82f6'
// — covers future years without code changes. Keep keys as numeric type so
// state.years (which stores numbers) can index this dict.
const YEAR_COLOR = { 2024: '#7c3aed', 2025: '#3b82f6' };
const YEAR_COLOR_DEFAULT = '#3b82f6';
const yearColor = y => YEAR_COLOR[y] || YEAR_COLOR_DEFAULT;
const yearBadgeClass = y => 'y' + String(y).slice(2);   // 2023 → 'y23', 2024 → 'y24', 2025 → 'y25'
const DOW_LABELS = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
const PLOTLY_CONFIG = { displayModeBar: false, responsive: true };

// Pre-compute pathogen/indicator sets so filter logic is O(1) per row.
const PATHOGEN_SET = new Set(FACETS.test_classes.pathogen);
const INDICATOR_SET = new Set(FACETS.test_classes.indicator);
const EXCLUDE = FACETS.exclude_constants;
const TBC_SET = new Set(EXCLUDE.tbc_names);
const YM_SET = new Set(EXCLUDE.yeast_mould_names);
const RAW_MEAT_TYPES = new Set(EXCLUDE.raw_meat_sample_types);
const ANIMAL_FEED_TYPES = new Set(EXCLUDE.animal_feed_sample_types);

// Special token used inside the microbe chip set to mean "any indicator failure".
const INDICATOR_TOKEN = '__INDICATOR__';

const state = {
  years: new Set(),               // empty = all years
  date_from: FACETS.date_min,
  date_to: FACETS.date_max,
  compliance: new Set(),
  sector: new Set(),
  severity: new Set(),
  gso_category: new Set(),
  microbe: new Set(),             // Set of pathogen names + optional INDICATOR_TOKEN; empty = no constraint
  pathogen_only: false,
  repeat_only: false,
  exclude_raw_meat: false,        // restored 2026-06-18: meat-sample noise distorts pathogen rates
};

const COMPLIANCE_OPTIONS = ['Compliant', 'Non-compliant'];

function buildChips(parentId, items, stateKey, valueMap) {
  const parent = document.getElementById(parentId);
  parent.innerHTML = '';
  items.forEach(it => {
    const el = document.createElement('div');
    el.className = 'chip';
    el.textContent = it;
    el.dataset.value = valueMap ? valueMap(it) : it;
    el.addEventListener('click', () => {
      el.classList.toggle('active');
      const v = valueMap ? valueMap(it) : it;
      if (state[stateKey].has(v)) state[stateKey].delete(v);
      else state[stateKey].add(v);
      applyFilters();
    });
    parent.appendChild(el);
  });
}

document.getElementById('f_date_from').value = FACETS.date_min;
document.getElementById('f_date_to').value = FACETS.date_max;
document.getElementById('f_date_from').addEventListener('change', e => {
  state.date_from = e.target.value; applyFilters();
});
document.getElementById('f_date_to').addEventListener('change', e => {
  state.date_to = e.target.value; applyFilters();
});

buildChips('f_year',          FACETS.years.map(y => String(y)), 'years', v => parseInt(v, 10));
buildChips('f_compliance',    COMPLIANCE_OPTIONS,                'compliance');
buildChips('f_sector',        FACETS.sectors,                    'sector');
buildChips('f_severity',      FACETS.severity,                   'severity');
buildChips('f_gso_category',  FACETS.gso_categories || [],       'gso_category');

// Microbe chips: one per pathogen (frequency-ordered, count in label) + a final
// 'Indicator' chip representing the whole indicator class. OR semantics — selecting
// multiple chips keeps samples that match ANY of them.
// Updates microbe-chip labels with live counts from the filtered scope so
// chip text reflects what clicking returns under the current year + scope
// filter (fixes the bug where chip counts were frozen at all-years totals).
function refreshMicrobeChipCounts(rowsScope) {
  const live = new Map();
  for (const r of rowsScope) {
    const seen = new Set();
    for (const t of (r[COLS.failed_tests] || [])) {
      if (seen.has(t)) continue;
      seen.add(t);
      live.set(t, (live.get(t) || 0) + 1);
    }
  }
  document.querySelectorAll('#f_microbe .chip').forEach(el => {
    const name = el.dataset.value;
    if (!name || name === '__INDICATOR__') return;
    const n = live.get(name) || 0;
    el.textContent = n > 0 ? `${name} (${n})` : `${name} (0)`;
    el.title = n === 0
      ? 'No failures of this organism in the current data — clicking returns 0 rows.'
      : `${n} samples failed this organism in the current view.`;
    el.style.opacity = n === 0 ? '0.55' : '';
  });
}

(function buildMicrobeChips() {
  const parent = document.getElementById('f_microbe');
  parent.innerHTML = '';
  function addChipGroup(label, chips, accentColor) {
    const header = document.createElement('div');
    header.style.width = '100%';
    header.style.fontSize = '10px';
    header.style.textTransform = 'uppercase';
    header.style.letterSpacing = '0.5px';
    header.style.color = accentColor;
    header.style.fontWeight = '600';
    header.style.marginTop = '6px';
    header.textContent = label;
    parent.appendChild(header);
    chips.forEach(p => {
      const el = document.createElement('div');
      el.className = 'chip';
      // Label: "name (N)" — count of samples in our cleaned data where this
      // organism appears in failed_tests. No external/manual baseline.
      const labelStr = p.count > 0 ? `${p.name} (${p.count})` : `${p.name} (0)`;
      el.textContent = labelStr;
      el.dataset.value = p.name;
      // Tooltip uses only our data
      el.title = p.count === 0
        ? 'No failures of this organism in the current data — clicking returns 0 rows.'
        : `${p.count} samples failed this organism in the current view.`;
      if (p.count === 0) el.style.opacity = '0.55';
      el.addEventListener('click', () => {
        el.classList.toggle('active');
        if (state.microbe.has(p.name)) state.microbe.delete(p.name);
        else state.microbe.add(p.name);
        applyFilters();
      });
      parent.appendChild(el);
    });
  }
  addChipGroup('Pathogens', FACETS.pathogen_chips, '#dc2626');
  addChipGroup('Indicators (each individually clickable)', FACETS.indicator_chips || [], '#0891b2');
  // 'Indicator (any)' meta-chip — OR across all indicators
  const indSection = document.createElement('div');
  indSection.style.width = '100%';
  indSection.style.fontSize = '10px';
  indSection.style.textTransform = 'uppercase';
  indSection.style.letterSpacing = '0.5px';
  indSection.style.color = '#0891b2';
  indSection.style.fontWeight = '600';
  indSection.style.marginTop = '6px';
  indSection.textContent = 'Class meta-chip';
  parent.appendChild(indSection);
  const ind = document.createElement('div');
  ind.className = 'chip';
  ind.textContent = 'Any indicator-class failure';
  ind.dataset.value = INDICATOR_TOKEN;
  ind.title = 'Shortcut: samples with at least one indicator failure (Total Bacterial Count, Coliforms, Enterobacteriaceae, Yeasts & Moulds)';
  ind.addEventListener('click', () => {
    ind.classList.toggle('active');
    if (state.microbe.has(INDICATOR_TOKEN)) state.microbe.delete(INDICATOR_TOKEN);
    else state.microbe.add(INDICATOR_TOKEN);
    applyFilters();
  });
  parent.appendChild(ind);
})();

// Sub-municipality filter removed 2026-07-16 — geography is now sector-level
// (5 sectors + Special), matching the Annual Report.

// GSO product multi-select removed 2026-06-18; its state/reset stub removed
// 2026-07-16. Filter on GSO category (which spans both years) instead.

document.getElementById('t_pathogen').addEventListener('click', e => {
  e.target.classList.toggle('active');
  state.pathogen_only = e.target.classList.contains('active');
  applyFilters();
});
document.getElementById('t_repeat').addEventListener('click', e => {
  e.target.classList.toggle('active');
  state.repeat_only = e.target.classList.contains('active');
  applyFilters();
});
document.getElementById('x_raw_meat').addEventListener('click', e => {
  e.target.classList.toggle('active');
  state.exclude_raw_meat = e.target.classList.contains('active');
  applyFilters();
});

document.getElementById('btn_reset').addEventListener('click', () => {
  state.years.clear();
  state.date_from = FACETS.date_min;
  state.date_to = FACETS.date_max;
  state.compliance.clear();
  state.severity.clear(); state.sector.clear(); state.microbe.clear();
  state.gso_category.clear();
  state.pathogen_only = false; state.repeat_only = false;
  state.exclude_raw_meat = false;
  document.getElementById('f_date_from').value = FACETS.date_min;
  document.getElementById('f_date_to').value = FACETS.date_max;
  document.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
  document.querySelectorAll('.toggle').forEach(t => t.classList.remove('active'));
  applyFilters();
});

function rowHasTestIn(row, set) {
  const tests = row[COLS.failed_tests] || [];
  for (const t of tests) if (set.has(t)) return true;
  return false;
}

// Each chip-set / multi-select filter is "include row iff its column value is
// in the selected set (empty set = no constraint)". Same logic for 8 filters.
const CHIP_FILTERS = [
  { state_key: 'years',        col_key: 'year' },
  { state_key: 'sector',       col_key: 'sector' },
  { state_key: 'severity',     col_key: 'severity' },
  { state_key: 'gso_category', col_key: 'gso_category' },
];

// Boolean quick toggles. When the toggle is on, the row must satisfy `test`.
const SHOW_ONLY_TOGGLES = [
  { state_key: 'pathogen_only',         test: r => r[COLS.pathogen] === 1 },
  { state_key: 'repeat_only',           test: r => (r[COLS.ro_count] || 0) >= 2 },
];

// Exclusion toggles. The raw-meat one was brought back 2026-06-18 because
// meat sample volume was inflating pathogen rates (Salmonella in particular).
// `sample_type` now carries the GSO category name, so the check is on that.
const EXCLUDE_TOGGLES = [
  { state_key: 'exclude_raw_meat',
    test: r => r[COLS.gso_category] === 'Meat, Poultry and its Products' },
];

function applyFilters() {
  const cD = COLS.date, cF = COLS.failure;
  const fCo = state.compliance;
  const fMicro = state.microbe;
  const dFrom = state.date_from, dTo = state.date_to;

  // Compliance (two-state chip group with off-state when both selected).
  const wantCompliant = fCo.has('Compliant');
  const wantNoncompliant = fCo.has('Non-compliant');
  const complianceActive = fCo.size > 0 && !(wantCompliant && wantNoncompliant);

  // Microbe chip filter: OR across selected pathogen chips PLUS the
  // INDICATOR_TOKEN meta-chip (any indicator-class failure).
  const microbePathogens = new Set();
  let wantIndicatorClass = false;
  for (const v of fMicro) {
    if (v === INDICATOR_TOKEN) wantIndicatorClass = true;
    else microbePathogens.add(v);
  }
  const microActive = fMicro.size > 0;

  // Pre-bind active filters to skip empty-state checks in the hot path.
  const activeChips = CHIP_FILTERS.filter(f => state[f.state_key].size > 0)
    .map(f => ({ set: state[f.state_key], col: COLS[f.col_key] }));
  const activeShowOnly = SHOW_ONLY_TOGGLES.filter(t => state[t.state_key]);
  const activeExcludes = EXCLUDE_TOGGLES.filter(t => state[t.state_key]);

  // --- year-aware UI: hide cards whose required source years are all
  // excluded by the current year chip selection. data-needs-year may list
  // a single year ("2025") or a comma-separated set ("2023,2025") — the
  // card is shown as long as ANY of its required years is in the active
  // selection (or when no year chip is active at all).
  const activeYears = state.years;  // Set of selected year integers
  document.querySelectorAll('.card[data-needs-year]').forEach(card => {
    const needed = card.dataset.needsYear.split(',').map(s => parseInt(s.trim(), 10));
    const hide = activeYears.size > 0 && !needed.some(y => activeYears.has(y));
    card.classList.toggle('hidden-by-year', hide);
  });

  // --- filter status pill + Reset button enable/disable
  let activeCount = 0;
  if (state.years.size > 0) activeCount++;
  if (state.compliance.size > 0) activeCount++;
  if (state.severity.size > 0) activeCount++;
  if (state.sector.size > 0) activeCount++;
  if (state.gso_category.size > 0) activeCount++;
  if (state.microbe.size > 0) activeCount++;
  if (state.pathogen_only) activeCount++;
  if (state.repeat_only) activeCount++;
  if (state.exclude_raw_meat) activeCount++;
  if (state.date_from !== FACETS.date_min || state.date_to !== FACETS.date_max) activeCount++;
  const pill = document.getElementById('filter_status');
  const btn  = document.getElementById('btn_reset');
  if (activeCount === 0) {
    pill.textContent = 'All filters cleared';
    pill.classList.remove('active');
    btn.disabled = true;
  } else {
    pill.textContent = activeCount + ' filter' + (activeCount === 1 ? '' : 's') + ' active';
    pill.classList.add('active');
    btn.disabled = false;
  }

  // ─── Single filter tier (2026-07-16) ────────────────────────────────────
  // Every active filter — year, date, compliance, sector, gso_category,
  // severity, microbe, pathogen_only, repeat_only, exclude_raw_meat —
  // contributes to ONE `rowsFiltered` set that feeds every
  // chart and KPI. (Replaces the old scope/slice/active split, where severity
  // and microbe drove only 5 of 15 figures and appeared to do nothing.)
  function isPass(r) {
    if (r[cD] && (r[cD] < dFrom || r[cD] > dTo)) return false;
    if (complianceActive) {
      const isNc = r[cF] === 1;
      if (wantCompliant && isNc) return false;
      if (wantNoncompliant && !isNc) return false;
    }
    for (const f of activeChips) if (!f.set.has(r[f.col])) return false;
    for (const e of activeExcludes) if (e.test(r)) return false;
    for (const t of activeShowOnly) if (!t.test(r)) return false;
    if (microActive) {
      let m = false;
      const tests = r[COLS.failed_tests] || [];
      for (const t of tests) {
        if (microbePathogens.has(t)) { m = true; break; }
        if (wantIndicatorClass && INDICATOR_SET.has(t)) { m = true; break; }
      }
      if (!m) return false;
    }
    return true;
  }

  const rowsFiltered = ROWS.filter(isPass);

  // Filter banner: show whenever any filter is active.
  const anyActive = activeChips.length > 0 || complianceActive || microActive
                  || activeShowOnly.length > 0 || activeExcludes.length > 0
                  || state.date_from !== FACETS.date_min || state.date_to !== FACETS.date_max;
  const banner = document.getElementById('slice-banner');
  if (banner) {
    if (anyActive) {
      banner.style.display = 'block';
      banner.innerHTML = '<b>Filter active:</b> '
        + rowsFiltered.length.toLocaleString() + ' of ' + ROWS.length.toLocaleString()
        + ' samples match the current filters — every chart and KPI reflects them.';
    } else {
      banner.style.display = 'none';
    }
  }

  renderAll(rowsFiltered);
}

function groupBy(rows, keyFn) {
  const m = new Map();
  for (const r of rows) {
    const k = keyFn(r);
    if (k === null || k === undefined) continue;
    if (!m.has(k)) m.set(k, []);
    m.get(k).push(r);
  }
  return m;
}
function pct(num, den) { return den ? 100 * num / den : 0; }

// Render a Plotly chart, first clearing any empty-state message ("No … data")
// left in the mount from a previous render, so it can't sit under the bars.
// (2026-07-16 — fixes the overlap on the chains chart and any similar transition.)
function reactChart(id, traces, layout, config) {
  const el = document.getElementById(id);
  if (el && !el.classList.contains('js-plotly-plot')) el.innerHTML = '';
  Plotly.react(id, traces, layout, config);
}

function renderKpis(rowsBase) {
  // Single filter tier (2026-07-16): `rowsBase` is the one filtered set. Sample-
  // level KPIs use it directly; when a filter restricts to non-compliant samples
  // the compliance card shows a "filter mode" badge (allNonCompliant, below).
  // `rows` = the severity-event subset, used only for organism rankings.
  const rowsFull = rowsBase;
  const rows = rowsBase.filter(r => r[COLS.severity] !== 'none');

  const total          = rowsBase.length;
  const nonCompliant   = rowsBase.filter(r => r[COLS.failure] === 1).length;
  const compliantN     = total - nonCompliant;
  const complianceRate = pct(compliantN, total);
  const pathogenFails  = rowsBase.filter(r => r[COLS.pathogen] === 1).length;
  const indicatorFails = rowsBase.filter(r => r[COLS.severity] === 'indicator_only').length;
  // Total failed test results (sum of n_failed). Distinct from sample
  // count — a sample with 3 failed tests contributes 3.
  let totalFailedTests = 0;
  for (const r of rowsBase) totalFailedTests += r[COLS.n_failed] || 0;
  const testsPerNcSample = nonCompliant ? (totalFailedTests / nonCompliant) : 0;

  // Detect "100% non-compliant view" — now only triggers when the
  // microbe / pathogen-only / repeat-only filters restrict to failing
  // samples (severity filter no longer collapses Total since we use rowsBase).
  const allNonCompliant = (total > 0 && compliantN === 0);

  // --- Rankings ---
  function rankByVolume(keyIdx, rowSet) {
    const counts = new Map();
    for (const r of rowSet) {
      const k = r[keyIdx]; if (!k) continue;
      counts.set(k, (counts.get(k) || 0) + 1);
    }
    let bestK = null, bestN = 0;
    for (const [k, n] of counts) if (n > bestN) { bestN = n; bestK = k; }
    return { key: bestK, count: bestN };
  }

  // Highest-risk sector = the sector contributing the MOST non-compliant
  // samples (matches the Annual Report's framing where Central — the largest
  // sector — is the top risk). Tie-break by total volume. Min 30 samples.
  const highestRiskSector = (() => {
    const tot = new Map(), fail = new Map();
    for (const r of rowsBase) {
      const k = r[COLS.sector]; if (!k) continue;
      tot.set(k, (tot.get(k) || 0) + 1);
      if (r[COLS.failure] === 1) fail.set(k, (fail.get(k) || 0) + 1);
    }
    let best = null, bF = -1, bT = -1;
    for (const [k, t] of tot) {
      if (t < 30) continue;
      const f = fail.get(k) || 0;
      if (f > bF || (f === bF && t > bT)) { bF = f; bT = t; best = k; }
    }
    return best ? { key: best, fail: bF, total: bT, rate: 100 * bF / bT } : { key: null };
  })();
  const highestRiskChain = rankByVolume(COLS.chain, rows);     // always by volume
  // Top failing test across ALL tests (pathogens + indicators), by number of
  // failing samples — so the top test is العد الكلي (Total Count), not just the
  // top pathogen.
  const topFailingTest = (() => {
    const fail = new Map();
    for (const r of rowsBase) {
      const seen = new Set();
      for (const t of (r[COLS.failed_tests] || [])) {
        if (seen.has(t)) continue; seen.add(t);
        fail.set(t, (fail.get(t) || 0) + 1);
      }
    }
    let bestK = null, bestN = 0;
    for (const [k, n] of fail) if (n > bestN) { bestN = n; bestK = k; }
    return { key: bestK, count: bestN };
  })();

  const fmtNum  = v => v.toLocaleString();
  const truncate = (s, n) => s && s.length > n ? s.slice(0, n - 1) + '…' : (s || '—');

  // Compliance rate card: when filter restricts to non-compliant samples,
  // showing 0.0% misleads — switch to a "Filter mode" badge instead.
  // Fixed reference to the official 2025 Annual Report compliance (73.18%);
  // 2024 has no official report, so only the 2025 figure is cited.
  const OFFICIAL_2025_COMPLIANCE = 73.18;
  const officialRef = ' · official 2025 report: ' + OFFICIAL_2025_COMPLIANCE.toFixed(1) + '%';
  const compRateCard = allNonCompliant
    ? { label: 'Compliance rate', value: '—',
        sub: 'filter restricts view to non-compliant samples only' + officialRef,
        cls: '' }
    : { label: 'Compliance rate', value: complianceRate.toFixed(1) + '%',
        sub: fmtNum(compliantN) + ' / ' + fmtNum(total) + ' samples compliant' + officialRef,
        cls: complianceRate >= 95 ? 'good' : complianceRate >= 80 ? 'warn' : 'bad' };

  const cards = [
    // ── Sample-level overview (4 cards) ─────────────────────
    { label: 'Total samples', value: fmtNum(total),
      sub: 'across ' + new Set(rowsFull.map(r => r[COLS.year])).size + ' year(s) · matches the filter',
      cls: '' },
    { label: 'Compliant samples', value: fmtNum(compliantN),
      sub: total > 0 ? pct(compliantN, total).toFixed(1) + '% of ' + fmtNum(total) + ' total' : 'no data',
      cls: 'good' },
    { label: 'Non-compliant samples', value: fmtNum(nonCompliant),
      sub: total > 0 ? pct(nonCompliant, total).toFixed(1) + '% of ' + fmtNum(total) + ' total' : 'no data',
      cls: nonCompliant > 0 ? 'bad' : 'good' },
    compRateCard,
    // ── Severity breakdown (3 cards) ────────────────────────
    { label: 'Pathogen failures', value: fmtNum(pathogenFails),
      sub: total > 0 ? pct(pathogenFails, total).toFixed(2) + '% pathogen-failure rate — not a compliance figure' : 'no data',
      cls: pathogenFails > 0 ? 'crit' : 'good' },
    { label: 'Indicator failures', value: fmtNum(indicatorFails),
      sub: total > 0 ? pct(indicatorFails, total).toFixed(2) + '% of ' + fmtNum(total) + ' total' : 'no data',
      cls: indicatorFails > 0 ? 'warn' : 'good' },
    { label: 'Total failed test results',
      value: fmtNum(totalFailedTests),
      sub: nonCompliant > 0
        ? fmtNum(nonCompliant) + ' samples · ' + testsPerNcSample.toFixed(1) + ' failed tests per non-compliant sample'
        : 'no failed tests',
      cls: '' },
    // Interactive test-count KPI removed 2026-07-16 — the estimate could not
    // compete honestly (2025 has no per-test source).
    // ── Rankings (3 cards) ──────────────────────────────────
    // "Most contaminated sample type" KPI removed 2026-06-18: it was a
    // broad GSO-category single pick (e.g. "Dairy Products") that conflicted
    // visually with the "Top 10 most-contaminated subtypes" list below
    // (specific Arabic sample names like تبولة, مسحة ثلاجة). The list is
    // the better single source of truth — same metric, better granularity.
    { label: 'Highest-risk sector',
      value: '<span style="font-size:14px; font-weight:600">' + truncate(highestRiskSector.key, 30) + '</span>',
      sub: highestRiskSector.key
        ? fmtNum(highestRiskSector.fail) + ' non-compliant of ' + fmtNum(highestRiskSector.total)
          + ' (' + highestRiskSector.rate.toFixed(1) + '%)'
        : 'no data',
      cls: '' },
    { label: 'Highest-risk chain',
      value: '<span style="font-size:14px; font-weight:600">' + truncate(highestRiskChain.key, 30) + '</span>',
      sub: highestRiskChain.key ? fmtNum(highestRiskChain.count) + ' non-compliant samples' : 'no data',
      cls: '' },
    { label: 'Top failing test',
      value: '<span style="font-size:14px; font-weight:600" class="ar">' + truncate(topFailingTest.key, 30) + '</span>',
      sub: topFailingTest.key
        ? fmtNum(topFailingTest.count) + ' failing samples · full rate ranking in the Official band'
        : 'no failing tests',
      cls: topFailingTest.count > 0 ? 'crit' : '' },
  ];
  document.getElementById('kpis').innerHTML = cards.map(c =>
    '<div class="kpi ' + c.cls + '"><div class="label">' + c.label + '</div><div class="value">' + c.value + '</div><div class="sub">' + c.sub + '</div></div>'
  ).join('');
}

// Top-10 most-contaminated subtypes (grouped by sample_name + GSO category).
// Replaces the single-pick "most contaminated sample type" card so the user
// sees the actual Arabic subtype (e.g. تبولة, مسحة ثلاجة) instead of just
// the broad GSO bucket like "Dairy Products". Min 20 samples per row to
// keep statistical noise out.
// Collapse subtype-name variants so one product doesn't split across rows in
// the most-contaminated ranking — e.g. "قطع بقدونس" (parsley pieces) groups
// with "بقدونس". (Muhannad 2026-07-09)
function normSubtypeName(n) {
  if (!n) return n;
  let s = String(n).trim().replace(/\s+/g, ' ');
  s = s.replace(/^قطع\s+/, '');   // "pieces of X" → "X"
  return s;
}
function renderTopSubtypes(rows) {
  // Single filter tier (2026-07-16): `rows` is the filtered set. When a slice-
  // type filter (microbe / pathogen-only / severity) is active, most rows are
  // failures so the non-compliance RATE degenerates to ~100% — in that mode we
  // rank subtypes by non-compliant COUNT with a lower sample floor. Otherwise we
  // rank by rate. Organism chips honour the active pathogen/microbe filter so a
  // pathogen filter never shows indicator organisms like العد الكلي.
  const microFilter = state.microbe && state.microbe.size ? state.microbe : null;
  const pathOnly = !!state.pathogen_only;
  const sliceActive = pathOnly || !!microFilter || (state.severity && state.severity.size > 0);
  const MIN_SAMPLES = sliceActive ? 5 : 20;

  const stats = new Map();   // key = normalized sample_name → {total, nc, gso, organisms}
  for (const r of rows) {
    const name = normSubtypeName(r[COLS.sample_name]);
    if (!name) continue;
    let slot = stats.get(name);
    if (!slot) {
      slot = { total: 0, nc: 0, gso: r[COLS.gso_category], organisms: new Map() };
      stats.set(name, slot);
    }
    slot.total++;
    if (!slot.gso && r[COLS.gso_category]) slot.gso = r[COLS.gso_category];
    if (r[COLS.failure] === 1) {
      slot.nc++;
      const seen = new Set();
      for (const t of (r[COLS.failed_tests] || [])) {
        if (pathOnly && !PATHOGEN_SET.has(t)) continue;
        if (microFilter && !microFilter.has(t)
            && !(microFilter.has(INDICATOR_TOKEN) && INDICATOR_SET.has(t))) continue;
        if (seen.has(t)) continue;
        seen.add(t);
        slot.organisms.set(t, (slot.organisms.get(t) || 0) + 1);
      }
    }
  }
  const items = [];
  for (const [name, s] of stats) {
    if (s.total < MIN_SAMPLES) continue;
    const orgList = Array.from(s.organisms.entries())
      .sort((a, b) => b[1] - a[1]).slice(0, 3);
    items.push({ name, total: s.total, nc: s.nc, gso: s.gso || '(uncategorised)',
                 rate: 100 * s.nc / s.total, organisms: orgList });
  }
  items.sort((a, b) => sliceActive ? (b.nc - a.nc) : (b.rate - a.rate));
  const top = items.slice(0, 10);
  const node = document.getElementById('top-subtypes');
  if (!top.length) {
    Plotly.purge('top-subtypes');
    node.innerHTML = '<div class="muted" style="padding:20px">No subtypes with ≥' + MIN_SAMPLES + ' samples in current view.</div>';
    return;
  }
  const ordered = top.slice().reverse();   // Plotly draws the first entry at the bottom → reverse so #1 is on top
  const barColor = it => it.rate >= 50 ? '#dc2626' : it.rate >= 30 ? '#f97316' : '#facc15';
  const orgStr = it => it.organisms.length
    ? it.organisms.map(([o, cnt]) => o + ' · ' + cnt).join('<br>') : '—';
  reactChart('top-subtypes', [{
    type: 'bar', orientation: 'h',
    x: ordered.map(it => it.rate),
    y: ordered.map(it => it.name),
    marker: { color: ordered.map(barColor) },
    text: ordered.map(it => it.rate.toFixed(1) + '%  (' + it.nc + '/' + it.total + ')'),
    textposition: 'outside', cliponaxis: false,
    customdata: ordered.map(it => [it.gso, orgStr(it)]),
    hovertemplate: '<b>%{y}</b><br>%{customdata[0]}<br>%{x:.1f}% non-compliant<br>Organisms:<br>%{customdata[1]}<extra></extra>',
  }], {
    paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
    font: { color: '#1c2742', size: 12, family: 'Segoe UI, Tahoma, sans-serif' },
    margin: { l: 190, r: 90, t: 6, b: 30 },
    height: 70 + ordered.length * 34,
    xaxis: { gridcolor: '#e5e7eb', ticksuffix: '%', rangemode: 'tozero' },
    yaxis: { automargin: true },
  }, PLOTLY_CONFIG);
}

// Distinct colour per microbe — picked to stay readable on the light theme
// and clearly different from each other. Pathogens use warmer reds/oranges;
// indicators use cooler greens/blues so the eye can group them visually.
const MICROBE_COLORS = {
  'استافيلوكوكس اورياس':    '#dc2626',  // Staph aureus — pathogen, red
  'السالمونيلا':            '#b91c1c',  // Salmonella — pathogen, dark red
  'ايشيريشيا كولاي':        '#ea580c',  // E. coli — pathogen, orange
  'باسيلس سيريس':           '#f59e0b',  // Bacillus cereus — pathogen, amber
  'العدد الكلي للبكتيريا':   '#0891b2',  // Total bacterial count — indicator, cyan
  'انتيروباكتريسي':         '#0284c7',  // Enterobacteriaceae — indicator, blue
  'كوليفورم':               '#7c3aed',  // Coliform — indicator, purple
  'الخمائر والاعفان':       '#059669',  // Yeasts & moulds — indicator, green
  'سيدوموناس':              '#65a30d',  // Pseudomonas — indicator, lime
};

function renderTrend(rows) {
  const byMonth = groupBy(rows, r => r[COLS.year_month]);
  const months = Array.from(byMonth.keys()).sort();
  const failureRate = months.map(m => {
    const list = byMonth.get(m);
    return pct(list.filter(r => r[COLS.failure] === 1).length, list.length);
  });
  const volume = months.map(m => byMonth.get(m).length);
  const colors = months.map(m => yearColor(parseInt(m.slice(0, 4))));

  // One % line per microbe present in the current filter (≥1 failure).
  // Sorted by overall failure count so top offenders draw first / on top.
  const microbeCounts = new Map();
  for (const r of rows) {
    for (const t of (r[COLS.failed_tests] || [])) {
      microbeCounts.set(t, (microbeCounts.get(t) || 0) + 1);
    }
  }
  const microbesActive = Array.from(microbeCounts.entries())
    .sort((a, b) => b[1] - a[1])
    .map(([m]) => m);

  // Per-microbe rate per month (% of samples in that month containing this organism).
  const microbeTraces = microbesActive.map(microbe => {
    const yvals = months.map(m => {
      const list = byMonth.get(m);
      const n = list.filter(r => (r[COLS.failed_tests] || []).includes(microbe)).length;
      return pct(n, list.length);
    });
    return {
      type: 'scatter', mode: 'lines+markers',
      x: months, y: yvals,
      name: microbe,
      line: { color: MICROBE_COLORS[microbe] || '#64748b', width: 2 },
      marker: { size: 5 },
      hovertemplate: '%{x} · ' + microbe + ': %{y:.1f}%<extra></extra>',
      // All microbe lines hidden by default in the legend ('legendonly') so
      // the chart isn't a spaghetti on first load — user clicks legend
      // entries to bring organisms into view.
      visible: 'legendonly',
    };
  });

  reactChart('chart_trend', [
    { type: 'bar', x: months, y: volume, name: 'Total samples', yaxis: 'y2',
      marker: { color: colors }, opacity: 0.55,
      hovertemplate: '%{x} · %{y} samples<extra></extra>' },
    { type: 'scatter', mode: 'lines+markers', x: months, y: failureRate, name: 'Non-compliance %',
      line: { color: '#1c2742', width: 3 }, marker: { size: 7 },
      hovertemplate: '%{x} · %{y:.1f}% non-compliant<extra></extra>' },
    ...microbeTraces,
  ], {
    paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
    font: { color: '#1c2742', family: 'Segoe UI, Tahoma, sans-serif', size: 12 },
    margin: { l: 50, r: 60, t: 10, b: 80 },
    xaxis: { gridcolor: '#e5e7eb' },
    // Hard-cap left y-axis at 100% so users can't misread auto-scaled
    // gridlines (110, 120, 150…) as if the chart exceeded 100%.
    yaxis: { gridcolor: '#e5e7eb', title: '% of samples', range: [0, 100], fixedrange: true },
    yaxis2: { overlaying: 'y', side: 'right', title: 'Total samples', showgrid: false, rangemode: 'tozero' },
    legend: { orientation: 'h', y: -0.18, font: { size: 11 } }, hovermode: 'x unified',
  }, PLOTLY_CONFIG);
}

function renderYoY(rows) {
  // Side-by-side bars per severity tier, per year — covers all years in FACETS.
  const counts = {};
  for (const y of FACETS.years) counts[y] = {};
  for (const r of rows) {
    const y = r[COLS.year], s = r[COLS.severity];
    if (!counts[y]) counts[y] = {};
    counts[y][s] = (counts[y][s] || 0) + 1;
  }
  const traces = FACETS.years.filter(y => Object.keys(counts[y] || {}).length).map(y => ({
    type: 'bar', name: String(y),
    x: SEVERITY_ORDER,
    y: SEVERITY_ORDER.map(s => counts[y][s] || 0),
    marker: { color: yearColor(y) },
    hovertemplate: y + ' · %{x}: %{y}<extra></extra>',
  }));
  reactChart('chart_yoy', traces, {
    paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
    font: { color: '#1c2742', size: 12 },
    barmode: 'group',
    margin: { l: 50, r: 18, t: 10, b: 50 },
    xaxis: { gridcolor: '#e5e7eb' }, yaxis: { gridcolor: '#e5e7eb' },
    legend: { orientation: 'h', y: 1.15 },
  }, PLOTLY_CONFIG);
}

function renderHeatmap(rows) {
  // 2024 sample_type is derived from GSO category (reverse bridge), so the
  // heatmap now spans every year present in the filter.
  // Drop empty columns so the visible grid only shows sample-types that
  // actually have rows (avoids a wide all-zero "animal_feed" column when
  // its data was severity=none and got filtered out).
  if (rows.length === 0) {
    Plotly.purge('chart_heatmap');
    document.getElementById('chart_heatmap').innerHTML =
      '<div class="muted" style="padding:30px">No samples in current view.</div>';
    return;
  }
  const allTypes = FACETS.gso_categories;
  const colTotals = allTypes.map(t => rows.filter(r => r[COLS.gso_category] === t).length);
  const types = allTypes.filter((_, i) => colTotals[i] > 0);
  const z = SEVERITY_ORDER.map(sev =>
    types.map(t => rows.filter(r => r[COLS.severity] === sev && r[COLS.gso_category] === t).length)
  );
  // Short display labels for long GSO category names so the x-axis stays
  // readable. Hover still shows the full name.
  const shortLabel = name => {
    if (name.length <= 22) return name;
    // Common-case shorteners for the wordy GSO categories.
    return name.replace('Tomato Concentrates, Sauces, Vinegar, Spices and Herbs', 'Sauces / Spices')
               .replace('Chocolate, Sweets and their Ingredients', 'Chocolate & Sweets')
               .replace('Cereals; Legumes and their Products', 'Cereals & Legumes')
               .replace('Meat, Poultry and its Products', 'Meat & Poultry')
               .replace('Fish and Shellfish their Products', 'Fish & Shellfish')
               .replace('Infants, Children and Certain Categories of Dietetic Foods', 'Infant / Dietetic')
               .replace('Jelly, Jam and Marmalade', 'Jelly & Jam')
               .replace('Egg and Egg Products', 'Eggs');
  };
  const xLabels = types.map(shortLabel);
  const xHover  = types;  // full names for hover
  // Light-theme colourscale that matches the rest of the dashboard:
  // off-white at 0 (so empty cells visually disappear into the card bg)
  // → light yellow → orange → deep red for the most-severe hotspots.
  const colorscale = [
    [0,    '#f8fafc'],   // empty cell — almost white
    [0.001,'#fef3c7'],   // 1+ sample — pale yellow
    [0.25, '#fde68a'],
    [0.45, '#fbbf24'],
    [0.65, '#f97316'],
    [0.85, '#dc2626'],
    [1.0,  '#7f1d1d'],
  ];
  // Pre-compute year span string so the title strip below the chart
  // honestly reports which years are in the matrix.
  const years = Array.from(new Set(rows.map(r => r[COLS.year]))).sort();
  const yearStr = years.length ? years.join(' + ') : '—';
  // customdata carries the full GSO name so hover stays informative even
  // when the visible label is truncated.
  const customMatrix = SEVERITY_ORDER.map(() => xHover);
  reactChart('chart_heatmap', [{
    type: 'heatmap', x: xLabels, y: SEVERITY_ORDER, z: z,
    customdata: customMatrix,
    colorscale: colorscale, zmin: 0, showscale: true,
    text: z, texttemplate: '%{text:,}',
    textfont: { size: 12, color: '#1c2742', family: 'Segoe UI, Tahoma, sans-serif' },
    xgap: 2, ygap: 2,
    hovertemplate: '<b>%{customdata}</b><br>%{y}: %{z:,} samples<extra></extra>',
    colorbar: { title: { text: 'Samples', side: 'right' },
                thickness: 12, len: 0.8, outlinewidth: 0, tickfont: { size: 11 } },
  }], {
    paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
    font: { color: '#1c2742', size: 12, family: 'Segoe UI, Tahoma, sans-serif' },
    title: { text: 'Years in view: ' + yearStr + ' · vocabulary: GSO 1016',
             font: { size: 11, color: '#64748b' }, x: 0.0, y: 0.99, xanchor: 'left' },
    margin: { l: 140, r: 18, t: 32, b: 130 },
    xaxis: { tickangle: -35, automargin: true, tickfont: { size: 11 } },
    yaxis: { automargin: true, autorange: 'reversed' },  // worst severity on top
  }, PLOTLY_CONFIG);
}

function renderSeverityMonth(rows) {
  const byMonth = groupBy(rows, r => r[COLS.year_month]);
  const months = Array.from(byMonth.keys()).sort();
  const traces = SEVERITY_ORDER.map(sev => ({
    type: 'bar', name: sev,
    x: months,
    y: months.map(m => byMonth.get(m).filter(r => r[COLS.severity] === sev).length),
    marker: { color: SEVERITY_COLOR[sev] },
    hovertemplate: '%{x} · ' + sev + ': %{y}<extra></extra>',
  }));
  reactChart('chart_severity_month', traces, {
    paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
    font: { color: '#1c2742', size: 12 },
    barmode: 'stack',
    legend: { orientation: 'h', y: 1.15 },
    margin: { l: 50, r: 18, t: 10, b: 50 },
    xaxis: { gridcolor: '#e5e7eb' }, yaxis: { gridcolor: '#e5e7eb' },
  }, PLOTLY_CONFIG);
}

function renderChains(rows) {
  const byChain = groupBy(rows.filter(r => r[COLS.chain]), r => r[COLS.chain]);
  const stats = [];
  for (const [chain, list] of byChain) {
    const total = list.length;
    const inv = list.filter(r => r[COLS.failure] === 1).length;
    if (inv === 0) continue;
    const path = list.filter(r => r[COLS.pathogen] === 1).length;
    const indicatorOnly = Math.max(0, inv - path);
    stats.push({ chain, total, inv, path, indicatorOnly, rate: pct(inv, total) });
  }
  stats.sort((a, b) => b.inv - a.inv);
  const top = stats.slice(0, 15).reverse();
  if (top.length === 0) {
    Plotly.purge('chart_chains');
    document.getElementById('chart_chains').innerHTML = '<div class="muted" style="padding:30px">No chain data in current view (2024 has no facility data).</div>';
    return;
  }
  reactChart('chart_chains', [
    { type: 'bar', orientation: 'h',
      y: top.map(s => s.chain.length > 35 ? s.chain.slice(0, 33) + '…' : s.chain),
      x: top.map(s => s.indicatorOnly), name: 'Indicator-only',
      marker: { color: '#d97706' },
      customdata: top.map(s => [s.total, s.rate.toFixed(1)]),
      hovertemplate: '<b>%{y}</b><br>%{x} indicator-only (of %{customdata[0]} samples · %{customdata[1]}% non-compliance)<extra></extra>',
    },
    { type: 'bar', orientation: 'h',
      y: top.map(s => s.chain.length > 35 ? s.chain.slice(0, 33) + '…' : s.chain),
      x: top.map(s => s.path), name: 'Pathogen',
      marker: { color: '#dc2626' },
      hovertemplate: '<b>%{y}</b><br>%{x} pathogen<extra></extra>',
    },
  ], {
    paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
    font: { color: '#1c2742', size: 12 },
    barmode: 'stack',
    margin: { l: 240, r: 18, t: 10, b: 40 },
    xaxis: { gridcolor: '#e5e7eb' }, yaxis: { automargin: true, gridcolor: '#e5e7eb' },
    legend: { orientation: 'h', y: 1.08 },
  }, PLOTLY_CONFIG);
}

// Cache of the last per-organism rows index so the drilldown click handler
// can resolve rows without rescanning the full filtered set.
let _testsByOrganism = new Map();

function renderTests(rows) {
  // Per-organism, per-year failure count. `failed_tests` is already deduped
  // at build-time (no double-count for variant spellings).
  const perOrg = new Map();  // test → {year → count}
  const rowIdx = new Map();  // test → array of rows
  for (const r of rows) {
    const yr = r[COLS.year];
    for (const t of (r[COLS.failed_tests] || [])) {
      if (!perOrg.has(t)) perOrg.set(t, {});
      perOrg.get(t)[yr] = (perOrg.get(t)[yr] || 0) + 1;
      if (!rowIdx.has(t)) rowIdx.set(t, []);
      rowIdx.get(t).push(r);
    }
  }
  _testsByOrganism = rowIdx;
  const allYears = Array.from(new Set(rows.map(r => r[COLS.year]))).sort();

  function buildPanel(domId, kind, baseColor) {
    const items = Array.from(perOrg.entries())
      .filter(([t]) => (kind === 'pathogen') === PATHOGEN_SET.has(t))
      .map(([t, byYr]) => ({
        test: t,
        total: Object.values(byYr).reduce((a, b) => a + b, 0),
        byYr,
      }))
      .sort((a, b) => a.total - b.total);  // ascending → biggest at top via reverse axis
    if (!items.length) {
      Plotly.purge(domId);
      document.getElementById(domId).innerHTML = '<div class="muted" style="padding:14px">No ' + kind + ' failures in current view.</div>';
      return;
    }
    // One trace per year so the bars stack by year — gives the year breakdown
    // inside each organism bar, like a year-over-year comparison.
    const traces = allYears.map(yr => ({
      type: 'bar', orientation: 'h',
      x: items.map(i => i.byYr[yr] || 0),
      y: items.map(i => i.test),
      name: String(yr),
      marker: { color: YEAR_COLOR[yr] || YEAR_COLOR_DEFAULT, line: { width: 0 } },
      hovertemplate: '<b>%{y}</b><br>' + yr + ': %{x:,} failures<extra></extra>',
      customdata: items.map(i => i.test),
    }));
    reactChart(domId, traces, {
      paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
      font: { color: '#1c2742', size: 12 },
      barmode: 'stack',
      margin: { l: 200, r: 18, t: 10, b: 40 },
      xaxis: { gridcolor: '#e5e7eb', title: 'Failures' },
      yaxis: { automargin: true, gridcolor: '#e5e7eb' },
      legend: { orientation: 'h', y: 1.12 },
    }, PLOTLY_CONFIG);
    // Click handler: drill down to a list of facilities + categories for the
    // clicked organism. Plotly's click event passes points with `customdata`.
    const node = document.getElementById(domId);
    node.removeAllListeners && node.removeAllListeners('plotly_click');
    node.on('plotly_click', e => {
      if (!e.points || !e.points[0]) return;
      const organism = e.points[0].customdata;
      renderTestsDrilldown(organism);
    });
  }

  buildPanel('chart_tests_pathogen', 'pathogen');
  buildPanel('chart_tests_indicator', 'indicator');
  document.getElementById('tests_drilldown').innerHTML = '';
}

function renderTestsDrilldown(organism) {
  const rows = _testsByOrganism.get(organism) || [];
  // Group by year, facility, GSO category
  const facCounts = new Map();
  const catCounts = new Map();
  const yrCounts  = new Map();
  for (const r of rows) {
    const f = r[COLS.facility] || '(unknown facility)';
    const c = r[COLS.gso_category] || '(uncategorised)';
    const y = r[COLS.year];
    facCounts.set(f, (facCounts.get(f) || 0) + 1);
    catCounts.set(c, (catCounts.get(c) || 0) + 1);
    yrCounts.set(y, (yrCounts.get(y) || 0) + 1);
  }
  const topFac = Array.from(facCounts.entries()).sort((a,b) => b[1]-a[1]).slice(0, 10);
  const topCat = Array.from(catCounts.entries()).sort((a,b) => b[1]-a[1]).slice(0, 10);
  const yrList = Array.from(yrCounts.entries()).sort((a,b) => a[0]-b[0]);
  document.getElementById('tests_drilldown').innerHTML = `
    <div style="padding:12px 14px; background:var(--bg-2); border:1px solid var(--line); border-radius:10px">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px">
        <div><span style="font-weight:600" class="ar">${escapeHtml(organism)}</span>
        <span class="muted" style="margin-left:10px">${rows.length.toLocaleString()} failures · clicked drilldown</span></div>
        <button class="btn" onclick="document.getElementById('tests_drilldown').innerHTML=''">Close</button>
      </div>
      <div style="display:flex; flex-wrap:wrap; gap:18px">
        <div style="flex:1; min-width:220px"><div class="section-note" style="margin-bottom:4px">By year</div><div id="dd_year" style="height:180px"></div></div>
        <div style="flex:1; min-width:280px"><div class="section-note" style="margin-bottom:4px">Top facilities</div><div id="dd_fac" style="height:260px"></div></div>
        <div style="flex:1; min-width:280px"><div class="section-note" style="margin-bottom:4px">Top GSO categories</div><div id="dd_cat" style="height:260px"></div></div>
      </div>
    </div>`;
  const ddLayout = (l, b) => ({
    paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
    font: { color: '#1c2742', size: 10, family: 'Segoe UI, Tahoma, sans-serif' },
    margin: { l: l, r: 34, t: 6, b: b }, showlegend: false,
    xaxis: { gridcolor: '#e5e7eb', rangemode: 'tozero' }, yaxis: { automargin: true, gridcolor: '#e5e7eb' },
  });
  reactChart('dd_year', [{ type: 'bar', x: yrList.map(e => String(e[0])), y: yrList.map(e => e[1]),
    marker: { color: yrList.map(e => yearColor(e[0])) }, text: yrList.map(e => e[1].toLocaleString()),
    textposition: 'outside', cliponaxis: false, hovertemplate: '%{x}: %{y} failures<extra></extra>' }],
    ddLayout(36, 24), PLOTLY_CONFIG);
  const fac = topFac.slice().reverse();
  reactChart('dd_fac', [{ type: 'bar', orientation: 'h', x: fac.map(e => e[1]), y: fac.map(e => e[0]),
    marker: { color: '#ea580c' }, text: fac.map(e => e[1].toLocaleString()),
    textposition: 'outside', cliponaxis: false, hovertemplate: '<b>%{y}</b>: %{x} failures<extra></extra>' }],
    ddLayout(150, 24), PLOTLY_CONFIG);
  const cat = topCat.slice().reverse();
  reactChart('dd_cat', [{ type: 'bar', orientation: 'h', x: cat.map(e => e[1]), y: cat.map(e => e[0]),
    marker: { color: '#3b82f6' }, text: cat.map(e => e[1].toLocaleString()),
    textposition: 'outside', cliponaxis: false, hovertemplate: '<b>%{y}</b>: %{x} failures<extra></extra>' }],
    ddLayout(150, 24), PLOTLY_CONFIG);
}

// renderMunicipality removed 2026-07-16 — the sub-municipality chart is
// superseded by the sector chart (renderSector).

const MAP_CENTROIDS = FACETS.map_centroids;
let mapMetric = 'failure_rate';   // 'failure_rate' | 'pathogen_rate' | 'volume'
let mapTiles  = 'light';          // 'light' | 'streets' | 'dark'

function _activate(selector, key, value) {
  document.querySelectorAll(selector).forEach(x => x.classList.remove('active'));
  document.querySelectorAll(selector + '[data-' + key + '="' + value + '"]').forEach(x => x.classList.add('active'));
}
document.querySelectorAll('[data-metric]').forEach(t => {
  t.addEventListener('click', () => {
    mapMetric = t.dataset.metric;
    _activate('[data-metric]', 'metric', mapMetric);
    renderMap(window.__mapRows || ROWS);
  });
});
document.querySelectorAll('[data-tiles]').forEach(t => {
  t.addEventListener('click', () => {
    mapTiles = t.dataset.tiles;
    _activate('[data-tiles]', 'tiles', mapTiles);
    renderMap(window.__mapRows || ROWS);
  });
});

function _tileStyle() {
  if (mapTiles === 'dark')   return 'carto-positron';
  if (mapTiles === 'streets') return 'open-street-map';
  return 'carto-positron';  // 'light' — clean, minimal, easy to read
}
function _labelColor() {
  return mapTiles === 'dark' ? '#1c2742' : '#0b1220';
}

function renderMap(rows) {
  // Sector-level bubbles (2026-07-16): every row is placed on its derived sector
  // (5 sectors + Special). The 16-sub-municipality layer was removed to match
  // the Annual Report's geography. Every sector is seeded so the footprint is
  // constant; only bubble size/colour responds to filters.
  const secAgg = new Map();
  for (const name of Object.keys(MAP_CENTROIDS.sectors)) {
    secAgg.set(name, { total: 0, inv: 0, path: 0 });
  }
  for (const r of rows) {
    const sec = r[COLS.sector];
    if (!sec || !MAP_CENTROIDS.sectors[sec]) continue;
    const cur = secAgg.get(sec);
    cur.total++;
    cur.inv += r[COLS.failure] === 1 ? 1 : 0;
    cur.path += r[COLS.pathogen] === 1 ? 1 : 0;
  }

  const allLats = [], allLons = [], allTotals = [];
  for (const [name, stats] of secAgg) {
    allLats.push(MAP_CENTROIDS.sectors[name][0]);
    allLons.push(MAP_CENTROIDS.sectors[name][1]);
    allTotals.push(stats.total);
  }

  function buildBubbleTrace(agg, centroids, label) {
    const names = Array.from(agg.keys());
    // Sort so zero-volume districts render BEHIND active ones.
    names.sort((a, b) => agg.get(a).total - agg.get(b).total);
    const lats = names.map(n => centroids[n][0]);
    const lons = names.map(n => centroids[n][1]);
    const stats = names.map(n => agg.get(n));
    const totals = stats.map(s => s.total);
    const rates = stats.map(s => s.total ? 100 * s.inv / s.total : 0);
    const pRates = stats.map(s => s.total ? 100 * s.path / s.total : 0);
    const colorVals = mapMetric === 'failure_rate' ? rates
                    : mapMetric === 'pathogen_rate' ? pRates
                    : totals;
    const maxTotal = Math.max(1, ...totals);
    // Zero-data districts get a small consistent marker so the location is
    // still visible (every sector represented), but doesn't compete visually.
    const sizes = totals.map(t => t === 0 ? 8 : 14 + 50 * Math.sqrt(t / maxTotal));
    const opacities = totals.map(t => t === 0 ? 0.35 : 0.88);
    const visibleLabels = names.map((n, i) =>
      totals[i] === 0 ? n + ' · (0)' : n + ' · ' + totals[i].toLocaleString()
    );
    const hoverText = names.map((n, i) =>
      totals[i] === 0
        ? `<b>${n}</b><br>${label}<br>No samples in current view`
        : `<b>${n}</b><br>${label}<br>` +
          `Samples: ${totals[i].toLocaleString()}<br>` +
          `Non-compliant: ${stats[i].inv.toLocaleString()} (${rates[i].toFixed(1)}%)<br>` +
          `Pathogen failures: ${stats[i].path.toLocaleString()} (${pRates[i].toFixed(1)}%)`
    );
    return {
      type: 'scattermapbox',
      lat: lats, lon: lons,
      mode: 'markers+text',
      text: visibleLabels,
      textposition: 'top center',
      textfont: { size: 11, color: _labelColor(),
                   family: 'Segoe UI, Tahoma, sans-serif' },
      hovertext: hoverText,
      hovertemplate: '%{hovertext}<extra></extra>',
      marker: {
        size: sizes,
        sizemode: 'diameter',
        color: colorVals,
        colorscale: mapMetric === 'volume'
          ? [[0, '#1f2a4a'], [0.5, '#3b82f6'], [1, '#059669']]
          : [[0, '#059669'], [0.4, '#d97706'], [0.7, '#ea580c'], [1, '#dc2626']],
        cmin: 0,
        cmax: mapMetric === 'volume' ? maxTotal : (mapMetric === 'pathogen_rate' ? 30 : 60),
        showscale: true,
        colorbar: {
          title: { text: mapMetric === 'volume' ? 'Samples' : '%', side: 'right' },
          thickness: 14, len: 0.6, outlinewidth: 0,
        },
        opacity: opacities,
      },
      name: label,
    };
  }

  // One bubble per sector (5 + Special); zero-data sectors shown faded.
  const traces = [];
  traces.push(buildBubbleTrace(secAgg, MAP_CENTROIDS.sectors, 'sector (قطاع)'));

  // Fit ALL visible bubbles with light padding. No weighting / percentile —
  // every bubble must be visible. Constant `ZOOM_K` calibrated empirically so
  // span 0.5° fits at ~zoom 10.5 (typical Plotly mapbox div size).
  const minLat = Math.min(...allLats), maxLat = Math.max(...allLats);
  const minLon = Math.min(...allLons), maxLon = Math.max(...allLons);
  const padLat = 0.025, padLon = 0.03;
  const spanLat = Math.max(0.02, (maxLat - minLat) + 2 * padLat);
  const spanLon = Math.max(0.02, (maxLon - minLon) + 2 * padLon);
  const centerLat = (minLat + maxLat) / 2;
  const centerLon = (minLon + maxLon) / 2;
  // The map div is typically ~2x wider than tall, so latitude span is the
  // binding constraint. Use the larger of (lat span) vs (lon span / 1.7).
  const effectiveSpan = Math.max(spanLat, spanLon / 1.7);
  const ZOOM_K = 720;     // calibrated: 0.5° → zoom 10.5
  const zoom = Math.max(9.5, Math.min(13.5, Math.log2(ZOOM_K / effectiveSpan)));

  reactChart('chart_map', traces, {
    mapbox: {
      style: _tileStyle(),
      center: { lat: centerLat, lon: centerLon },
      zoom: zoom,
    },
    paper_bgcolor: 'rgba(0,0,0,0)',
    font: { color: '#1c2742', size: 12 },
    margin: { l: 0, r: 0, t: 0, b: 0 },
    showlegend: false,
  }, { displayModeBar: true, modeBarButtonsToRemove: ['lasso2d', 'select2d'], responsive: true });
}

// Shared helper: stacked-by-year volume bars + single non-compliance % line
// on a secondary axis. Cleaner replacement for the old 3-series grouped bars
// that overlapped each other. Used by the Sectors and Sub-municipality charts
// so they read consistently. Both are fed rowsScope, so the rate line is always
// a valid scope non-compliance rate (the microbe filter is slice-only).
function _renderVolumeVsRate(domId, items, labelKey, opts) {
  // items: [{key, byYear: {year: count}, inv, total, rate}, ...]
  const labels = items.map(i => i[labelKey]);
  const years = Array.from(new Set(items.flatMap(i => Object.keys(i.byYear).map(Number)))).sort();
  const traces = years.map(yr => ({
    type: 'bar',
    x: labels,
    y: items.map(i => i.byYear[yr] || 0),
    name: String(yr),
    marker: { color: YEAR_COLOR[yr] || YEAR_COLOR_DEFAULT, line: { width: 0 } },
    hovertemplate: '<b>%{x}</b><br>' + yr + ': %{y:,} samples<extra></extra>',
  }));
  // Non-compliance rate as a single orange line on the right axis. These charts
  // are fed rowsScope (the microbe filter is a SLICE, not a scope constraint),
  // so the rate is always over the full scope and stays meaningful. (2026-07-09)
  traces.push({
    type: 'scatter', mode: 'lines+markers',
    x: labels, y: items.map(i => i.rate),
    name: 'Non-compliance %', yaxis: 'y2',
    line: { color: '#ea580c', width: 3, shape: 'spline' },
    marker: { size: 9, line: { color: '#fff', width: 1.5 } },
    hovertemplate: '<b>%{x}</b><br>Non-compliance: %{y:.1f}%<extra></extra>',
  });
  reactChart(domId, traces, {
    paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
    font: { color: '#1c2742', size: 11, family: 'Segoe UI, Tahoma, sans-serif' },
    barmode: 'stack',
    margin: opts.margin || { l: 50, r: 60, t: 10, b: 110 },
    xaxis: { tickangle: opts.tickangle || -30, gridcolor: '#e5e7eb', automargin: true },
    yaxis: { gridcolor: '#e5e7eb', title: { text: 'Samples', font: { size: 11 } }, zeroline: true, zerolinecolor: '#cbd5e1' },
    yaxis2: { overlaying: 'y', side: 'right',
              title: { text: '% non-compliance', font: { size: 11, color: '#ea580c' } },
              showgrid: false, range: [0, 100], tickfont: { color: '#ea580c' } },
    legend: { orientation: 'h', y: -0.30, font: { size: 11 } },
    hovermode: 'x unified',
    bargap: 0.20,
  }, PLOTLY_CONFIG);
}

function renderGsoCategory(rows) {
  // Horizontal stacked bars (one row per category) — categories on the
  // Y-axis read cleanly even with long English names like "Tomato
  // Concentrates, Sauces, Vinegar, Spices and Herbs". The non-compliance
  // % appears as a small right-side text label on each row, avoiding the
  // overlapping rate-line / grouped-bar mess of the old layout.
  const byCat = groupBy(rows.filter(r => r[COLS.gso_category]), r => r[COLS.gso_category]);
  const items = Array.from(byCat.entries()).map(([k, list]) => {
    const inv = list.filter(r => r[COLS.failure] === 1).length;
    const byYear = {};
    for (const r of list) {
      const y = r[COLS.year];
      byYear[y] = (byYear[y] || 0) + 1;
    }
    return { cat: k, total: list.length, inv, byYear, rate: pct(inv, list.length) };
  });
  // Ascending so the biggest bar lands at the TOP of the chart (Plotly draws
  // higher Y values higher; we'll set autorange:'reversed' to flip).
  items.sort((a, b) => a.total - b.total);
  // Cap to top 15 so labels stay readable; show the largest ones.
  const top = items.slice(-15);
  if (!top.length) {
    Plotly.purge('chart_gso_cat');
    document.getElementById('chart_gso_cat').innerHTML =
      '<div class="muted" style="padding:30px">No GSO-categorised samples in current view.</div>';
    return;
  }
  const years = Array.from(new Set(rows.map(r => r[COLS.year]))).sort();
  const labels = top.map(i => i.cat);
  // One trace per year so segments stack across the bar.
  const traces = years.map(yr => ({
    type: 'bar', orientation: 'h',
    y: labels,
    x: top.map(i => i.byYear[yr] || 0),
    name: String(yr),
    marker: { color: YEAR_COLOR[yr] || YEAR_COLOR_DEFAULT, line: { width: 0 } },
    hovertemplate: '<b>%{y}</b><br>' + yr + ': %{x:,} samples<extra></extra>',
  }));
  // Invisible trace anchored at total → carries the rate text label
  // beyond the bar end. cliponaxis:false lets it spill into the right margin.
  const maxTotal = Math.max(1, ...top.map(i => i.total));
  traces.push({
    type: 'bar', orientation: 'h',
    y: labels,
    x: top.map(() => 0),
    showlegend: false,
    opacity: 0,
    text: top.map(i => i.total.toLocaleString() + '  ·  ' + i.rate.toFixed(1) + '% non-compliant'),
    textposition: 'outside',
    textfont: { size: 11, color: '#1c2742' },
    hoverinfo: 'skip',
    cliponaxis: false,
    base: top.map(i => i.total),  // anchor label position at end of stacked bar
  });
  reactChart('chart_gso_cat', traces, {
    paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
    font: { color: '#1c2742', size: 11, family: 'Segoe UI, Tahoma, sans-serif' },
    barmode: 'stack',
    margin: { l: 250, r: 130, t: 20, b: 40 },
    xaxis: { gridcolor: '#e5e7eb', title: { text: 'Samples', font: { size: 11 } },
             range: [0, maxTotal * 1.30] },
    yaxis: { automargin: true, tickfont: { size: 11 } },
    legend: { orientation: 'h', y: -0.10, font: { size: 11 } },
    bargap: 0.30,
  }, PLOTLY_CONFIG);
}

function renderSector(rows) {
  const SECTORS = FACETS.sectors;
  if (!SECTORS.length) {
    Plotly.purge('chart_sector');
    document.getElementById('chart_sector').innerHTML = '<div class="muted" style="padding:30px">No sector data in current view.</div>';
    return;
  }
  // Per-sector aggregate using canonical order so missing sectors stay visible at zero.
  const items = SECTORS.map(s => {
    const list = rows.filter(r => r[COLS.sector] === s);
    const inv = list.filter(r => r[COLS.failure] === 1).length;
    const byYear = {};
    for (const r of list) {
      const y = r[COLS.year];
      byYear[y] = (byYear[y] || 0) + 1;
    }
    return { sector: s, total: list.length, inv, byYear, rate: pct(inv, list.length) };
  });
  _renderVolumeVsRate('chart_sector', items, 'sector', { tickangle: -15, margin: { l: 50, r: 60, t: 10, b: 80 } });
}

function renderDow(rows) {
  const totals = [0, 0, 0, 0, 0, 0, 0];
  const inv = [0, 0, 0, 0, 0, 0, 0];
  for (const r of rows) {
    if (r[COLS.dow] === null) continue;
    totals[r[COLS.dow]]++;
    if (r[COLS.failure] === 1) inv[r[COLS.dow]]++;
  }
  reactChart('chart_dow', [
    { type: 'bar', x: DOW_LABELS, y: totals, name: 'Total', marker: { color: '#1f2a4a' },
      hovertemplate: '<b>%{x}</b>: %{y} samples<extra></extra>' },
    { type: 'bar', x: DOW_LABELS, y: inv, name: 'Non-compliant', marker: { color: '#ea580c' },
      hovertemplate: '<b>%{x}</b>: %{y} non-compliant<extra></extra>' },
  ], {
    paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
    font: { color: '#1c2742', size: 12 },
    barmode: 'group',
    margin: { l: 50, r: 18, t: 10, b: 40 },
    xaxis: { gridcolor: '#e5e7eb' }, yaxis: { gridcolor: '#e5e7eb' },
    legend: { orientation: 'h', y: 1.12 },
  }, PLOTLY_CONFIG);
}

function renderRepeatTable(rows) {
  const byChain = groupBy(rows.filter(r => r[COLS.chain]), r => r[COLS.chain]);
  const stats = [];
  for (const [chain, list] of byChain) {
    const total = list.length;
    const invR = list.filter(r => r[COLS.failure] === 1).length;
    const path = list.filter(r => r[COLS.pathogen] === 1).length;
    let peak = 0;
    for (const r of list) peak = Math.max(peak, r[COLS.ro_count] || 0);
    if (peak < 2) continue;
    stats.push({ chain, total, inv: invR, path, peak, rate: pct(invR, total) });
  }
  stats.sort((a, b) => b.peak - a.peak);
  const node = document.getElementById('repeat_table');
  if (!stats.length) {
    Plotly.purge('repeat_table');
    node.innerHTML = '<div class="muted" style="padding:20px">No repeat-offender chains in current view.</div>';
    return;
  }
  const top = stats.slice(0, 15).reverse();   // reverse so the worst chain is on top
  const color = s => s.peak >= 10 ? '#dc2626' : s.peak >= 5 ? '#f97316' : '#3b82f6';
  reactChart('repeat_table', [{
    type: 'bar', orientation: 'h',
    x: top.map(s => s.peak), y: top.map(s => s.chain),
    marker: { color: top.map(color) },
    text: top.map(s => String(s.peak)), textposition: 'outside', cliponaxis: false,
    customdata: top.map(s => [s.total, s.inv, s.rate, s.path]),
    hovertemplate: '<b>%{y}</b><br>Max 90-day non-compliance streak: %{x}<br>%{customdata[1]}/%{customdata[0]} non-compliant (%{customdata[2]:.1f}%)<br>Pathogen failures: %{customdata[3]}<extra></extra>',
  }], {
    paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
    font: { color: '#1c2742', size: 11, family: 'Segoe UI, Tahoma, sans-serif' },
    margin: { l: 230, r: 50, t: 6, b: 34 },
    height: 70 + top.length * 26,
    xaxis: { gridcolor: '#e5e7eb', title: { text: 'Max non-compliance streak (90d)', font: { size: 10 } }, rangemode: 'tozero', dtick: 1 },
    yaxis: { automargin: true },
  }, PLOTLY_CONFIG);
}

function escapeHtml(s) {
  if (s == null) return '';
  return String(s).replace(/[&<>"']/g, c =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function renderAll(rows) {
  // Single filter tier (2026-07-16): every figure derives from the one filtered
  // set. rowsActive (severity events only) is a local derivation used solely by
  // the two intrinsically severity-event charts (severity-month, heatmap).
  const rowsActive = rows.filter(r => r[COLS.severity] !== 'none');

  document.getElementById('meta_rows').textContent = FACETS.row_count.toLocaleString();
  document.getElementById('meta_range').textContent = FACETS.date_min + ' → ' + FACETS.date_max;
  window.__mapRows = rows;   // map metric/tile toggles re-render on this set

  refreshMicrobeChipCounts(rows);
  renderKpis(rows);
  renderMap(rows);
  renderTrend(rows);
  renderYoY(rows);
  renderSector(rows);
  renderGsoCategory(rows);
  renderChains(rows);
  renderDow(rows);
  renderRepeatTable(rows);
  renderTopSubtypes(rows);
  renderSeverityMonth(rowsActive);   // intrinsically severity-event
  renderHeatmap(rowsActive);         // intrinsically severity-event
  renderTests(rows);
}

applyFilters();
</script>
</div><!-- /.page-body -->
<footer>أمانة منطقة الرياض · Riyadh Municipality Research &amp; Development</footer>
</body>
</html>
"""


def main() -> None:
    # Load every per-year wide parquet present on disk (data<YEAR>.parquet).
    # 2025 is the "no gso_code at source" outlier so we treat it the same as
    # the rest — load + tag year + stack.
    import re as _re
    cleaned_dir = ROOT / "cleaned"
    year_files = []
    for p in sorted(cleaned_dir.glob("data*.parquet")):
        m = _re.match(r"^data(\d{4})\.parquet$", p.name)
        if m:
            year_files.append((int(m.group(1)), p))

    frames = []
    for year, path in year_files:
        df = pd.read_parquet(path)
        if "year" not in df.columns:
            df = df.assign(year=year)
        frames.append(df)
        print(f"  loaded {path.name}: {len(df)} rows (year={year})")

    if not frames:
        raise SystemExit("no data<YEAR>.parquet files found in cleaned/")

    # Union the columns (2026-07-16): the old intersection dropped 2024-only
    # columns — notably the native GSO family (gso_category_name_en etc.) — which
    # forced 2024 into keyword classification. build_data/build_facets read
    # columns via getattr(..., None), so 2025's absent GSO columns become NaN and
    # fall through to the sample_type derivation, while 2024 keeps native GSO.
    combined = pd.concat(frames, ignore_index=True)
    combined = combined.sort_values(["sampling_date", "year"], kind="mergesort", na_position="last")

    payload = {
        "data": build_data(combined),
        "facets": build_facets(combined),
    }
    from datetime import datetime
    import base64
    payload_json = json.dumps(payload, ensure_ascii=False, default=str)
    html = TEMPLATE.replace("__PAYLOAD__", payload_json)
    # Embed the Riyadh Municipality (Amana) logo as a base64 data URI
    logo_p = Path("/home/bioinfo/Documents/Data-Analysis-Muhannad/amana.jpg")
    logo_uri = ("data:image/jpeg;base64," + base64.b64encode(logo_p.read_bytes()).decode("ascii")
                if logo_p.exists() else "")
    html = html.replace("__LOGO_DATA_URI__", logo_uri)
    # Stamp build time into the masthead
    stamp = datetime.now().strftime("%d %b %Y")
    html = html.replace('<span class="val" id="build-stamp">—</span>',
                        f'<span class="val" id="build-stamp">{stamp}</span>')
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(html, encoding="utf-8")
    size_kb = OUT_HTML.stat().st_size / 1024
    counts_by_year = combined.groupby("year").size()
    counts_str = " ".join(f"{int(y)}={int(c)}" for y, c in counts_by_year.items())
    print(f"\nwrote {OUT_HTML}  ({size_kb:.0f} KB, {len(combined)} rows, {counts_str})")


if __name__ == "__main__":
    main()
