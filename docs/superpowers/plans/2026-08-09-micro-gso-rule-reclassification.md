# Microbiology GSO Rule-Based Reclassification — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic sample-name keyword rule layer to `enrich_gso.py` that recodes cooked/prepared foods to Ready-to-Eat (P) and sauces to G across both years, plus a false-friend-safe Group A pass and Group C swab-vs-food rulings — lifting 2025 GSO coverage and unifying the taxonomy.

**Architecture:** All logic lives in `microbiology/scripts/enrich_gso.py`. Pure name→code functions are added first (unit-tested with a plain-`assert` script), then wired into `enrich_wide` (both years) right after the canonical code is computed and before product/category lookup, so category/product/panel all follow the overridden code. Group A is a stricter normalized-equality tier inside `assign_2025_codes_by_name`. The dashboard surfaces a new `gso_code_rule_applied` column.

**Tech Stack:** Python 3.12, pandas, pyarrow, PyYAML; run via `microbiology/.venv/bin/python`. No pytest (not installed) — tests are plain-`assert` scripts run with the venv Python. Node.js for `node --check` on emitted dashboard JS.

**Design spec:** `docs/superpowers/specs/2026-08-09-micro-gso-rule-reclassification-design.md`

## Global Constraints

- Microbiology only. Run everything from `microbiology/` with `PY=.venv/bin/python`.
- Row totals must stay **20,881** (2024 = 9,317; 2025 = 11,564) after every re-clean/enrich.
- Rules apply to **both years** and override 2024 native codes (full-consistency decision).
- Rule precedence per row: **cooked/prepared → P** first, then **sauce → G**, else keep existing code.
- Sandwiches → **P-2**, except **P-1** when name contains salad (`سلطه`/`خس`). Stuffed `محشي` → **P-6/4**.
- Group A uses **normalized-equality only** (no fuzzy, no manual blacklist).
- Every rule output code (`P-1 P-2 P-3 P-4 P-5 P-6/1 P-6/2 P-6/3 P-6/4 G-2 G-3 N-3`) must exist in `schemas/gso_1016_reference.yaml`.
- Commit messages end with: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- After each dashboard rebuild, extract the largest `<script>` and run `node --check` — must pass.

---

### Task 1: Rule primitive functions + unit tests

**Files:**
- Modify: `microbiology/scripts/enrich_gso.py` — add normalization + keyword tables + `classify_prepared_to_P`, `classify_sauce_to_G`, `apply_gso_name_rules` after `_norm_name_2025` (which ends at line 286).
- Create: `microbiology/scripts/test_gso_rules.py` — plain-`assert` unit tests.

**Interfaces:**
- Produces:
  - `classify_prepared_to_P(name: str | None) -> str | None` — returns a P-code or None.
  - `classify_sauce_to_G(name: str | None) -> str | None` — returns `"G-2"`/`"G-3"` or None.
  - `apply_gso_name_rules(names: list, canon: list[str|None]) -> tuple[list[str|None], list[str]]` — returns (new_canon, tags); tags[i] ∈ `{"cooked_to_P","sauce_to_G",""}`.
  - `_norm_rule(s) -> str` — aggressive normalization for keyword matching.

- [ ] **Step 1: Write the failing test**

Create `microbiology/scripts/test_gso_rules.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/lab/storage/Data-Analysis-Muhannad/microbiology
.venv/bin/python scripts/test_gso_rules.py
```
Expected: FAIL — `ImportError: cannot import name 'classify_prepared_to_P'`.

- [ ] **Step 3: Add the rule functions**

In `microbiology/scripts/enrich_gso.py`, immediately after `_norm_name_2025` (after line 286, before `assign_2025_codes_by_name`), insert:

```python
# ---------------------------------------------------------------------------
# Name-keyword GSO rules (Muhannad 2026-08-09): cooked/prepared -> Ready-to-Eat
# (P), sauces -> G. Blanket, both years. Spec:
# docs/superpowers/specs/2026-08-09-micro-gso-rule-reclassification-design.md
def _norm_rule(s) -> str:
    """Aggressive normalisation for keyword matching."""
    if not isinstance(s, str):
        return ""
    s = re.sub(r"[\d٠-٩]+", "", s)          # drop digits
    s = s.replace("ة", "ه")                 # taa marbuta -> haa
    s = re.sub(r"[أإآ]", "ا", s)            # unify alef
    s = re.sub(r"[ىي]", "ي", s)             # unify yaa
    s = re.sub(r"[^\w؀-ۿ]+", " ", s)   # punctuation -> space
    s = re.sub(r"\s+", " ", s).strip()
    return s

# cooking-method triggers (masculine stem catches feminine via substring)
_COOK_KW = ["مقلي", "مطبوخ", "مشوي", "مسلوق", "مدخن", "شوايه", "شواء",
            "على الفحم", "الفحم", "محشي", "محاشي"]
# prepared/RTE nouns that are P even without a cooking word
_PREP_MAIN = ["شاورما", "كباب", "كبه", "برجر", "برغر"]


def classify_prepared_to_P(name) -> str | None:
    """Cooked/prepared item -> Ready-to-Eat P sub-code (or None)."""
    n = _norm_rule(name)
    if not n:
        return None
    has_cook = any(k in n for k in _COOK_KW)
    # sub-code checks, most specific first
    if "كولسلو" in n:
        return "P-3"
    if any(k in n for k in ["فلافل", "بهاجي"]):
        return "P-6/1"
    if any(k in n for k in ["سمبوسه", "شوربه", "بطاطس مهروسه", "تارت", "فلان", "كريم كراميل"]):
        return "P-6/2"
    if any(k in n for k in ["سبرنق رول", "سبرينج رول", "ترايفل"]):
        return "P-6/3"
    if any(k in n for k in ["حمص", "متبل", "بابا غنوج", "ورق عنب", "محشي", "محاشي"]):
        return "P-6/4"
    if any(k in n for k in ["ساندويتش", "ساندوتش"]):
        return "P-1" if ("سلطه" in n or "خس" in n) else "P-2"
    if any(k in n for k in ["رز", "ارز"]):
        return "P-5"
    if has_cook or any(k in n for k in _PREP_MAIN):
        return "P-4"
    return None


def classify_sauce_to_G(name) -> str | None:
    """Sauce -> G (G-2 tomato, G-3 otherwise), or None."""
    n = _norm_rule(name)
    if not n:
        return None
    if any(k in n for k in ["كاتشب", "كتشب", "صلصه طماطم", "صلصه بيتزا", "صلصه الطماطم"]):
        return "G-2"
    if "صوص" in n or "صلصه" in n:
        return "G-3"
    return None


def apply_gso_name_rules(names, canon):
    """Override canonical GSO codes from name rules. Precedence: cooked -> P,
    then sauce -> G, else keep. Returns (new_canon, tags)."""
    new_canon = list(canon)
    tags = [""] * len(canon)
    for i, nm in enumerate(names):
        p = classify_prepared_to_P(nm)
        if p:
            new_canon[i] = p
            tags[i] = "cooked_to_P"
            continue
        g = classify_sauce_to_G(nm)
        if g:
            new_canon[i] = g
            tags[i] = "sauce_to_G"
    return new_canon, tags
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /home/lab/storage/Data-Analysis-Muhannad/microbiology
.venv/bin/python scripts/test_gso_rules.py
```
Expected: `all rule tests passed`.

- [ ] **Step 5: Commit**

```bash
cd /home/lab/storage/Data-Analysis-Muhannad
git add microbiology/scripts/enrich_gso.py microbiology/scripts/test_gso_rules.py
[ "$(git diff --cached --name-only | grep -c chemistry)" = 0 ] && \
git commit -m "GSO rules: add name-keyword classifiers (cooked->P, sauce->G) + tests

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Wire rules into `enrich_wide` (both years) + `gso_code_rule_applied` + long parquet

**Files:**
- Modify: `microbiology/scripts/enrich_gso.py` — `enrich_wide` (canon override + new column + category follow), `enrich_long` (same override on the 2024 long parquet).

**Interfaces:**
- Consumes: `apply_gso_name_rules` (Task 1).
- Produces: wide + long parquets whose `gso_code_canonical` reflects the rules; new wide column `gso_code_rule_applied` (`cooked_to_P` | `sauce_to_G` | None).

- [ ] **Step 1: Override canon inside `enrich_wide`**

In `enrich_gso.py`, find (line 364):
```python
    df["gso_code_canonical"] = pd.array(canon, dtype="string")
