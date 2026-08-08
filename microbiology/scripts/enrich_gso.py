"""Apply the GSO 1016 reference to the cleaned parquets.

Adds (to both wide and long parquets where applicable):
    gso_code_canonical  — normalised version of the raw gso_code
    gso_product_name_en
    gso_product_name_ar
    gso_category_letter  (A..Q)
    gso_category_name_en
    gso_sub_products_ar

And (long parquet, where per-test data exists):
    gso_limit_for_this_test
    gso_panel_complete    (bool: were all required tests run for this sample?)
    gso_tests_missing     (list of canonical tests not run)
    validity_vs_gso_limit (agree | lab_says_pass_should_fail | lab_says_fail_should_pass | no_limit | n/a)
"""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent
GSO_REF = ROOT / "schemas" / "gso_1016_reference.yaml"
P24_WIDE = ROOT / "cleaned" / "data2024.parquet"
P24_LONG = ROOT / "cleaned" / "data2024_long.parquet"
P25_WIDE = ROOT / "cleaned" / "data2025.parquet"

# Mapping from GSO 1016 category_name_en to dashboard category labels.
# Keeps 2024 categories stylistically aligned with 2025 raw categories.
GSO_CATEGORY_TO_DISPLAY: dict[str, tuple[str, str]] = {
    "Dairy Products": ("الاجبان (cheeses)", "cheeses"),
    "Infants, Children and Certain Categories of Dietetic Foods": (
        "Infants, Children and Certain Categories of Dietetic Foods",
        "Infants, Children and Certain Categories of Dietetic Foods",
    ),
    "Meat, Poultry and its Products": (
        "لحوم نيئة مبردة ومجمدة (Raw meat Cold or chilled )",
        "Raw meat Cold or chilled",
    ),
    "Fish and Shellfish their Products": (
        "Fish/fish product(الاسماك / منتجات الاسماك)",
        "fish product",
    ),
    "Egg and Egg Products": ("egg", "egg"),
    "Fats and Oils": ("Fats and Oils", "Fats and Oils"),
    "Tomato Concentrates, Sauces, Vinegar, Spices and Herbs": (
        "البهارات والصوصات", "Spices and Herbs"),
    "Cereals; Legumes and their Products": (
        "الحبوب والبقوليات", "Cereals; Legumes and their Products"),
    "Fruit and Vegetables": (
        "فواكه و خضروات طازجة (Fresh fruits and vegetables )",
        "Fresh fruits and vegetables",
    ),
    "Jelly, Jam and Marmalade": ("Jelly, Jam and Marmalade", "Jelly, Jam and Marmalade"),
    "Chocolate, Sweets and their Ingredients": (
        "الحلا(sweetness)", "sweetness"),
    "Drinking Water": ("المياه الغير معبأة (Unbottled water)", "Unbottled water"),
    "Beverages": (
        "شراب بنكهة و مركزاتها ( flavoured drink & its concentrates )",
        "flavoured drink & its concentrates",
    ),
    "Ready to Eat Foods": (
        "اطعمة جاهزة للأكل Ready to eat meals", "Ready to eat meals"),
    "Miscellaneous Foods": ("Miscellaneous Foods", "Miscellaneous Foods"),
}

