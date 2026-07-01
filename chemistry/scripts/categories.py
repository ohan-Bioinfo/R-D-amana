#!/usr/bin/env python3
"""Canonical sample-category classification for the chemistry pipeline.

Single source of truth for turning the lab's messy `sample_category` labels
(and, for 2024 rows that have none, the `sample_name`) into a clean canonical
category, with per-section validation and section-aware best-judgment.

Approved rules (2026-07-01 spec, Phase 0 sign-off):
  1. Coffee (قهوة) → الحبوب والبقوليات (valid for aflatoxin; coffee is an
     aflatoxin-tested commodity). Only affects 2024 rows (2025 has raw labels).
  2. Section-aware best-judgment: a category that is invalid for the section is
     overridden by a section-valid category derived from the name when possible
     (e.g. `مياه غسيل ادوات` mislabeled Meat → water). Spice keywords are checked
     before meat so `بهارات دجاج` (chicken *spices*) → spices, not meat. Bare
     `ماء` is NOT a water keyword (it false-matched `ضرماء` = a wheat town).
  3. Name grouping (D4/D5): `فلتر` names → «مياه فلتر»; شطة variants → «شطة»
     (the coffee `قهوة خولاني وشط` is excluded — needs شط + ة/ه).
  4. 2024 leftovers → section-aware default (best-effort), else «أغذية متنوعة».

Public API:
  classify(section, raw_category, sample_name) -> (canonical, flag)
      flag ∈ {None, 'review', 'reclassified', 'suspect', 'defaulted'}
  name_group(sample_name) -> str | None      # display-name group, or None
"""
from __future__ import annotations
import re

# ------------------------------------------------------------ canonical vocab
C_CEREAL = "الحبوب والبقوليات"; C_SPICE = "البهارات والصوصات"; C_RTE = "الأطعمة الجاهزة للأكل"
C_FRVEG = "الفواكه والخضار"; C_SWEET = "الحلويات والشوكولاتة"; C_BEV = "المشروبات"
C_MEAT = "اللحوم والدواجن"; C_FISH = "الأسماك والمأكولات البحرية"; C_DAIRY = "الحليب ومنتجات الألبان"
C_FAT = "الدهون والزيوت"; C_FEED = "الأعلاف"; C_HONEY = "عسل"
W_TAP = "مياه الحنفية"; W_FILTER = "مياه فلتر"; W_DRINK = "مياه شرب/معبأة"
C_MISC = "أغذية متنوعة"

# raw category text (bilingual) -> canonical. First substring hit wins.
CAT_KEYWORDS = [
    ("فلتر", W_FILTER),
    ("حنفي", W_TAP), ("tap water", W_TAP),
    ("معبأ", W_DRINK), ("شرب", W_DRINK), ("bottled", W_DRINK), ("unbottled", W_DRINK),
    ("غير المعبأ", W_DRINK), ("متحرك", W_DRINK), ("drinking", W_DRINK),
    ("حبوب", C_CEREAL), ("بقول", C_CEREAL), ("cereal", C_CEREAL), ("legume", C_CEREAL),
    ("بهار", C_SPICE), ("صوص", C_SPICE), ("spice", C_SPICE), ("sauce", C_SPICE),
    ("جاهز", C_RTE), ("ready to eat", C_RTE),
    ("فواكه", C_FRVEG), ("خضار", C_FRVEG), ("fruit", C_FRVEG), ("vegetable", C_FRVEG),
    ("حلوي", C_SWEET), ("شوكولا", C_SWEET), ("شكولا", C_SWEET), ("sweet", C_SWEET), ("chocolate", C_SWEET),
    ("مشروب", C_BEV), ("beverage", C_BEV),
    ("لحوم", C_MEAT), ("دواجن", C_MEAT), ("meat", C_MEAT), ("poultry", C_MEAT),
    ("أسماك", C_FISH), ("اسماك", C_FISH), ("مأكولات", C_FISH), ("fish", C_FISH), ("seafood", C_FISH),
    ("ألبان", C_DAIRY), ("البان", C_DAIRY), ("حليب", C_DAIRY), ("dairy", C_DAIRY), ("milk", C_DAIRY),
    ("دهون", C_FAT), ("زيوت", C_FAT), ("oil", C_FAT), ("fat", C_FAT),
    ("اعلاف", C_FEED), ("أعلاف", C_FEED), ("fodder", C_FEED), ("feed", C_FEED),
    ("عسل", C_HONEY), ("honey", C_HONEY),
]