```
Replace it with:
```python
    # Name-keyword rule layer (both years): cooked/prepared -> P, sauce -> G.
    canon, rule_tags = apply_gso_name_rules(list(df["sample_name"]), canon)
    df["gso_code_canonical"] = pd.array(canon, dtype="string")
    df["gso_code_rule_applied"] = pd.array(
        [t or None for t in rule_tags], dtype="string")
```

- [ ] **Step 2: Make category follow the code for rule-applied rows (2025 too)**

In `enrich_wide`, find the category block guard (line 380):
```python
    if derive_categories and "category_canonical" in df.columns:
```
Replace the whole `if` header and its loop opener so rule-applied rows always derive category from the (overridden) code, even when `derive_categories=False` (2025). Change the block to:

```python
    if "category_canonical" in df.columns:
        cat_canonical = list(df["category_canonical"])
        cat_en = list(df["category_en"])
        sample_type = list(df["sample_type"])
        for i, (code, gso_cat_en, tag) in enumerate(
                zip(canon, df["gso_category_name_en"], rule_tags)):
            if not derive_categories and not tag:
                continue  # 2025 non-rule rows keep cleaner categories
            if code and gso_cat_en is not None and not pd.isna(gso_cat_en):
                cc, ce = GSO_CATEGORY_TO_DISPLAY.get(
                    str(gso_cat_en), (str(gso_cat_en), str(gso_cat_en)))
                cat_canonical[i] = cc
                cat_en[i] = ce
                sample_type[i] = classify_sample_type_from_en(ce)
            elif derive_categories:
                cat_canonical[i] = "(Swabs) المسحات"
                cat_en[i] = "Swabs"
                sample_type[i] = "swab"
        df["category_canonical"] = pd.array(cat_canonical, dtype="string")
        df["category_en"] = pd.array(cat_en, dtype="string")
        df["sample_type"] = pd.array(sample_type, dtype="string")
```

Note: this reads `df["category_en"]`/`df["sample_type"]` as existing columns (present on both years after clean/prior enrich). The 2025 stub-column branch (lines 333-344, no `gso_code`) is unaffected — rules run only when a `gso_code` column exists, which 2025 has after `assign_2025_codes_by_name`.

- [ ] **Step 3: Apply the same override in `enrich_long` (2024 panel keys)**

In `enrich_gso.py`, find in `enrich_long` (line 417-418):
```python
    canon = [normalise_gso_code(v) for v in df["gso_code"]]
    df["gso_code_canonical"] = pd.array(canon, dtype="string")
```
Replace with:
```python
    canon = [normalise_gso_code(v) for v in df["gso_code"]]
    canon, _long_tags = apply_gso_name_rules(list(df["sample_name"]), canon)
    df["gso_code_canonical"] = pd.array(canon, dtype="string")
```

- [ ] **Step 4: Run the pipeline and verify counts + rule tallies**

```bash
cd /home/lab/storage/Data-Analysis-Muhannad/microbiology
.venv/bin/python scripts/clean_2024.py --year 2024
.venv/bin/python scripts/clean_2025.py "2025-original/Data 2025.xlsx" cleaned/data2025.parquet reports/data2025_diff.md
.venv/bin/python scripts/enrich_gso.py 2>&1 | tail -20
.venv/bin/python - <<'PY'
import pandas as pd
tot=0
for y in (2024,2025):
    d=pd.read_parquet(f"cleaned/data{y}.parquet"); tot+=len(d)
    ra=d["gso_code_rule_applied"].value_counts(dropna=True).to_dict()
    coded=(d["gso_code_canonical"].notna()).sum()
    print(f"{y}: rows={len(d)} coded={coded} ({100*coded/len(d):.1f}%) rule_applied={ra}")