# Fallback sample_type classifier keyed on category_en keywords.
# Mirrors the bucket logic in schemas/lab_data_2025_v1.yaml.
SAMPLE_TYPE_KEYWORDS: list[tuple[str, list[str]]] = [
    ("swab", ["swab", "swabs", "مسحة", "مسحات", "المسحات"]),
    ("water", ["unbottled water", "bottled water", "drinking water", "mineral water", "مياه"]),
    ("egg", ["egg", "بيض"]),
    ("fats_oils", ["oil", "oils", "frying oil", "زيت قلي", "الزيت القلي", "shortening",
                   "fat", "fats", "دهن", "الدهن", "سمن", "سمنة", "margarine", "مرجرين",
                   "زيت نباتي", "زيت طبخ", "زيت الذرة", "زيت دوار الشمس"]),
    ("fish", ["fish", "سمك", "اسماك", "الاسماك"]),
    ("dairy", ["milk", "cheese", "yogurt", "cream", "dairy", "لبن", "حليب", "جبن", "جبنة", "قشطة",
                "البان", "حلومي", "شيدر", "ice cream", "ايس كريم", "ايسكريم"]),
    ("raw_meat", ["raw meat", "raw minced", "raw poultry", "لحوم نيئة", "نيئة", "نيء", "لحم نيء"]),
    ("cooked_meat_poultry", ["cooked meat", "cooked chicken", "cooked", "مطبوخة", "مطبوخ", "دجاج",
                             "poultry", "turkey", "ديك رومي"]),
    ("cereals", ["grain", "grains", "cereal", "cereals", "الحبوب", "حبوب", "malt", "rice", "ارز",
                 "الارز", "شابورة", "شابورا"]),
    ("produce", ["salad", "سلطة", "السلطة", "vegetable", "خضار", "خضروات", "الخضار", "fruit",
                 "fruits", "فاكهة", "الفواكه", "فواكه", "fresh fruits", "okra", "بامية", "الملوخية",
                 "berries", "avocado", "افوكادو", "celery", "peaches", "grapes", "guava", "جوافة",
                 "pine", "تبولة", "مانجا"]),
    ("sauce_condiment", ["sauce", "صوص", "صلصة", "صلصه", "salsa", "syrup", "shira", "شيرة",
                         "نكهة", "نكهات", "mayonnaise", "مايونيز", "spices", "herbs", "بهارات",
                         "تتبيلة", "بابا غنوج"]),
    ("sweets_bakery", ["sweet", "sweetness", "الحلا", "الحلويات", "sweets", "dessert", "desserts",
                       "حلوى", "الحلوى", "bakery", "baked", "مخبوزات", "chocolate", "شوكولاتة",
                       "tiramisu", "تراميسو", "waffle", "بيتي فور", "chips", "شبس", "فشار",
                       "popcorn", "كريم كراميل", "mahalibah", "مهلبية", "حلا"]),
    ("beverage", ["juice", "juices", "عصير", "عصائر", "العصائر", "drink", "drinks", "مشروب",
                  "مشروبات", "beverage", "beverages", "soft drink"]),
    ("prepared_meal", ["falafel", "فلافل", "bhaji", "samosa", "سمبوسك", "سمبوسة", "ready to eat",
                       "جاهزة", "kofta", "كفتة", "kibbeh", "كبه", "كبة", "محاشي",
                       "ايدام", "مصقع", "مشكل", "barbecue", "barbeque", "bbq", "باربكيو"]),
    ("animal_feed", ["اعلاف", "feed", "fodder"]),
]


def classify_sample_type_from_en(category_en: str | None) -> str:
    if not category_en:
        return "other"
    blob = category_en.casefold()
    for sample_type, keywords in SAMPLE_TYPE_KEYWORDS:
        for kw in keywords:
            if kw.casefold() in blob:
                return sample_type
    return "other"