# sample-name keyword -> canonical (used when the row has NO raw category, i.e.
# all of 2024). ORDER MATTERS: water & spices are listed before meat so that
# `بهارات دجاج` resolves to spices and `قهوة` (coffee) resolves to grains.
NAME_KEYWORDS = [
    # water — note: NO bare "ماء" (false-matched ضرماء = wheat town)
    ("فلتر", W_FILTER),
    ("مياه", W_TAP), ("مياة", W_TAP), ("موية", W_TAP), ("مويه", W_TAP), ("حنفي", W_TAP), ("المياه", W_TAP),
    # spices / sauces — before meat so chicken-spice → spices
    ("شط", C_SPICE), ("صلصة", C_SPICE), ("صوص", C_SPICE), ("خل", C_SPICE), ("بهار", C_SPICE),
    ("فلفل", C_SPICE), ("كركم", C_SPICE), ("زنجبيل", C_SPICE), ("هيل", C_SPICE), ("قرفة", C_SPICE),
    ("كمون", C_SPICE), ("كزبرة", C_SPICE),
    # cereals / legumes / nuts — coffee (قهوة) lives here per approval #1
    ("قهوة", C_CEREAL), ("قهوه", C_CEREAL),
    ("ارز", C_CEREAL), ("أرز", C_CEREAL), ("قمح", C_CEREAL), ("عدس", C_CEREAL), ("حمص", C_CEREAL),
    ("فول", C_CEREAL), ("فاصولي", C_CEREAL), ("ذرة", C_CEREAL), ("شعير", C_CEREAL), ("لوز", C_CEREAL),
    ("فستق", C_CEREAL), ("كاجو", C_CEREAL), ("بندق", C_CEREAL), ("جوز", C_CEREAL), ("سمسم", C_CEREAL),
    ("ترمس", C_CEREAL), ("جريش", C_CEREAL), ("بر ", C_CEREAL),
    # fish — before meat (تونة etc.)
    ("سمك", C_FISH), ("تون", C_FISH), ("جمبري", C_FISH), ("روبيان", C_FISH), ("سلمون", C_FISH), ("بلطي", C_FISH),
    # meat / poultry
    ("لحم", C_MEAT), ("دجاج", C_MEAT), ("فروج", C_MEAT), ("شاورما", C_MEAT), ("كباب", C_MEAT),
    # dairy
    ("حليب", C_DAIRY), ("لبن", C_DAIRY), ("جبن", C_DAIRY), ("زبادي", C_DAIRY), ("قشطة", C_DAIRY),
    # beverages (coffee intentionally NOT here)
    ("عصير", C_BEV), ("شاي", C_BEV), ("كركدي", C_BEV), ("نسكافيه", C_BEV),
    # others
    ("عسل", C_HONEY),
    ("زيت", C_FAT), ("سمن", C_FAT),
    ("مربى", C_SWEET), ("شوكولا", C_SWEET), ("حلاوة", C_SWEET), ("كاكاو", C_SWEET), ("بسكويت", C_SWEET),
    ("علف", C_FEED), ("اعلاف", C_FEED),
    ("بيض", C_RTE),
]

# per-section valid canonical categories (approved draft).
SECTION_VALID = {
    "aflatoxins":           {C_CEREAL, C_SPICE, C_RTE, C_SWEET},
    "food_chemistry":       {C_CEREAL, C_SPICE, C_RTE, C_FRVEG, C_SWEET, C_BEV,
                             C_MEAT, C_FISH, C_DAIRY, C_FAT, C_FEED, C_HONEY, C_MISC},
    "heavy_metals":         {C_CEREAL, C_SPICE, C_RTE, C_FRVEG, C_SWEET, C_BEV,
                             C_MEAT, C_FISH, C_DAIRY, C_FAT, C_FEED, C_HONEY, C_MISC,
                             W_TAP, W_FILTER, W_DRINK},
    "honey":                {C_HONEY, C_RTE},
    "hormones_antibiotics": {C_MEAT, C_FISH, C_DAIRY},
    "pesticides":           {C_FRVEG, C_CEREAL, C_SPICE, C_RTE, C_DAIRY, C_FAT},
    "water_analysis":       {W_TAP, W_FILTER, W_DRINK},
}
SECTION_REVIEW = {"aflatoxins": {C_FRVEG}}   # allowed but flagged (dried ok, fresh not)
# 2024 leftover default (best-effort). Only sections with a dominant type get a
# real default; mixed sections fall back to Miscellaneous.
SECTION_DEFAULT = {
    "aflatoxins": C_CEREAL, "pesticides": C_FRVEG, "water_analysis": W_TAP,
    "honey": C_HONEY, "hormones_antibiotics": C_MEAT,
    "food_chemistry": C_MISC, "heavy_metals": C_MISC,
}

_SHATTA = re.compile(r"شط[ةه]")   # شطة/شطه/الشطة; excludes وشط (coffee)


def _norm(s) -> str:
    return "" if s is None else str(s).strip().strip('"').strip().lower()


def _cat_from_raw(raw) -> str | None:
    s = _norm(raw)
    if not s or s in ("<na>", "nan", "none"):
        return None
    for kw, canon in CAT_KEYWORDS:
        if kw.lower() in s:
            return canon
    return None


def _cat_from_name(name) -> str | None:
    s = _norm(name)
    if not s:
        return None
    for kw, canon in NAME_KEYWORDS:
        if kw.lower() in s:
            return canon
    return None


def classify(section: str, raw_category, sample_name):
    """Return (canonical_category, flag)."""
    valid = SECTION_VALID.get(section, set())
    review = SECTION_REVIEW.get(section, set())

    base = _cat_from_raw(raw_category)
    if base is None:
        base = _cat_from_name(sample_name)

    if base is None:
        return SECTION_DEFAULT.get(section, C_MISC), "defaulted"

    # Water subtype refinement (D4): a name that says فلتر / معبأ wins over a
    # generic "Tap water" raw label, so filter/bottled water gets its own slice.
    if base in (W_TAP, W_FILTER, W_DRINK):
        nh = _cat_from_name(sample_name)
        if nh in (W_FILTER, W_DRINK) and nh != base:
            base = nh

    if base in valid:
        return base, None
    if base in review:
        return base, "review"

    # invalid for this section — try a section-valid name hint (best-judgment)
    hint = _cat_from_name(sample_name)
    if hint in valid:
        return hint, "reclassified"
    return base, "suspect"      # kept, but flagged for review


def name_group(sample_name) -> str | None:
    """D4/D5 display-name grouping. Returns a group label, or None to keep the
    original name."""
    s = _norm(sample_name)
    if not s:
        return None
    if "فلتر" in s:
        return W_FILTER
    if _SHATTA.search(s):
        return "شطة"
    return None