print("TOTAL rows:", tot, "(expect 20881)")
assert tot==20881, "row total drifted!"
PY
```
Expected: total 20,881; `cooked_to_P` ≈ 941 and `sauce_to_G` ≈ 2,896 combined across years (±normalisation drift); 2025 coded % clearly above 36.9%.

- [ ] **Step 5: Commit**

```bash
cd /home/lab/storage/Data-Analysis-Muhannad
git add microbiology/scripts/enrich_gso.py microbiology/cleaned/data2024.parquet \
        microbiology/cleaned/data2024_long.parquet microbiology/cleaned/data2025.parquet
[ "$(git diff --cached --name-only | grep -c chemistry)" = 0 ] && \
git commit -m "GSO rules: apply cooked->P / sauce->G to wide+long parquets, both years

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Group A — strict normalized-equality tier (2025 spelling variants)

**Files:**
- Modify: `microbiology/scripts/enrich_gso.py` — add `_norm_name_strict`; extend `assign_2025_codes_by_name` with a Tier-1b strict-equality pass.
- Modify: `microbiology/scripts/test_gso_rules.py` — add false-friend assertions.

**Interfaces:**
- Consumes: `normalise_gso_code`, `_norm_name_2025` (existing).
- Produces: `_norm_name_strict(s) -> str | None`; `assign_2025_codes_by_name` now also assigns strict-equality single-code matches for rows still uncoded after Tier 1/Tier 2.

- [ ] **Step 1: Add the false-friend test (failing)**

Append to `microbiology/scripts/test_gso_rules.py` before the final `print`:

```python
from enrich_gso import _norm_name_strict
# strict normalisation collapses spacing/punct/ال/ya but NEVER a content-word swap
eq(_norm_name_strict("سلطة كولسلو") == _norm_name_strict("سلطه كول سلو"), True,
   "coleslaw spacing variant collapses")
eq(_norm_name_strict("جبنة بيتزا") == _norm_name_strict("لبنه بيتزا"), False,
   "cheese vs labneh must NOT collapse (false friend)")
eq(_norm_name_strict("لحم سبايسي") == _norm_name_strict("حمص سبايسي"), False,
   "meat vs hummus must NOT collapse (false friend)")
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd /home/lab/storage/Data-Analysis-Muhannad/microbiology
.venv/bin/python scripts/test_gso_rules.py
```
Expected: FAIL — `cannot import name '_norm_name_strict'`.

- [ ] **Step 3: Add `_norm_name_strict` + Tier-1b**

In `enrich_gso.py`, immediately after `_norm_name_2025` (line 286) add:

```python
def _norm_name_strict(s) -> str | None:
    """Stricter than _norm_name_2025: also unify yaa, drop leading ال,
    remove all spaces and punctuation. Two names are 'the same product' only
    when their strict forms are EQUAL — never a fuzzy match, so cheese/labneh
    and similar false friends can never collapse."""
    if not isinstance(s, str):
        return None
    s = re.sub(r"[\d٠-٩]+", "", s)
    s = s.replace("ة", "ه")
    s = re.sub(r"[أإآ]", "ا", s)
    s = re.sub(r"[ىي]", "ي", s)
    s = re.sub(r"[^؀-ۿ]+", "", s)   # keep Arabic letters only
    s = re.sub(r"^ال", "", s)
    return s or None
```

Then in `assign_2025_codes_by_name`, after the Tier-1 `learned` dict is built (after line 302) add the strict map:

```python
    d24["ns"] = d24["sample_name"].map(_norm_name_strict)
    codes_per_strict = d24.dropna(subset=["ns"]).groupby("ns")["canon"].agg(lambda s: set(s))
    learned_strict = {n: next(iter(c)) for n, c in codes_per_strict.items() if len(c) == 1}
```

And in the per-row assignment loop, change (lines 306-310):
```python
    for n in norms:
        code = None
        if n is not None:
            code = NAME_TO_CODE_2025.get(n) or learned.get(n)
        codes.append(code)
```
to also try the strict map (Tier-1b) for rows still uncoded:
```python
    strict_norms = df["sample_name"].map(_norm_name_strict)
    for n, ns in zip(norms, strict_norms):
        code = None
        if n is not None:
            code = NAME_TO_CODE_2025.get(n) or learned.get(n)
        if code is None and ns is not None:
            code = learned_strict.get(ns)   # Tier-1b: strict-equality only
        codes.append(code)
```

