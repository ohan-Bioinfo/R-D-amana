#!/usr/bin/env python3
"""Canonical sample-category classification for the chemistry pipeline.

Single source of truth for turning a sample into a clean canonical category.

Classification order (2026-07-04 — Muhannad's validated re-classification):
  1. sample_id PREFIX → product → category (PRIMARY key). The lab encodes the
     product in the sample_id prefix (e.g. `al-0100` = لوز/almond, `uu-pe-0510`
     = فلفل/pepper, `zab-…` = زبيب/raisin). This is the most reliable signal and
     overrides mislabeled raw categories (e.g. a meat sample tagged "Tap water").
     Prefix→product decode table: reports/…-Corrected.xlsx tab
     "related-missing-code prefix for".
  2. Water sub-classification by name/raw (tap / filter / bottled / NON-POTABLE).
  3. Sample-name keyword → category (for `1-####` IDs that carry no product
     prefix but name the product).
  4. Raw sample_category keyword.
  5. Default → «أغذية متنوعة» (Miscellaneous), flagged `defaulted`.

Muhannad's 2026-07-04 rulings (reverse the earlier 2026-07-01 taxonomy):
  * Nuts (لوز/فستق/كاجو/بندق/جوز/ترمس/مكسرات) → sweets/chocolate (were grains).
  * فلفل (pepper) → fruit & vegetables (was spices).
  * بصل مجفف (dried onion) → fruit & vegetables (was spices).
  * زبيب (raisin), سلطة (salad), رقائق/شيبس (chips) → fruit & vegetables.
  * سمسم (sesame) → miscellaneous (was grains).
  * هريس/جريش (harees) → cereals; مربى → jelly/jam; حليب… → dairy.
  * NEW category: non-potable water «مياه غير صالحة للشرب» for حوض/راكد/متحرك.
  * Per-section valid-category gating RETIRED — category comes purely from the
    product (prefix/name); no more section-based `suspect` overrides.

Public API:
  classify(section, raw_category, sample_name, sample_id) -> (canonical, flag)
      flag ∈ {None, 'defaulted'}
  name_group(sample_name) -> str | None
"""
from __future__ import annotations
import re

# ------------------------------------------------------------ canonical vocab
C_CEREAL = "الحبوب والبقوليات"; C_SPICE = "البهارات والصوصات"
C_FRVEG = "الفواكه والخضار"; C_SWEET = "الحلويات والشوكولاتة"; C_BEV = "المشروبات"
C_MEAT = "اللحوم والدواجن"; C_FISH = "الأسماك والمأكولات البحرية"; C_DAIRY = "الحليب ومنتجات الألبان"
C_FAT = "الدهون والزيوت"; C_FEED = "الأعلاف"
C_JAM = "المربى والجلي"          # → GSO "Jelly, Jam and Marmalade"
C_RTE = "الأطعمة الجاهزة للأكل"   # → GSO "Ready to Eat Foods" (re-added 2026-07-04 for كشنة)
C_MISC = "أغذية متنوعة"          # RESERVED for sesame only (Muhannad 2026-07-04)
C_OTHER = "أخرى"                 # → GSO "Others" — unclassified / junk leftovers

# Explicit product-name overrides that WIN over the sample_id prefix — for
# products whose lab prefix is wrong/shared (Muhannad 2026-07-04). Black seed
# (حبة البركة / الحبة السوداء) carries a `ses` (sesame) prefix but is a spice;
# كشنة carries a `spic` prefix but Muhannad classes it Ready-to-Eat. Skipped
# for bread items (see classify) so "خبز بالحبة السوداء" stays a cereal.
NAME_OVERRIDE = [
    ("الحبة السوداء", C_SPICE),
    ("حبة البركة", C_SPICE), ("حبةالبركة", C_SPICE),
    ("كشنة", C_RTE),
    # olive oil → fats. Must win over the tuna keyword "تون", which is a
    # substring of "زيتون" (Muhannad 2026-07-04).
    ("زيت زيتون", C_FAT),
]
# water subtypes (all → GSO "Drinking Water" EXCEPT C_NONPOT)
W_TAP = "مياه الحنفية"; W_FILTER = "مياه فلتر"; W_DRINK = "مياه شرب/معبأة"
C_NONPOT = "مياه غير صالحة للشرب"   # → GSO "Non-potable Water" (2026-07-04)
# Water collapses to exactly TWO classes (Muhannad 2026-07-04): potable (tap /
# filter / bottled merged) and non-potable. The tap/filter/bottled constants are
# still used internally by the subtype detector, then merged at the end.
W_POTABLE = "مياه صالحة للشرب"      # → GSO "Drinking Water"

