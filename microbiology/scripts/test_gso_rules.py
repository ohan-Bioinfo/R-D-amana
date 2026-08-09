"""Unit tests for the GSO name-rule layer. Run: .venv/bin/python scripts/test_gso_rules.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from enrich_gso import (classify_prepared_to_P as P, classify_sauce_to_G as G,
                        apply_gso_name_rules, load_reference)


def eq(got, exp, msg):
    assert got == exp, f"FAIL {msg}: got {got!r}, expected {exp!r}"


# cooked / prepared -> P (blanket, overrides standard cooked codes)
eq(P("دجاج مشوي"), "P-4", "grilled chicken")
eq(P("دجاج على الفحم"), "P-4", "charcoal chicken")
eq(P("سمك مدخن"), "P-4", "smoked fish -> P (blanket, not D-5)")
eq(P("بطاطس مقلي"), "P-4", "fried potato -> P (blanket, not J-8)")
eq(P("بيض مسلوق"), "P-4", "boiled egg -> P (blanket, not E-1)")
eq(P("رز بخاري مطبوخ"), "P-5", "cooked rice")
eq(P("رز ابيض"), "P-5", "white rice")
eq(P("ملفوف محشي بالرز"), "P-6/4", "stuffed cabbage: stuffed beats rice")
eq(P("ورق عنب"), "P-6/4", "vine leaves (dip/mezze, no cook word)")
eq(P("حمص"), "P-6/4", "hummus dip")
eq(P("متبل باذنجان"), "P-6/4", "mutabbal dip")
eq(P("فلافل"), "P-6/1", "falafel")
eq(P("سمبوسه لحم"), "P-6/2", "samosa")
eq(P("شوربه عدس"), "P-6/2", "soup")
eq(P("كولسلو"), "P-3", "coleslaw")
eq(P("ساندويتش جبن"), "P-2", "sandwich without salad")
eq(P("ساندويتش تركي بسلطه"), "P-1", "sandwich with salad")
eq(P("شاورما دجاج"), "P-4", "shawarma (RTE main)")
# not prepared -> None (leave code alone)
eq(P("جبن شيدر"), None, "raw hard cheese")
eq(P("حليب مبستر"), None, "pasteurized milk")
eq(P("مياه شرب معبأة"), None, "bottled water")

# sauce -> G
eq(G("صوص رانش"), "G-3", "ranch sauce")
eq(G("صوص شوكولاته"), "G-3", "chocolate sauce -> sauces (user rule)")
eq(G("صوص جبن"), "G-3", "cheese sauce -> sauces (overrides A-13)")
eq(G("كاتشب"), "G-2", "ketchup -> tomato")
eq(G("صلصه طماطم"), "G-2", "tomato sauce")
eq(G("جبن شيدر"), None, "no sauce")

# precedence: cooked beats sauce; overrides input codes; tags recorded
nc, tags = apply_gso_name_rules(
    ["بطاطس مقلي بصوص", "صوص ثوم", "دجاج مشوي", "جبن شيدر"],
    ["J-8", "A-13", "C-9", "A-13"])
eq(nc, ["P-4", "G-3", "P-4", "A-13"], "override codes")
eq(tags, ["cooked_to_P", "sauce_to_G", "cooked_to_P", ""], "rule tags")

# every rule-output code must exist in the GSO reference
codes_map, _ = load_reference()
for c in ["P-1", "P-2", "P-3", "P-4", "P-5", "P-6/1", "P-6/2", "P-6/3", "P-6/4", "G-2", "G-3", "N-3"]:
    assert c in codes_map, f"FAIL: rule code {c} missing from gso reference"

print("all rule tests passed")