- [ ] **Step 4: Run tests + pipeline, verify no false friends assigned**

```bash
cd /home/lab/storage/Data-Analysis-Muhannad/microbiology
.venv/bin/python scripts/test_gso_rules.py            # expect: all rule tests passed
.venv/bin/python scripts/enrich_gso.py 2>&1 | grep "2025 name-based"
.venv/bin/python - <<'PY'
import pandas as pd
d=pd.read_parquet("cleaned/data2025.parquet")
# the 8 flagged false-friend 2025 names must NOT receive the false code
ff={"ليمون مشوي":"D-5","لحم بري":"C-9","بسبوسة جبن":"P-6/2","جبنة بالخضار":"A-3",
    "صوص حمص":"G-3"}  # note: صوص حمص correctly G-3 via sauce rule, not the FF code
for nm,bad in {"ليمون مشوي":"D-5","لحم بري":"C-9","جبنة بالخضار":"A-3"}.items():
    rows=d[d["sample_name"]==nm]
    if len(rows):
        got=set(rows["gso_code_canonical"].dropna())
        assert bad not in got, f"FALSE FRIEND: {nm} got {bad}"
        print(f"ok: {nm} -> {got or 'uncoded'} (not {bad})")
print("false-friend guard verified")
PY
```
Expected: coverage line shows a higher coded count; false-friend guard passes.

- [ ] **Step 5: Commit**

```bash
cd /home/lab/storage/Data-Analysis-Muhannad
git add microbiology/scripts/enrich_gso.py microbiology/scripts/test_gso_rules.py \
        microbiology/cleaned/data2025.parquet
[ "$(git diff --cached --name-only | grep -c chemistry)" = 0 ] && \
git commit -m "GSO Group A: strict normalized-equality tier for 2025 (false-friend-safe)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Group C — swab-vs-food rulings + wash-water → N-3

**Files:**
- Modify: `microbiology/scripts/enrich_gso.py` — add `reclassify_group_c(df)` and call it inside `enrich_wide` after the category block, before `df.to_parquet` (line 399).

**Interfaces:**
- Consumes: nothing new.
- Produces: rows named as wash-water get `gso_code_canonical = "N-3"` and category Drinking Water; food-named rows currently typed `swab` but carrying a food code get `sample_type` off `swab`.

- [ ] **Step 1: Add `reclassify_group_c`**

In `enrich_gso.py`, after `classify_sauce_to_G` / `apply_gso_name_rules` (Task 1 block), add:

```python
_WASHWATER_KW = ["مياه غسيل", "مياه حنفيه لغسيل", "مياه فلتر لغسيل", "غسيل الادوات",
                 "غسيل الاسماك", "مياه غسيل ادوات"]


def reclassify_group_c(df):
    """Group C: rows whose name is wash-water -> N-3 (unbottled/wash water);
    food-named rows still typed swab but carrying a food code -> drop swab typing.
    Operates in place on category/sample_type/gso_code_canonical."""
    if "sample_type" not in df.columns:
        return
    cc = list(df["category_canonical"]); ce = list(df["category_en"])
    st = list(df["sample_type"]); gc = list(df["gso_code_canonical"])
    for i, nm in enumerate(df["sample_name"]):
        nn = _norm_rule(nm)
        if nn and any(_norm_rule(k) in nn for k in _WASHWATER_KW):
            gc[i] = "N-3"; cc[i] = "مياه الشرب"; ce[i] = "Drinking Water"; st[i] = "water"
        elif st[i] == "swab" and gc[i] and not str(gc[i]).startswith("N"):
            # food code but typed swab -> not a swab
            st[i] = "food"
    df["gso_code_canonical"] = pd.array(gc, dtype="string")
    df["category_canonical"] = pd.array(cc, dtype="string")
    df["category_en"] = pd.array(ce, dtype="string")
    df["sample_type"] = pd.array(st, dtype="string")
```

- [ ] **Step 2: Call it in `enrich_wide`**

In `enrich_wide`, immediately before `df.to_parquet(path, compression="zstd", index=False)` (line 399), add:
```python
    reclassify_group_c(df)