# ---------------------------------------------------------------- prefix table
# sample_id prefix → canonical category. Derived from Muhannad's prefix tab plus
# the 3,093 validated sheet-8 corrections (majority vote; only prefixes with
# solid support or an explicit product decode are listed). Ambiguous prefixes
# (e.g. `pe` = peanut AND pepper) are deliberately omitted so the NAME rules
# below disambiguate them.
PREFIX_TO_CANONICAL = {
    # fruit & vegetables
    "uu-pe": C_FRVEG, "zab": C_FRVEG, "sal": C_FRVEG, "oou-on": C_FRVEG,
    "uu-le": C_FRVEG, "uu-pr": C_FRVEG, "uo-ap": C_FRVEG, "oo-oss-po": C_FRVEG,
    "oau-fi": C_FRVEG, "oau-da": C_FRVEG, "uoss-be": C_FRVEG, "fr": C_FRVEG,
    "mango": C_FRVEG, "veg": C_FRVEG, "co": C_FRVEG,
    # sweets / chocolate  (nuts live here now)
    "al": C_SWEET, "pis": C_SWEET, "lup": C_SWEET, "walnuts": C_SWEET, "cho": C_SWEET,
    # dairy
    "milk": C_DAIRY,
    # miscellaneous  (sesame)
    "ses": C_MISC, "se": C_MISC,
    # spices / sauces
    "cer": C_SPICE, "car": C_SPICE, "spic": C_SPICE, "sau": C_SPICE,
    "salt": C_SPICE, "hs": C_SPICE,
    # cereals / legumes
    "puree": C_CEREAL, "coff": C_CEREAL, "len": C_CEREAL, "lens": C_CEREAL,
    "bea": C_CEREAL, "ma": C_CEREAL, "bu": C_CEREAL, "cor": C_CEREAL,
    # fish
    "sh": C_FISH, "fish": C_FISH,
    # meat
    "raw": C_MEAT,
    # jelly / jam
    "sweet": C_JAM,
}
# prefixes that denote water — routed to the water sub-classifier (name decides
# tap / filter / bottled / non-potable).
WATER_PREFIXES = {"bot", "ubot", "wat", "water"}

_PREFIX_RE = re.compile(r"^([a-z]+(?:-[a-z]+)*)-\d")

