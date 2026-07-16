# Jam Section Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ingest the lab's unread `"Jams "` sheet as a new display-only `jam` section so ~84 jam samples appear in the dashboard under GSO "Jelly, Jam and Marmalade".

**Architecture:** Add an `only_sheets` whitelist to the shared sheet iterator so a single named sheet inside a multi-sheet file can be targeted; add a limit-less `chem_jam.yaml` schema that reads it; wire the section into the cleaner, classifier default, and dashboard.

**Tech Stack:** Python 3 (pandas, pyarrow, openpyxl), YAML schemas, self-contained HTML+JS dashboard. No test framework — tests are plain `assert` scripts run with the venv Python.

## Global Constraints

- Venv Python (absolute): `/home/bioinfo/Documents/Data-Analysis-Muhannad/microbiology/.venv/bin/python`. Referenced as `$PY`.
- Work in the isolated worktree `/home/bioinfo/Documents/Data-Analysis-Muhannad-chem-wt`; run python from its `chemistry/` dir; run `git` from the worktree root. Do NOT touch the main repo dir (concurrent microbio session).
- Scope: `chemistry/` + mirror `clean/chemistry/`. Never touch `microbiology/`.
- Jam is **display-only**: all tests have `limit: null` (no pass/fail derivation); validity comes only from the `Matched/not matched` column (1 `غير مطابقة`, 83 blank→unknown).
- Jam category is `المربى والجلي` → GSO "Jelly, Jam and Marmalade". Water stays 2 classes; 5 sectors incl. Central; existing sections must be unchanged.
- Raw source: `chemistry/raw/2024/Food chemistry section.xlsx`, sheet `"Jams "` (trailing space), 84 data rows.

---

### Task 1: `only_sheets` whitelist in the sheet iterator

**Files:**
- Modify: `chemistry/scripts/_common.py` (`iter_data_sheets`, near lines 225 & 236)
- Test: `chemistry/scripts/tests/test_only_sheets.py` (new)

**Interfaces:**
- Produces: `iter_data_sheets(path, year, schema)` honours an optional `schema["only_sheets"]` list — when non-empty, only sheets whose stripped-lowercased name equals or starts with a whitelist token are yielded. When absent/empty, behaviour is unchanged.

- [ ] **Step 1: Write the failing test**

Create `chemistry/scripts/tests/test_only_sheets.py`:

```python
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pathlib import Path
from _common import iter_data_sheets

RAW = Path(__file__).resolve().parents[2] / "raw" / "2024" / "Food chemistry section.xlsx"

# With only_sheets, exactly the "Jams " sheet is read out of the 15-sheet file.
schema = {"single_sheet": True, "only_sheets": ["Jams"], "header_row_max": 4}
sheets = {sn for sn, ym, rows in iter_data_sheets(RAW, 2024, schema)}
assert sheets == {"Jams "}, f"only_sheets should yield just 'Jams ', got {sheets!r}"

# Without only_sheets, single_sheet reads more than one sheet (whitelist really filters).
schema_open = {"single_sheet": True, "header_row_max": 4}
sheets_open = {sn for sn, ym, rows in iter_data_sheets(RAW, 2024, schema_open)}
assert len(sheets_open) > 1, f"expected multiple sheets without whitelist, got {sheets_open!r}"

print("ONLY_SHEETS PASS")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$PY scripts/tests/test_only_sheets.py`
Expected: `AssertionError` on the first assert (currently `only_sheets` is ignored, so all readable sheets are yielded, not just `"Jams "`).

- [ ] **Step 3: Implement the whitelist**

In `chemistry/scripts/_common.py`, in `iter_data_sheets`, add the whitelist read next to `skip_tokens` (currently line 225):

```python
    skip_tokens = [t.lower() for t in schema.get("skip_sheets", [])]
    only_sheets = [t.strip().lower() for t in schema.get("only_sheets", [])]
```

Then inside the `for sn in wb.sheetnames:` loop, immediately after the existing `skip_tokens` skip block:

```python
        if any(t in sn_low for t in skip_tokens):
            continue
```

add:

```python
        if only_sheets:
            sn_norm = sn.strip().lower()
            if not any(sn_norm == t or sn_norm.startswith(t) for t in only_sheets):
                continue
```

- [ ] **Step 4: Run test to verify it passes**

Run: `$PY scripts/tests/test_only_sheets.py`
Expected: `ONLY_SHEETS PASS`

- [ ] **Step 5: Commit**

```bash
git add chemistry/scripts/_common.py chemistry/scripts/tests/test_only_sheets.py
git commit -m "Chem: only_sheets whitelist in iter_data_sheets (target one sheet in a multi-sheet file)"
```

---

### Task 2: Jam schema + classifier default + cleaner wiring

**Files:**
- Create: `chemistry/schemas/chem_jam.yaml`
- Modify: `chemistry/scripts/categories.py:207` (`SECTION_DEFAULT`)
- Modify: `chemistry/scripts/clean_chemistry.py` (lines ~551-553 `--section` choices; lines ~558-560 `all` list)
- Test: `chemistry/scripts/tests/verify_jam.py` (new)
- Regenerate: `chemistry/cleaned/chem_jam_2024.parquet`, `clean/chemistry/chem_jam_2024.parquet`

**Interfaces:**
- Consumes: `only_sheets` support from Task 1.
- Produces: `cleaned/chem_jam_2024.parquet` — 84 rows; `sample_category_canonical == "المربى والجلي"`; columns include `fructose_value`, `glucose_value`, `glucose_plus_fructose_value`, `sucrose_value`, `hmf_value`, `moisture_value`, `ph_value`; `is_valid` False for 1 row, null for 83.

- [ ] **Step 1: Create the jam schema**

Create `chemistry/schemas/chem_jam.yaml`:

```yaml
# Jam (مربى) — the unread "Jams " sheet inside the 2024 Food-chemistry file.
# Sugar/HMF/moisture/pH/acidity panel with NO limit columns → display-only.
# Validity comes solely from the lab's "Matched/not matched" column.
section: jam
applies_to:
  2024: "Food chemistry section.xlsx"

single_sheet: true
only_sheets: ["Jams"]      # matches the "Jams " sheet (trailing space)
skip_sheets: []
header_row_max: 4

columns:
  sampling_date:    ["Receiving Date"]     # only date present → drives the monthly chart
  sample_name:      ["Sample name", "Sample Name"]
  sample_id:        ["Sample ID"]
  facility_name:    ["Facility Name"]
  municipality:     ["Municipality name"]
  validity_raw:     ["Matched/not matched", "Matched/ not matched"]
  fructose:              ["Fructose %"]
  glucose:               ["Glucose %"]
  glucose_plus_fructose: ["(Glucose + Fructose) %"]
  sucrose:               ["Sucrose"]
  maltose:               ["Maltose"]
  carb_qc:               ["Carbohydrate QC %"]
  hmf:                   ["HMF %"]
  concentration:         ["Concentration"]
  moisture:              ["Moisture"]
  ph:                    ["pH"]
  acidity:               ["Acidity"]
  texture:               ["القوام"]
  colour:                ["اللون"]
  testing_notes:         ["Testing Notes"]

tests:
  - { name: "Fructose",           result: fructose,              limit: null, unit: "%" }
  - { name: "Glucose",            result: glucose,               limit: null, unit: "%" }
  - { name: "Glucose + Fructose", result: glucose_plus_fructose, limit: null, unit: "%" }
  - { name: "Sucrose",            result: sucrose,               limit: null, unit: "%" }
  - { name: "Maltose",            result: maltose,               limit: null, unit: "%" }
  - { name: "HMF",                result: hmf,                   limit: null, unit: "%" }
  - { name: "Concentration",      result: concentration,         limit: null, unit: "%" }
  - { name: "Moisture",           result: moisture,              limit: null, unit: "%" }
  - { name: "pH",                 result: ph,                    limit: null }
  - { name: "Acidity",            result: acidity,               limit: null, unit: "%" }
  - { name: "Texture",            result: texture,               kind: string }
  - { name: "Colour",             result: colour,                kind: string }
```