```

- [ ] **Step 3: Run pipeline + verify the 9 Group C rows**

```bash
cd /home/lab/storage/Data-Analysis-Muhannad/microbiology
.venv/bin/python scripts/enrich_gso.py 2>&1 | tail -3
.venv/bin/python - <<'PY'
import pandas as pd
d=pd.read_parquet("cleaned/data2025.parquet")
ww=d[d["sample_name"].astype(str).str.contains("غسيل")]
print("wash-water rows now N-3:", set(ww["gso_code_canonical"].dropna()),
      "| sample_type:", set(ww["sample_type"].dropna()))
# food-named swab example
for nm in ["تشيز كيك توت","سلطة خضراء","رمان حب"]:
    r=d[d["sample_name"]==nm]
    if len(r): print(nm, "->", set(r["sample_type"].dropna()), set(r["gso_code_canonical"].dropna()))
PY
```
Expected: wash-water rows show `N-3` / `water`; food-named rows no longer `swab`.

- [ ] **Step 4: Commit**

```bash
cd /home/lab/storage/Data-Analysis-Muhannad
git add microbiology/scripts/enrich_gso.py microbiology/cleaned/data2025.parquet \
        microbiology/cleaned/data2024.parquet
[ "$(git diff --cached --name-only | grep -c chemistry)" = 0 ] && \
git commit -m "GSO Group C: wash-water->N-3, food-named swabs reclassified

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Dashboard surfacing + Group B review doc + regenerate + verify

**Files:**
- Modify: `microbiology/scripts/build_dashboard_combined.py` — add `gso_code_rule_applied` to the per-row payload `DATA_COLS` and a count line in the GSO-audit card explainer.
- Create: `kimi/yolo/2025_gso_groupB_disambiguation.md` — proposed code per ambiguous name.
- Modify: `microbiology/CHANGELOG.md` — new entry.
- Rebuild: `microbiology/reports/microbiology_dashboard.html`, `microbiology_sunburst.html`, `microbiology_sunburst2.html`.

**Interfaces:**
- Consumes: `gso_code_rule_applied` column (Task 2).

- [ ] **Step 1: Surface the rule column in the dashboard payload**

```bash
cd /home/lab/storage/Data-Analysis-Muhannad/microbiology
grep -n "DATA_COLS\|dq_flags\|sample_type" scripts/build_dashboard_combined.py | head
```
Add `"gso_code_rule_applied"` to the `DATA_COLS` list (follow the exact list style at the grep hit; append the string to the list literal). If the column may be absent on older parquets, guard the read: where `DATA_COLS` is selected from the dataframe, ensure missing columns are filled — search for where `DATA_COLS` is used and add, right before it:
```python
for _c in DATA_COLS:
    if _c not in combined.columns:
        combined[_c] = None
```

- [ ] **Step 2: Add a rule-reclassified count to the GSO-audit explainer**

```bash
grep -n "GSO 1016 audit\|incomplete\|systematic\|panel_gap_kind" scripts/build_dashboard_combined.py | head
```
In the GSO-audit card HTML/JS (near the "incomplete panel" explainer), add a line rendering the count of rows where `gso_code_rule_applied` is non-null, labelled e.g. `↳ re-coded by name rule (cooked→P / صوص→G): <n>`. Follow the surrounding render pattern (reuse an existing count-from-payload helper).

- [ ] **Step 3: Generate the Group B review doc**

```bash
cd /home/lab/storage/Data-Analysis-Muhannad/microbiology
.venv/bin/python - <<'PY'
import pandas as pd, re
from pathlib import Path
d=pd.read_parquet("cleaned/data2025.parquet")
un=d[d["gso_code_canonical"].isna()]
# names still uncoded after rules+GroupA, ranked by row count
top=un["sample_name"].value_counts().head(120)
lines=["# 2025 GSO Group B — disambiguation review (2026-08-09)","",
       "Names still uncoded after rules + Group A. Pick a code per row (or leave blank).","",
       "| 2025 name | rows | proposed code | your code |","|---|---|---|---|"]
for nm,c in top.items():
    lines.append(f"| {nm} | {c} |  |  |")
Path("/home/lab/storage/Data-Analysis-Muhannad/kimi/yolo/2025_gso_groupB_disambiguation.md").write_text("\n".join(lines),encoding="utf-8")
print("wrote review doc with", len(top), "names")
PY
```

