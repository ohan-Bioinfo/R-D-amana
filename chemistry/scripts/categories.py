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
C_MISC = "أغذية متنوعة"
# water subtypes (all → GSO "Drinking Water" EXCEPT C_NONPOT)
W_TAP = "مياه الحنفية"; W_FILTER = "مياه فلتر"; W_DRINK = "مياه شرب/معبأة"
C_NONPOT = "مياه غير صالحة للشرب"   # → GSO "Non-potable Water" (2026-07-04)

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
    # nuts → sweets (REVERSED 2026-07-04)
    ("لوز", C_SWEET), ("فستق", C_SWEET), ("كاجو", C_SWEET), ("بندق", C_SWEET),
    ("جوز", C_SWEET), ("مكسرات", C_SWEET), ("ترمس", C_SWEET), ("فول سوداني", C_SWEET),
    # sesame → miscellaneous (REVERSED). Tahini stays a sauce/spice.
    ("طحينة", C_SPICE), ("طحينه", C_SPICE), ("سمسم", C_MISC),
    # pepper → fruit & veg (REVERSED). Before spices so فلفل never reads as spice.
    ("فلفل", C_FRVEG),
    # dried onion → fruit & veg (REVERSED). Before spices.
    ("بصل مجفف", C_FRVEG),
    # raisin / dried fruit, salad, chips, fresh veg → fruit & veg
    ("زبيب", C_FRVEG), ("سلطة", C_FRVEG), ("رقائق", C_FRVEG), ("شيبس", C_FRVEG),
    ("بطاطس", C_FRVEG), ("بصل", C_FRVEG), ("فجل", C_FRVEG), ("فطر", C_FRVEG),
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
    # fish — before meat
    ("سمك", C_FISH), ("تون", C_FISH), ("جمبري", C_FISH), ("روبيان", C_FISH),
    ("سلمون", C_FISH), ("بلطي", C_FISH),
    # meat / poultry
    ("لحم", C_MEAT), ("دجاج", C_MEAT), ("فروج", C_MEAT), ("شاورما", C_MEAT), ("كباب", C_MEAT),
    # dairy
    ("حليب", C_DAIRY), ("لبن", C_DAIRY), ("جبن", C_DAIRY), ("زبادي", C_DAIRY), ("قشطة", C_DAIRY),
    # beverages
    ("عصير", C_BEV), ("شاي", C_BEV), ("كركدي", C_BEV), ("نسكافيه", C_BEV),
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

    # 5. Default.
    return C_MISC, "defaulted"


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