- [ ] **Step 2: Add the classifier section default**

Some rows are typo'd `مربو …` (not `مربى`) so the name keyword misses; the section default catches them. In `chemistry/scripts/categories.py` change line 207 from:

```python
SECTION_DEFAULT = {"pesticides": C_FRVEG, "water_analysis": W_POTABLE}
```

to:

```python
SECTION_DEFAULT = {"pesticides": C_FRVEG, "water_analysis": W_POTABLE, "jam": C_JAM}
```

- [ ] **Step 3: Wire `jam` into the cleaner CLI**

In `chemistry/scripts/clean_chemistry.py`, add `"jam"` to BOTH lists.

Choices (currently lines 551-553) — add `"jam"`:

```python
                    choices=["aflatoxins", "food_chemistry", "heavy_metals", "honey",
                             "hormones_antibiotics", "pesticides", "water_analysis",
                             "jam", "all"])
```

The `all` iteration list (currently lines 558-560) — add `"jam"`:

```python
    sections = [args.section] if args.section != "all" else [
        "aflatoxins", "food_chemistry", "heavy_metals", "honey",
        "hormones_antibiotics", "pesticides", "water_analysis", "jam",
    ]
```

- [ ] **Step 4: Write the jam verification test**

Create `chemistry/scripts/tests/verify_jam.py`:

```python
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
df = pd.read_parquet("cleaned/chem_jam_2024.parquet")

assert len(df) == 84, f"expected 84 jam rows, got {len(df)}"
cats = set(df["sample_category_canonical"].dropna().unique())
assert cats == {"المربى والجلي"}, f"all jam rows must be Jelly/Jam, got {cats}"

# Validity: exactly one غير مطابقة (is_valid False), the rest unknown (null).
false_n = (df["is_valid"] == False).sum()
assert false_n == 1, f"expected 1 non-compliant jam row, got {false_n}"

# Sugar panel populated (display-only values present for most rows).
for col in ["fructose_value", "glucose_value", "glucose_plus_fructose_value",
            "sucrose_value", "hmf_value", "moisture_value", "ph_value"]:
    assert col in df.columns, f"missing column {col}"
    assert df[col].notna().sum() >= 70, f"{col} mostly empty ({df[col].notna().sum()}/84)"

print("JAM VERIFY OK  (rows:", len(df), ")")
```

- [ ] **Step 5: Run the section and the test**

Run:
```bash
$PY scripts/clean_chemistry.py --section jam
cp cleaned/chem_jam_2024.parquet ../clean/chemistry/
$PY scripts/tests/verify_jam.py
```
Expected: cleaner prints `wrote cleaned/chem_jam_2024.parquet  (84 rows; …)` with no traceback, then `JAM VERIFY OK  (rows: 84 )`.

- [ ] **Step 6: Commit**

```bash
git add chemistry/schemas/chem_jam.yaml chemistry/scripts/categories.py chemistry/scripts/clean_chemistry.py chemistry/scripts/tests/verify_jam.py chemistry/cleaned/chem_jam_2024.parquet clean/chemistry/chem_jam_2024.parquet
git commit -m "Chem: new jam section (reads unread Jams sheet, display-only, Jelly/Jam/Marmalade)"
```

---

### Task 3: Dashboard section + full rebuild + regression verify

**Files:**
- Modify: `chemistry/scripts/build_dashboard.py:129-137` (`SECTIONS`)
- Regenerate: all `chemistry/cleaned/*.parquet`, `clean/chemistry/*.parquet`, `chemistry/reports/chemistry_dashboard.html`

**Interfaces:**
- Consumes: `cleaned/chem_jam_2024.parquet` from Task 2.

- [ ] **Step 1: Record the current food_chemistry row counts (regression baseline)**

Write the current counts to a scratch file so Step 4 can compare without manual copying:
```bash
$PY -c "import pandas as pd,json; json.dump({'fc2024':len(pd.read_parquet('cleaned/chem_food_chemistry_2024.parquet')),'fc2025':len(pd.read_parquet('cleaned/chem_food_chemistry_2025.parquet'))}, open('/tmp/jam_fc_baseline.json','w')); print(open('/tmp/jam_fc_baseline.json').read())"
```
Expected: prints the two counts (e.g. `{"fc2024": ..., "fc2025": ...}`). The jam change must not alter them (jam reads only the `"Jams "` sheet; food_chemistry still reads only monthly sheets).