- [ ] **Step 4: Regenerate dashboards + `node --check`**

```bash
cd /home/lab/storage/Data-Analysis-Muhannad/microbiology
.venv/bin/python scripts/build_dashboard_combined.py 2>&1 | tail -2
.venv/bin/python scripts/build_micro_sunburst.py 2>&1 | tail -1
.venv/bin/python scripts/build_micro_sunburst2.py 2>&1 | tail -1
.venv/bin/python - <<'PY'
import re
html=open("reports/microbiology_dashboard.html",encoding="utf-8").read()
big=max(re.findall(r"<script>(.*?)</script>", html, re.S), key=len)
open("/tmp/dash.js","w").write(big)
PY
node --check /tmp/dash.js && echo "DASH JS OK"
```
Expected: dashboard prints `20881 rows`; `DASH JS OK`.

- [ ] **Step 5: Final reconciliation checks**

```bash
cd /home/lab/storage/Data-Analysis-Muhannad/microbiology
.venv/bin/python - <<'PY'
import pandas as pd
tot=0; ra={}
for y in (2024,2025):
    d=pd.read_parquet(f"cleaned/data{y}.parquet"); tot+=len(d)
    for k,v in d["gso_code_rule_applied"].value_counts().items(): ra[k]=ra.get(k,0)+int(v)
    coded=int(d["gso_code_canonical"].notna().sum())
    print(f"{y}: rows={len(d)} coded={coded} ({100*coded/len(d):.1f}%)")
print("rule_applied totals:", ra, "| grand total rows:", tot)
assert tot==20881
PY
```
Manual spot-check: open `reports/microbiology_sunburst.html`, confirm cooked items appear under Ready-to-Eat and صوص under Sauces; eyeball ~10 names.

- [ ] **Step 6: CHANGELOG + commit + push**

Add a CHANGELOG entry summarising the rule layer, counts (cooked→P, صوص→G, Group A added, Group C), and downstream deltas. Then:
```bash
cd /home/lab/storage/Data-Analysis-Muhannad
git add microbiology/scripts/build_dashboard_combined.py \
        microbiology/reports/microbiology_dashboard.html \
        microbiology/reports/microbiology_sunburst.html \
        microbiology/reports/microbiology_sunburst2.html \
        microbiology/CHANGELOG.md kimi/yolo/2025_gso_groupB_disambiguation.md
[ "$(git diff --cached --name-only | grep -c chemistry)" = 0 ] && \
git commit -m "Dashboard: surface GSO rule reclassification; Group B review doc; rebuild

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
git push origin main
```

---

## Self-Review

**Spec coverage:**
- Rule 1 cooked→P (sub-codes, blanket, both years) → Task 1 (functions) + Task 2 (wired to wide+long) ✓
- Rule 2 صوص→G (G-2/G-3) → Task 1 + Task 2 ✓
- Precedence cooked-before-sauce → `apply_gso_name_rules` (Task 1), tested ✓
- Group A normalized-equality guard → Task 3 (`_norm_name_strict` + Tier-1b), false-friend test ✓
- Group B review doc (not auto-applied) → Task 5 Step 3 ✓
- Group C wash-water→N-3 + food-named swab reclass → Task 4 ✓
- `gso_code_rule_applied` column + dashboard surfacing → Task 2 + Task 5 ✓
- Both-years scope, 20,881 invariant, category follows code → Task 2 (category block edit) + verify steps ✓
- Downstream (panels/category shift) recomputed by re-running enrich+dashboard → Task 5 ✓

**Placeholder scan:** All steps carry real code or exact grep-anchored edits. The two grep-anchored steps in Task 5 (payload list + audit-card render) point at existing patterns to follow because the exact surrounding lines vary; every other step has literal code. No TBD/TODO.

**Type consistency:** `classify_prepared_to_P`, `classify_sauce_to_G`, `apply_gso_name_rules(names, canon)->(new_canon, tags)`, `_norm_rule`, `_norm_name_strict`, `reclassify_group_c(df)` used with identical signatures across Tasks 1–4. Column name `gso_code_rule_applied` identical in Tasks 2 and 5.