# Canonical test-name aliases — covers spelling variants found in the GSO
# reference table that don't exactly match the 2024 cleaner's canonical names.
TEST_ALIAS_TO_CANONICAL = {
    # Reference uses both 2024 and 2025 spellings; map both to a single key.
    "العد الكلي للبكتيريا": "العد الكلي للبكتيريا",
    "العدد الكلي للبكتيريا": "العد الكلي للبكتيريا",
    "Total Count Bacteria": "العد الكلي للبكتيريا",
    "انتيروباكتيريسي": "انتيروباكتريسي",
    "انتيروبكتريسي": "انتيروباكتريسي",
    "Enterobacteriaeace": "انتيروباكتريسي",
    "الانتيروباكتيريسي": "انتيروباكتريسي",
    "ايشيريشيا كولاي": "ايشيريشيا كولاي",
    "ايشيريشياكولاي": "ايشيريشيا كولاي",
    "ايشريشيا كولاي": "ايشيريشيا كولاي",
    "E.coli": "ايشيريشيا كولاي",
    "E.coli O157": "ايشيريشيا كولاي O157",
    "E.coli O157**": "ايشيريشيا كولاي O157",
    "Escherichia coli O157": "ايشيريشيا كولاي O157",
    "السالمونيلا": "السالمونيلا",
    "سالمونيلا": "السالمونيلا",
    "Salmonella": "السالمونيلا",
    "استافيلو كوكس اورياس": "استافيلوكوكس اورياس",
    "استافيلوكوكس اورياس": "استافيلوكوكس اورياس",
    "Staphylococcus aureus": "استافيلوكوكس اورياس",
    "باسيلس سيريس": "باصلص سيرز",
    "باسيلس سيرس": "باصلص سيرز",
    "باسيليس سيريس": "باصلص سيرز",
    "Bacillus cereus": "باصلص سيرز",
    "الخمائر و الاعفان": "الخمائر والاعفان",
    "الخمائر و الأعفان": "الخمائر والاعفان",
    "الخمائر والاعفان": "الخمائر والاعفان",
    "خمائر و الاعفان": "الخمائر والاعفان",
    "اعفان": "الخمائر والاعفان",
    "الاعفان": "الخمائر والاعفان",
    "الأعفان": "الخمائر والاعفان",
    "كوليفورم": "كوليفورم",
    "Coliform": "كوليفورم",
    "Coliform (100ml)": "كوليفورم",
    "كوليفورم (100ml)": "كوليفورم",
    "الليستيريا": "الليستيريا",
    "Listeria": "الليستيريا",
    "C.perfringens": "كلوستريديوم بيرفرنجنز",
    "C.Perfringens": "كلوستريديوم بيرفرنجنز",
    "Clostridium perfringens": "كلوستريديوم بيرفرنجنز",
    "C.botulinum": "كلوستريديوم بوتولينوم",
    "Clostridium botulinum": "كلوستريديوم بوتولينوم",
    "Aeromonas": "Aeromonas",
    "V. parahaemolyticus": "فيبريو",
    "V.parahaemolyticus": "فيبريو",
    "Vibrio sp.": "فيبريو",
    "Vibrio parahaemolyticus": "فيبريو",
    "Cronobacter sakazakii": "Cronobacter sakazakii",
    "Sulphite-reducing anaerobes": "Sulphite-reducing anaerobes",
    "Lipolytic bacteria": "Lipolytic bacteria",
    # 2026-08-08 panel-completeness aliases (user-approved): same organism /
    # test, different spelling between the GSO reference and the lab sheets.
    # These cleared ~1,011 false "incomplete panel" flags.
    "لستيريا": "الليستيريا",            # Listeria — reference short form
    "L.monocytogenes": "الليستيريا",    # Listeria — reference Latin form
    "خمائر": "الخمائر والاعفان",         # yeasts — lab runs combined yeasts&molds
    "CAMPYLOPACTER": "كامبيلوباكتر",     # Campylobacter — reference caps typo
    "باسلس سيرس": "باصلص سيرز",          # Bacillus cereus — yet another variant
    "Aeromonas spp": "Aeromonas",
    "P.aeruginosa": "سيدومومناس",        # bottled water: lab records Pseudomonas genus
}