# --------------------------------------------------------------- name keywords
# sample-name keyword → canonical (used for rows with no product prefix — mostly
# the aflatoxin `1-####` IDs, and 2024 rows with no raw category). ORDER MATTERS.
NAME_KEYWORDS = [
    # honey / molasses / jam → sweets & jam
    ("مربى", C_JAM),
    ("عسل", C_SWEET), ("دبس", C_SWEET),
    # nuts → sweets (REVERSED 2026-07-04). "سوداني" catches both "فول سوداني" and
    # "فول السوداني" (with the ال article) before the plain "فول"→cereal rule.
    ("لوز", C_SWEET), ("فستق", C_SWEET), ("كاجو", C_SWEET), ("بندق", C_SWEET),
    ("جوز", C_SWEET), ("مكسرات", C_SWEET), ("ترمس", C_SWEET),
    ("فول سوداني", C_SWEET), ("سوداني", C_SWEET), ("صنوبر", C_SWEET), ("بيكان", C_SWEET),
    # sesame → miscellaneous (REVERSED). Tahini stays a sauce/spice.
    ("طحينة", C_SPICE), ("طحينه", C_SPICE), ("سمسم", C_MISC),
    # pepper → fruit & veg (REVERSED). Before spices so فلفل never reads as spice.
    ("فلفل", C_FRVEG),
    # dried onion → fruit & veg (REVERSED). Before spices.
    ("بصل مجفف", C_FRVEG),
    # raisin / dried fruit, salad, chips, fresh veg → fruit & veg
    ("زبيب", C_FRVEG), ("سلطة", C_FRVEG), ("رقائق", C_FRVEG), ("شيبس", C_FRVEG),
    ("بطاطس", C_FRVEG), ("بصل", C_FRVEG), ("فجل", C_FRVEG), ("فطر", C_FRVEG),
    ("خوخ", C_FRVEG), ("دراق", C_FRVEG),   # peach → fruit & veg (2026-07-04)
    # Beverages checked BEFORE the produce sweep so "عصير برتقال" (orange juice)
    # stays a beverage rather than matching برتقال → fruit & veg.
    ("عصير", C_BEV), ("شاي", C_BEV), ("كركدي", C_BEV), ("نسكافيه", C_BEV),
    # Produce sweep — fresh fruits & vegetables the pesticide panel tests that
    # were defaulting to Miscellaneous (Muhannad 2026-07-04: Misc = sesame only).
    ("تفاح", C_FRVEG), ("طماطم", C_FRVEG), ("برتقال", C_FRVEG), ("خيار", C_FRVEG),
    ("كيوي", C_FRVEG), ("جزر", C_FRVEG), ("باذنجان", C_FRVEG), ("ثوم", C_FRVEG),
    ("افوكادو", C_FRVEG), ("رمان", C_FRVEG), ("كوسة", C_FRVEG), ("كوسه", C_FRVEG),
    ("بقدونس", C_FRVEG), ("عنب", C_FRVEG), ("قرع", C_FRVEG), ("جرجير", C_FRVEG),
    ("نعناع", C_FRVEG), ("خس", C_FRVEG), ("موز", C_FRVEG), ("كراث", C_FRVEG),
    ("بطاطا", C_FRVEG), ("شبت", C_FRVEG), ("شمندر", C_FRVEG), ("يوسف", C_FRVEG),
    ("مندرين", C_FRVEG), ("بامية", C_FRVEG), ("باميه", C_FRVEG), ("حبق", C_FRVEG),
    ("فراولة", C_FRVEG), ("توت", C_FRVEG), ("ملفوف", C_FRVEG), ("مانجو", C_FRVEG),
    ("جوافة", C_FRVEG), ("سبانخ", C_FRVEG), ("اناناس", C_FRVEG), ("بروكلي", C_FRVEG),
    ("فاكهة", C_FRVEG), ("كرز", C_FRVEG), ("ملوخية", C_FRVEG), ("برقوق", C_FRVEG),
    ("نكتارين", C_FRVEG), ("لفت", C_FRVEG), ("بابايا", C_FRVEG), ("شمام", C_FRVEG),
    ("زهرة", C_FRVEG), ("رجلة", C_FRVEG), ("رجله", C_FRVEG), ("جريب", C_FRVEG),
    ("بخارة", C_FRVEG),
    # spices / sauces
    ("شط", C_SPICE), ("صلصة", C_SPICE), ("صوص", C_SPICE), ("خل", C_SPICE),
    ("بهار", C_SPICE), ("كركم", C_SPICE), ("زنجبيل", C_SPICE), ("هيل", C_SPICE),
    ("قرفة", C_SPICE), ("كمون", C_SPICE), ("كزبرة", C_SPICE), ("حبة البركة", C_SPICE),
    ("حبةالبركة", C_SPICE),
    # cereals / legumes / grains — coffee lives here (aflatoxin commodity)
    ("قهوة", C_CEREAL), ("قهوه", C_CEREAL),
    ("هريس", C_CEREAL), ("جريش", C_CEREAL), ("جريس", C_CEREAL),
    ("ارز", C_CEREAL), ("أرز", C_CEREAL), ("قمح", C_CEREAL), ("عدس", C_CEREAL),
    ("حمص", C_CEREAL), ("فول", C_CEREAL), ("فاصولي", C_CEREAL), ("ذرة", C_CEREAL),
    ("شعير", C_CEREAL), ("خبز", C_CEREAL), ("توست", C_CEREAL), ("طحين", C_CEREAL),
    ("سميد", C_CEREAL),
    # table olive → fruit & veg — BEFORE the fish block, because "تون" (tuna)
    # is a substring of "زيتون" (olive) and would otherwise steal it.
    ("زيتون", C_FRVEG),
    # fish — before meat
    ("سمك", C_FISH), ("تون", C_FISH), ("جمبري", C_FISH), ("روبيان", C_FISH),
    ("ربيان", C_FISH), ("سلمون", C_FISH), ("بلطي", C_FISH),
    # meat / poultry
    ("لحم", C_MEAT), ("دجاج", C_MEAT), ("فروج", C_MEAT), ("شاورما", C_MEAT), ("كباب", C_MEAT),
    # dairy
    ("حليب", C_DAIRY), ("لبن", C_DAIRY), ("جبن", C_DAIRY), ("زبادي", C_DAIRY), ("قشطة", C_DAIRY),
    # fats
    ("زيت", C_FAT), ("سمن", C_FAT),
    # sweets (bakery/confectionery)
    ("شوكولا", C_SWEET), ("حلاوة", C_SWEET), ("كاكاو", C_SWEET), ("بسكويت", C_SWEET),
    # feed
    ("علف", C_FEED), ("اعلاف", C_FEED),
]

