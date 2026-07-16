import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import categories as C

def check(got, want, msg):
    assert got == want, f"{msg}: got {got!r}, want {want!r}"

# #11 — fruit family must NOT fire on a dairy product
check(C.name_group("حليب جمل فراولة 2 عينة خاصة", C.C_DAIRY, "milk-0002-r01"),
      "حليب جمل فراولة", "dairy strawberry must not collapse to fruit")
# fruit family DOES fire inside fruit & veg
check(C.name_group("فراولة كوري", C.C_FRVEG, "str-0001-r01"), "فراولة",
      "strawberry in fruit&veg -> فراولة")
# #3 — meat token-order-insensitive
a = C.name_group("لحم عجل كتف بلدي", C.C_MEAT, "meat-1")
b = C.name_group("كتف بلدي عجل لحم", C.C_MEAT, "meat-2")
check(a, b, "meat word-order variants must merge")
# different cut stays separate
assert C.name_group("لحم فخذ عجل بلدي", C.C_MEAT, "m3") != a, "different cut must not merge"
# #4 — every filter-water variant collapses
for n in ["مياة فلتر للعجانة", "موية فلتر", "مياه فلتر للطبخ م ك", "ماء فلتر"]:
    check(C.name_group(n, C.W_POTABLE, "ubot-1-r01"), C.W_FILTER, f"filter collapse: {n}")
# #7 — fish families
check(C.name_group("سمك دنيس ني م.ك", C.C_FISH, "fish-1"), "دنيس", "fish family دنيس")
check(C.name_group("روبيان جامبو بحر", C.C_FISH, "fish-2"), "ربيان", "shrimp family ربيان")
# #1/#2 — nameless water by prefix
check(C.name_group("", C.W_POTABLE, "ubot-0007-r01"), C.W_TAP, "nameless ubot -> tap")
check(C.name_group("", C.W_POTABLE, "bot-0007-r01"), "مياه معبأة", "nameless bot -> bottled")
# #6 — generic suffix/number stripping
check(C.name_group("حليب سادة 3", C.C_DAIRY, "milk-9"), "حليب سادة", "strip trailing number")

# regression: unlisted fish species must be preserved (not mangled by marker regex)
check(C.name_group("سمك صافي", C.C_FISH, "f-1"), "سمك صافي", "unlisted fish preserved")
# marker «م.ك» stripped while «سمك» survives
check(C.name_group("سمك صافي م.ك", C.C_FISH, "f-2"), "سمك صافي", "marker stripped, سمك kept")
# «سمك» inside a non-fish category name must survive the generic path
check(C.name_group("بهارات سمك", C.C_SPICE, "s-1"), "بهارات سمك", "سمك in spice name preserved")

# #14 — كشنة is a spice, not Ready-to-Eat
cat, _ = C.classify("food_chemistry", None, "كشنة بهارات", "spic-0001-r01")
check(cat, C.C_SPICE, "كشنة -> spices")

print("ALL PASS")
