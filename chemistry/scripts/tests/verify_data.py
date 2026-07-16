import sys, os, glob
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd, categories as C
A = pd.concat([pd.read_parquet(f) for f in glob.glob("cleaned/*.parquet")],
              ignore_index=True)

# #13 — no Others anywhere
assert (A["sample_category_canonical"] == C.C_OTHER).sum() == 0, "Others still present"

# #11 — no dairy row grouped under a fruit-family label
FRUIT = {"ليمون","برتقال","يوسفي","فراولة","تفاح","عنب","بصل","طماطم","خس","شطة","فلفل"}
dairy = A[A["sample_category_canonical"] == C.C_DAIRY]
bad = dairy[dairy["sample_name_group"].isin(FRUIT)]
assert bad.empty, f"dairy rows mislabelled as fruit: {bad['sample_name'].tolist()[:5]}"

# #4 — all WATER filter samples share one group label; non-water products such
# as «قهوة فلتر» are intentionally NOT relabelled (final review 2026-07-16).
water_cats = {C.W_POTABLE, C.C_NONPOT}
filt = A[(A["sample_name"].astype(str).str.contains("فلتر", na=False))
         & (A["sample_category_canonical"].isin(water_cats))]
assert set(filt["sample_name_group"].unique()) == {C.W_FILTER}, \
    f"filter water not merged: {filt['sample_name_group'].unique()}"
# and non-water فلتر products must NOT be relabelled as filter water
nonwater = A[(A["sample_name"].astype(str).str.contains("فلتر", na=False))
             & (~A["sample_category_canonical"].isin(water_cats))]
assert (nonwater["sample_name_group"] != C.W_FILTER).all(), \
    f"non-water فلتر mislabelled: {nonwater[nonwater['sample_name_group']==C.W_FILTER]['sample_name'].tolist()}"

# #1/#2 (nameless water → tap/bottled): the current corpus has NO nameless
# water rows — every ubot/bot sample already carries a real name — so there is
# nothing to assert here at the data level. The name_group() logic for the
# nameless case is unit-tested directly in scripts/tests/test_categories.py.
print("DATA VERIFY OK  (rows:", len(A), ")")