# raw category text (bilingual) → canonical. Last-resort fallback.
CAT_KEYWORDS = [
    ("حبوب", C_CEREAL), ("بقول", C_CEREAL), ("cereal", C_CEREAL), ("legume", C_CEREAL),
    ("بهار", C_SPICE), ("صوص", C_SPICE), ("spice", C_SPICE), ("sauce", C_SPICE),
    ("فواكه", C_FRVEG), ("خضار", C_FRVEG), ("fruit", C_FRVEG), ("vegetable", C_FRVEG),
    ("حلوي", C_SWEET), ("شوكولا", C_SWEET), ("شكولا", C_SWEET), ("sweet", C_SWEET), ("chocolate", C_SWEET),
    ("مشروب", C_BEV), ("beverage", C_BEV),
    ("لحوم", C_MEAT), ("دواجن", C_MEAT), ("meat", C_MEAT), ("poultry", C_MEAT),
    ("أسماك", C_FISH), ("اسماك", C_FISH), ("مأكولات", C_FISH), ("fish", C_FISH), ("seafood", C_FISH),
    ("ألبان", C_DAIRY), ("البان", C_DAIRY), ("حليب", C_DAIRY), ("dairy", C_DAIRY), ("milk", C_DAIRY),
    ("دهون", C_FAT), ("زيوت", C_FAT), ("oil", C_FAT), ("fat", C_FAT),
    ("اعلاف", C_FEED), ("أعلاف", C_FEED), ("fodder", C_FEED), ("feed", C_FEED),
    ("مربى", C_JAM), ("jam", C_JAM), ("jelly", C_JAM),
    ("عسل", C_SWEET), ("honey", C_SWEET), ("دبس", C_SWEET),
]

# water detection + subtype
_WATER_HINTS = ("مياه", "مياة", "موية", "مويه", "حنفي", "فلتر", "معبأ",
                "tap water", "drinking water", "bottled water")
_NONPOTABLE = ("حوض", "راكد", "متحرك")   # basin / standing / mobile → non-potable

_SHATTA = re.compile(r"شط[ةه]")

# Per-section default for unmatched rows. The pesticide panel only tests fresh
# produce, so its leftovers are fruit & veg (Muhannad 2026-07-04: Miscellaneous
# is reserved for sesame). Every other section falls to Miscellaneous.
SECTION_DEFAULT = {"pesticides": C_FRVEG}

# Precise per-sample_id corrections from Muhannad's validated sheet-8
# «التصنيف الصحيح» column (chemistry/scripts/category_corrections.csv). These
# WIN over every rule below — the correction column is the source of truth.
import csv as _csv
from pathlib import Path as _Path

def _load_corrections() -> dict:
    p = _Path(__file__).with_name("category_corrections.csv")
    out = {}
    if p.exists():
        with p.open(encoding="utf-8") as f:
            for row in _csv.DictReader(f):
                sid = (row.get("sample_id") or "").strip()
                cat = (row.get("canonical_category") or "").strip()
                if sid and cat:
                    out[sid] = cat
    return out