def normalise_gso_code(raw) -> str | None:
    """Normalise a raw GSO code from messy lab forms into canonical form
    ``<LETTER>-<N>`` or ``<LETTER>-<N>/<M>``. Handles 15+ observed typo
    variants: leading `**`, lowercase, missing hyphen, '/' substituted with
    '.', '-', or 'L' (OCR/typo), concatenated codes, trailing whitespace.
    Returns None if the code is unrecoverable (e.g. bare letter 'H')."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    s = str(raw).strip()
    if not s:
        return None
    # 1. Strip leading asterisks/whitespace.
    s = re.sub(r"^[\*\s]+", "", s)
    # 2. Remove internal whitespace BEFORE splitting ("C -7" → "C-7").
    s = re.sub(r"\s+", "", s)
    # 3. Take just the first code if multiple were concatenated by non-space separator.
    s = re.split(r"[+,;]", s)[0]
    # 4. Uppercase letters (j-1 → J-1, p-5 → P-5).
    s = s.upper()
    # 5. Substitute '/' substitutes inside ANY sub-coded family. Sep can be one
    #    or more of {L, ., -, /} (covers P-6./1 and P-6-4-style typos).
    s = re.sub(r"^([A-Z])-(\d+)[L\.\-/]+(\d+)$", r"\1-\2/\3", s)
    # 6. Add missing slash for "P-61" → "P-6/1" (collapsed sub-code).
    s = re.sub(r"^P-6(\d)$", r"P-6/\1", s)
    # 7. Add missing hyphen between letter and number ("L9" → "L-9").
    s = re.sub(r"^([A-Z])(\d)", r"\1-\2", s)
    # 8. Final canonical-form check.
    if not re.match(r"^[A-Z]-\d+(/\d+)?$", s):
        return None
    return s


def canonical_test(t: str | None) -> str | None:
    if t is None or (isinstance(t, float) and pd.isna(t)):
        return None
    s = str(t).strip().lstrip("*").rstrip("*").strip()
    return TEST_ALIAS_TO_CANONICAL.get(s, s)


def load_reference() -> tuple[dict[str, dict], dict[str, dict]]:
    """Returns (codes_map, code_test_limits) where
        codes_map[code] = {name_en, name_ar, category_letter, category_name_en, sub_products_ar, required_tests}
        code_test_limits[(code, canonical_test)] = {limit_numeric, limit_raw, zero_tolerance, optional}
    """
    with GSO_REF.open("r", encoding="utf-8") as f:
        ref = yaml.safe_load(f)
    codes_map: dict[str, dict] = {}
    code_test_limits: dict[tuple[str, str], dict] = {}
    for c in ref["codes"]:
        codes_map[c["code"]] = {
            "name_en": c.get("name_en"),
            "name_en_long": c.get("name_en_long"),
            "name_ar": c.get("name_ar"),
            "category_letter": c.get("category_letter"),
            "category_name_en": c.get("category_name_en"),
            "sub_products_ar": c.get("sub_products_ar"),
            "required_tests": [
                canonical_test(t["test"]) for t in c.get("required_tests", [])
                if canonical_test(t["test"])
            ],
        }
        for t in c.get("required_tests", []):
            ct = canonical_test(t["test"])
            if not ct:
                continue
            code_test_limits[(c["code"], ct)] = {
                "limit_numeric": t.get("limit_numeric"),
                "limit_raw": t.get("limit_raw"),
                "zero_tolerance": bool(t.get("zero_tolerance")),
                "optional": bool(t.get("optional")),
            }
    return codes_map, code_test_limits


# ---------------------------------------------------------------------------
def enrich_wide(path: Path, codes_map: dict[str, dict], label: str) -> None:
    df = pd.read_parquet(path)
    if "gso_code" not in df.columns:
        # 2025 has no gso_code at source. Add empty stub columns so the schema
        # stacks with 2024, and skip the audit print.
        df["gso_code_canonical"]   = pd.array([None] * len(df), dtype="string")
        df["gso_product_name_en"]  = pd.array([None] * len(df), dtype="string")
        df["gso_product_name_ar"]  = pd.array([None] * len(df), dtype="string")
        df["gso_category_letter"]  = pd.array([None] * len(df), dtype="string")
        df["gso_category_name_en"] = pd.array([None] * len(df), dtype="string")
        df["gso_sub_products_ar"]  = pd.array([None] * len(df), dtype="string")
        df.to_parquet(path, compression="zstd", index=False)
        print(f"  {label} wide: no gso_code column at source — empty stub columns written for schema parity")
        return

    initial_canon = [normalise_gso_code(v) for v in df["gso_code"]]
    # Recover placeholder codes (e.g. "H", "31", "124") for food products by
    # matching their sample_name to a row that already has a valid GSO code.
    # Rows whose raw gso_code is truly absent remain environmental swabs.
    sample_to_code: dict[str, str] = {}
    for sn, code in zip(df["sample_name"], initial_canon):
        if pd.notna(sn) and code and code in codes_map:
            sample_to_code.setdefault(str(sn), code)
    canon: list[str | None] = []
    n_recovered = 0
    for raw_val, sn, code in zip(df["gso_code"], df["sample_name"], initial_canon):
        if code is None and pd.notna(raw_val) and pd.notna(sn):
            recovered = sample_to_code.get(str(sn))
            if recovered:
                n_recovered += 1
                canon.append(recovered)
                continue
        canon.append(code)
    df["gso_code_canonical"] = pd.array(canon, dtype="string")
    if n_recovered:
        print(f"  recovered {n_recovered} placeholder GSO codes by sample_name lookup")

    def lookup(field):
        return [codes_map.get(c, {}).get(field) for c in canon]

    df["gso_product_name_en"]   = pd.array(lookup("name_en"), dtype="string")
    df["gso_product_name_ar"]   = pd.array(lookup("name_ar"), dtype="string")
    df["gso_category_letter"]   = pd.array(lookup("category_letter"), dtype="string")
    df["gso_category_name_en"]  = pd.array(lookup("category_name_en"), dtype="string")
    df["gso_sub_products_ar"]   = pd.array(lookup("sub_products_ar"), dtype="string")

    # 2024 only: populate category_canonical / category_en / sample_type from GSO.
    # Rows with no GSO code are environmental/hygiene swabs.
    if "category_canonical" in df.columns:
        cat_canonical: list[str | None] = []
        cat_en: list[str | None] = []
        sample_type: list[str | None] = []
        for code, gso_cat_en in zip(canon, df["gso_category_name_en"]):
            if code and gso_cat_en is not None and not pd.isna(gso_cat_en):
                cc, ce = GSO_CATEGORY_TO_DISPLAY.get(str(gso_cat_en), (str(gso_cat_en), str(gso_cat_en)))
                cat_canonical.append(cc)
                cat_en.append(ce)
                sample_type.append(classify_sample_type_from_en(ce))
            else:
                # No GSO code → environmental swab.
                cat_canonical.append("(Swabs) المسحات")
                cat_en.append("Swabs")
                sample_type.append("swab")
        df["category_canonical"] = pd.array(cat_canonical, dtype="string")
        df["category_en"] = pd.array(cat_en, dtype="string")
        df["sample_type"] = pd.array(sample_type, dtype="string")

    df.to_parquet(path, compression="zstd", index=False)
    matched = sum(1 for c in canon if c and c in codes_map)
    no_code = sum(1 for c in canon if not c)
    print(f"  {label} wide: {matched}/{len(df)} rows matched a GSO code ({100*matched/len(df):.1f}%); {no_code} rows classified as swabs")
    cats = df["category_canonical"].dropna().value_counts().head(20)
    if len(cats):
        print(f"  top categories:")
        for k, v in cats.items():
            print(f"    {k}: {v}")


# ---------------------------------------------------------------------------
def enrich_long(path: Path, codes_map: dict[str, dict],
                code_test_limits: dict[tuple[str, str], dict]) -> None:
    """Adds per-test enrichment to the long parquet, plus sample-level
    audit columns (tests_missing, panel_complete) joined back as constant
    per (source_file, m_s_no) group."""
    df = pd.read_parquet(path)
    canon = [normalise_gso_code(v) for v in df["gso_code"]]
    df["gso_code_canonical"] = pd.array(canon, dtype="string")
    df["gso_product_name_en"] = pd.array(
        [codes_map.get(c, {}).get("name_en") for c in canon], dtype="string"
    )
    df["gso_category_letter"] = pd.array(
        [codes_map.get(c, {}).get("category_letter") for c in canon], dtype="string"
    )
    df["gso_category_name_en"] = pd.array(
        [codes_map.get(c, {}).get("category_name_en") for c in canon], dtype="string"
    )

    # Per-test limit lookup.
    canon_test = [canonical_test(t) for t in df["test"]]
    df["test_canonical"] = pd.array(canon_test, dtype="string")
    limits_num: list[float | None] = []
    limits_raw: list[str | None] = []
    zero_tol_arr: list[bool] = []
    for code, t in zip(canon, canon_test):
        entry = code_test_limits.get((code, t)) if code and t else None
        if entry:
            limits_num.append(entry["limit_numeric"])
            limits_raw.append(entry["limit_raw"])
            zero_tol_arr.append(entry["zero_tolerance"])
        else:
            limits_num.append(None)
            limits_raw.append(None)
            zero_tol_arr.append(False)
    df["gso_limit_numeric"] = pd.array(limits_num, dtype="Float64")
    df["gso_limit_raw"] = pd.array(limits_raw, dtype="string")
    df["gso_zero_tolerance"] = pd.array(zero_tol_arr, dtype="boolean")

    # Validity-vs-GSO-limit cross-check. We compare result_numeric to gso_limit_numeric.
    # Zero-tolerance means: any positive detection should fail.
    # Results written with a comparison prefix ('>10', '<10') are parsed to
    # their numeric part only, and the lab marks 99%+ of '>10' as valid — so a
    # disagreement that hinges on a prefixed result is recorded as
    # 'ambiguous_prefixed_result' (not a true disagreement) until the lab
    # confirms the convention (user decision 2026-08-08).
    decisions: list[str | None] = []
    for r_num, lim_num, zt, validity_bool, r_raw in zip(
        df["result_numeric"], df["gso_limit_numeric"], df["gso_zero_tolerance"],
        df["validity"], df["result_raw"],
    ):
        # Determine what the GSO standard would decide for this row.
        if lim_num is None or pd.isna(lim_num):
            decisions.append(None)
            continue
        if r_num is None or pd.isna(r_num):
            decisions.append("no_result")
            continue
        if zt:
            # Zero-tolerance ("غير موجودة"): anything ≤ 0 (incl. below detection
            # limit results parsed as 0) passes. Strict `== 0` over-counted
            # disagreements when LOD values fell through as 0.
            gso_pass = (r_num <= 0)
        else:
            gso_pass = (r_num <= lim_num)
        if pd.isna(validity_bool):
            decisions.append("no_lab_verdict")
            continue
        lab_pass = bool(validity_bool)
        if gso_pass == lab_pass:
            decisions.append("agree")
        elif lab_pass and not gso_pass:
            decisions.append("lab_says_pass_should_fail")
        else:
            decisions.append("lab_says_fail_should_pass")
    # Downgrade prefix-hinged disagreements to 'ambiguous_prefixed_result'.
    COMPARISON_PREFIXES = (">", "<", "≥", "≤")
    for i, (dec, r_raw) in enumerate(zip(decisions, df["result_raw"])):
        if dec in ("lab_says_pass_should_fail", "lab_says_fail_should_pass") and (
            isinstance(r_raw, str) and r_raw.strip().startswith(COMPARISON_PREFIXES)
        ):
            decisions[i] = "ambiguous_prefixed_result"
    df["validity_vs_gso_limit"] = pd.array(decisions, dtype="string")

    # Sample-level panel completeness: group by (source_file, m_s_no).
    # Required tests come from the reference; "tests run" come from this sample's test rows.
    tests_run_by_sample: dict[tuple, set[str]] = defaultdict(set)
    for sf, ms, t in zip(df["source_file"], df["m_s_no"], df["test_canonical"]):
        if t:
            tests_run_by_sample[(sf, ms)].add(t)

    missing_per_row: list[str | None] = []
    complete_per_row: list[bool | None] = []
    for sf, ms, code in zip(df["source_file"], df["m_s_no"], canon):
        if not code or code not in codes_map:
            missing_per_row.append(None)
            complete_per_row.append(None)
            continue
        required = set(codes_map[code]["required_tests"])
        run = tests_run_by_sample.get((sf, ms), set())
        missing = sorted(required - run)
        missing_per_row.append("|".join(missing) if missing else None)
        complete_per_row.append(not missing)
    df["gso_tests_missing"] = pd.array(missing_per_row, dtype="string")
    df["gso_panel_complete"] = pd.array(complete_per_row, dtype="boolean")

    df.to_parquet(path, compression="zstd", index=False)
    n_matched = int(df["gso_code_canonical"].notna().sum())
    n_with_limit = int(df["gso_limit_numeric"].notna().sum())
    print(f"  2024 long: {n_matched}/{len(df)} rows have a canonical gso_code "
          f"({100*n_matched/len(df):.1f}%); {n_with_limit} have a per-test limit lookup")
    print(f"  cross-check distribution:")
    print(df["validity_vs_gso_limit"].value_counts(dropna=False).to_string())
    panel = df.groupby(["source_file", "m_s_no"]).first()
    n_samples = len(panel)
    n_complete = int((panel["gso_panel_complete"] == True).sum())
    n_incomplete = int((panel["gso_panel_complete"] == False).sum())
    print(f"  panel completeness: {n_complete}/{n_samples} samples ran the full required panel "
          f"({100*n_complete/n_samples:.1f}%); {n_incomplete} have missing tests")


def stub_audit_on_2025_wide() -> None:
    """2025 has no GSO reference data. Add empty columns so the schema stacks."""
    wide = pd.read_parquet(P25_WIDE)
    n = len(wide)
    if "gso_panel_complete" not in wide.columns:
        wide["gso_panel_complete"] = pd.array([None] * n, dtype="boolean")
    if "gso_lab_vs_gso_disagree" not in wide.columns:
        wide["gso_lab_vs_gso_disagree"] = pd.array([None] * n, dtype="boolean")
    if "gso_lab_vs_gso_ambiguous" not in wide.columns:
        wide["gso_lab_vs_gso_ambiguous"] = pd.array([None] * n, dtype="boolean")
    if "gso_tests_missing" not in wide.columns:
        wide["gso_tests_missing"] = pd.array([None] * n, dtype="string")
    wide.to_parquet(P25_WIDE, compression="zstd", index=False)


def propagate_audit_to_wide_for(year: int) -> None:
    """Generic version of propagate_audit_to_wide_2024 for any year with a long parquet."""
    long_path = ROOT / "cleaned" / f"data{year}_long.parquet"
    wide_path = ROOT / "cleaned" / f"data{year}.parquet"
    if not long_path.exists():
        print(f"  no long parquet for {year} — skipping audit propagation")
        return
    long = pd.read_parquet(long_path)
    wide = pd.read_parquet(wide_path)
    grp = long.groupby(["source_file", "m_s_no"], dropna=False)
    panel = grp["gso_panel_complete"].first()
    DISAGREE_VALUES = {"lab_says_pass_should_fail", "lab_says_fail_should_pass"}
    def _has_disagree(s):
        return any(v in DISAGREE_VALUES for v in s if v is not None)
    disagree = grp["validity_vs_gso_limit"].apply(_has_disagree)
    ambiguous = grp["validity_vs_gso_limit"].apply(
        lambda s: any(v == "ambiguous_prefixed_result" for v in s if isinstance(v, str)))
    missing = grp["gso_tests_missing"].apply(lambda s: next((v for v in s if v is not None), None))
    audit_df = pd.DataFrame({
        "source_file": [k[0] for k in panel.index],
        "m_s_no": [k[1] for k in panel.index],
        "gso_panel_complete": panel.values,
        "gso_lab_vs_gso_disagree": disagree.values,
        "gso_lab_vs_gso_ambiguous": ambiguous.values,
        "gso_tests_missing": missing.values,
    })
    wide_keyed = wide[["source_file", "m_s_no"]].copy()
    wide_keyed["m_s_no"] = wide_keyed["m_s_no"].astype("Int64")
    audit_df["m_s_no"] = audit_df["m_s_no"].astype("Int64")
    merged = wide_keyed.merge(audit_df, on=["source_file", "m_s_no"], how="left")
    wide["gso_panel_complete"] = pd.array(merged["gso_panel_complete"].tolist(), dtype="boolean")
    wide["gso_lab_vs_gso_disagree"] = pd.array(merged["gso_lab_vs_gso_disagree"].tolist(), dtype="boolean")
    wide["gso_lab_vs_gso_ambiguous"] = pd.array(merged["gso_lab_vs_gso_ambiguous"].tolist(), dtype="boolean")
    wide["gso_tests_missing"] = pd.array(merged["gso_tests_missing"].tolist(), dtype="string")
    wide.to_parquet(wide_path, compression="zstd", index=False)
    n_incomplete = int((wide["gso_panel_complete"] == False).sum())
    n_disagree = int((wide["gso_lab_vs_gso_disagree"] == True).sum())
    n_ambiguous = int((wide["gso_lab_vs_gso_ambiguous"] == True).sum())
    print(f"  {year} wide: panel_complete=False on {n_incomplete} samples; "
          f"lab_vs_gso disagree on {n_disagree} samples; ambiguous (prefixed result) on {n_ambiguous}")


def main() -> int:
    codes_map, code_test_limits = load_reference()
    print(f"loaded {len(codes_map)} gso_codes, {len(code_test_limits)} (code,test) limit entries\n")

    print("--- 2025 wide ---")
    enrich_wide(P25_WIDE, codes_map, "2025")

    # Iterate over every year that has a wide parquet on disk (anchored regex
    # — substring match would mis-exclude future filenames like data20251.parquet).
    cleaned_dir = ROOT / "cleaned"
    year_files = [p for p in sorted(cleaned_dir.glob("data*.parquet"))
                  if re.match(r"^data\d{4}\.parquet$", p.name)]
    years = sorted({int(re.match(r"^data(\d{4})\.parquet$", p.name).group(1))
                    for p in year_files
                    if re.match(r"^data(\d{4})\.parquet$", p.name).group(1) != "2025"})

    for y in years:
        wide_p = cleaned_dir / f"data{y}.parquet"
        long_p = cleaned_dir / f"data{y}_long.parquet"
        print(f"\n--- {y} wide ---")
        enrich_wide(wide_p, codes_map, str(y))
        if long_p.exists():
            print(f"\n--- {y} long (audit pass) ---")
            enrich_long(long_p, codes_map, code_test_limits)
    print()
    print("--- Propagate audit columns to wide ---")
    for y in years:
        propagate_audit_to_wide_for(y)
    stub_audit_on_2025_wide()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