- [ ] **Step 2: Add the dashboard section**

In `chemistry/scripts/build_dashboard.py`, add a `jam` entry to `SECTIONS` after the `honey` line (line 133):

```python
    ("honey",                "Honey analysis",        "Sugars profile, HMF, moisture, acidity (each with its own limit)"),
    ("jam",                  "Jam & jelly",           "Sugar profile (Fructose/Glucose/Sucrose), HMF, moisture, pH — display-only, no GSO limits"),
```

- [ ] **Step 3: Full clean rebuild + mirror + dashboard**

Run:
```bash
$PY scripts/clean_chemistry.py --section all
cp cleaned/*.parquet ../clean/chemistry/
$PY scripts/build_dashboard.py
```
Expected: cleaner prints a `wrote` line for jam plus every other section (no traceback); dashboard builds with no traceback.

- [ ] **Step 4: Verify — jam present, food_chemistry unchanged, existing suites pass**

Run:
```bash
$PY -c "import pandas as pd,json; b=json.load(open('/tmp/jam_fc_baseline.json')); assert len(pd.read_parquet('cleaned/chem_food_chemistry_2024.parquet'))==b['fc2024'] and len(pd.read_parquet('cleaned/chem_food_chemistry_2025.parquet'))==b['fc2025'], 'food_chemistry row count changed!'; print('FOOD_CHEM UNCHANGED')"
$PY scripts/tests/verify_jam.py
$PY -c "h=open('reports/chemistry_dashboard.html',encoding='utf-8').read(); assert 'Jam & jelly' in h and 'chem_jam_2024' not in h; print('JAM TAB OK')"
$PY -c "import re,json; h=open('reports/chemistry_dashboard.html',encoding='utf-8').read(); m=re.search(r'const DATA = (\{.*?\});\n\s*const COLS', h, re.S); d=json.loads(m.group(1)); assert 'jam' in d['sections']; assert d['sections']['jam']['n_total']==84; print('JAM PAYLOAD OK', d['sections']['jam']['n_total'])"
$PY scripts/tests/test_categories.py
$PY scripts/tests/verify_data.py
$PY scripts/tests/verify_dashboard.py
```
Expected: `FOOD_CHEM UNCHANGED`, `JAM VERIFY OK`, `JAM TAB OK`, `JAM PAYLOAD OK 84`, then `ALL PASS` / `DATA VERIFY OK` / `DASHBOARD VERIFY OK`. (The `'Jam & jelly' in h` check confirms the tab label is present; `'chem_jam_2024' not in h` guards against a stray filename leak — the label, not the parquet path, should appear.)

- [ ] **Step 5: Confirm mirror byte-identical**

Run:
```bash
for f in cleaned/*.parquet; do cmp -s "$f" "../clean/chemistry/$(basename "$f")" || echo "MISMATCH $(basename "$f")"; done; echo "mirror check done"
```
Expected: only `mirror check done` (no MISMATCH lines).

- [ ] **Step 6: Commit**

```bash
git add chemistry/scripts/build_dashboard.py chemistry/cleaned/*.parquet clean/chemistry/*.parquet chemistry/reports/chemistry_dashboard.html chemistry/reports/chem_*.md
git commit -m "Dashboard: add Jam & jelly section; full rebuild with jam (#15)"
```

---

## Self-review notes
- **Spec coverage:** only_sheets (Task 1), schema+wiring+classifier default (Task 2), dashboard section + rebuild + regression (Task 3) — every spec section maps to a task. 2024-honey stays out of scope.
- **Non-regression:** Task 3 Step 1/4 pins food_chemistry counts; Steps 4 runs the three existing verify suites so jam doesn't break the earlier corrections.
- **Display-only:** all jam tests carry `limit: null`; validity is lab-verdict-only, matching the spec.