CORRECTIONS = _load_corrections()


def _norm(s) -> str:
    return "" if s is None else str(s).strip().strip('"').strip().lower()


def _prefix(sample_id) -> str | None:
    s = _norm(sample_id)
    m = _PREFIX_RE.match(s)
    return m.group(1) if m else None


def _looks_like_water(*texts) -> bool:
    blob = " ".join(_norm(t) for t in texts)
    return any(h.lower() in blob for h in _WATER_HINTS)


def _water_subtype(raw, name) -> str:
    blob = _norm(name) + " " + _norm(raw)
    if any(k in blob for k in _NONPOTABLE):
        return C_NONPOT
    if "فلتر" in blob:
        return W_FILTER
    if any(k in blob for k in ("معبأ", "bottled", "drinking", "شرب")):
        return W_DRINK
    return W_TAP


def _cat_from_name(name) -> str | None:
    s = _norm(name)
    if not s:
        return None
    for kw, canon in NAME_KEYWORDS:
        if kw.lower() in s:
            return canon
    return None


def _cat_from_raw(raw) -> str | None:
    s = _norm(raw)
    if not s or s in ("<na>", "nan", "none"):
        return None
    for kw, canon in CAT_KEYWORDS:
        if kw.lower() in s:
            return canon
    return None


def classify(section, raw_category, sample_name, sample_id=None):
    """Return (canonical_category, flag). flag ∈ {None, 'defaulted'}."""
    canon, flag = _classify_core(section, raw_category, sample_name, sample_id)
    # Pesticide residue testing is done on fresh produce, so anything that reads
    # as a spice or a cereal/legume in that section (كزبرة/زنجبيل, …) is really
    # fruit & veg — convert ALL pesticide spices AND cereals/legumes to fruit &
    # vegetables (Muhannad 2026-07-04).
    if section == "pesticides" and canon in (C_SPICE, C_CEREAL):
        return C_FRVEG, flag
    # Water = exactly two classes: merge tap / filter / bottled into one potable
    # «مياه صالحة للشرب»; non-potable «مياه غير صالحة للشرب» stays separate. This
    # runs last so it also collapses water values coming from the per-sample_id
    # corrections (Muhannad 2026-07-04).
    if canon in (W_TAP, W_FILTER, W_DRINK):
        return W_POTABLE, flag
    return canon, flag


def _classify_core(section, raw_category, sample_name, sample_id=None):
    n = _norm(sample_name)

    # -1. Precise per-sample_id correction from Muhannad's «التصنيف الصحيح»
    #     column — the authoritative source of truth, wins over every rule.
    if sample_id is not None:
        hit = CORRECTIONS.get(str(sample_id).strip())
        if hit:
            return hit, None

    # 0. Explicit product-name overrides — win over the (wrong/shared) prefix.
    #    Bread items skip this so "خبز ... بالحبة السوداء" stays a cereal.
    if "خبز" not in n and "توست" not in n:
        for kw, canon in NAME_OVERRIDE:
            if kw in n:
                return canon, None

    pfx = _prefix(sample_id)

    # 1. Explicit product prefix (overrides mislabeled raw categories).
    if pfx in PREFIX_TO_CANONICAL:
        return PREFIX_TO_CANONICAL[pfx], None

    # 2. Water — by prefix or by text. Sub-classify tap/filter/bottled/non-potable.
    if pfx in WATER_PREFIXES or _looks_like_water(raw_category, sample_name):
        return _water_subtype(raw_category, sample_name), None

    # 3. Sample-name product keyword (nuts/pepper/… reversals applied).
    base = _cat_from_name(sample_name)
    if base:
        return base, None

    # 4. Raw sample_category keyword.
    base = _cat_from_raw(raw_category)
    if base:
        return base, None

    # 5. Default — Miscellaneous is reserved for sesame (ses/سمسم); pesticide
    #    leftovers are fresh produce; everything else unclassified → «أخرى»
    #    (Others), not Miscellaneous (Muhannad 2026-07-04).
    return SECTION_DEFAULT.get(section, C_OTHER), "defaulted"


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
    if "فلفل" in s:
        return "فلفل"
    return None
