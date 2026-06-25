"""Filter audit — replicates each dashboard filter against the embedded payload
to verify correctness and surface semantic duplicates.

Run:
    .venv/bin/python scripts/audit_filters.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent
HTML_PATH = ROOT / "reports" / "data_combined_dashboard.html"
SCHEMA_25 = ROOT / "schemas" / "lab_data_2025_v1.yaml"


def load_payload() -> tuple[pd.DataFrame, dict]:
    html = HTML_PATH.read_text(encoding="utf-8")
    m = re.search(r"const PAYLOAD = (\{.+?\});", html, re.DOTALL)
    payload = json.loads(m.group(1))
    cols = payload["data"]["cols"]
    df = pd.DataFrame(payload["data"]["rows"], columns=cols)
    return df, payload["facets"]


def main() -> None:
    df, facets = load_payload()
    n = len(df)
    with SCHEMA_25.open() as f:
        s = yaml.safe_load(f)
    pathogens = set(s["test_classification"]["pathogen"])
    indicators = set(s["test_classification"]["indicator"])
    tbc_names = set(facets["exclude_constants"]["tbc_names"])
    ym_names = set(facets["exclude_constants"]["yeast_mould_names"])
    raw_meat = set(facets["exclude_constants"]["raw_meat_sample_types"])
    animal_feed = set(facets["exclude_constants"]["animal_feed_sample_types"])

    def has_any(test_list, S):
        return bool(test_list) and any(t in S for t in test_list)

    # ---- Build a dict { filter_name → boolean mask (Series of bool) } ----
    masks: dict[str, pd.Series] = {}
    masks["year_2023"]            = df["year"] == 2023
    masks["year_2024"]            = df["year"] == 2024
    masks["year_2025"]            = df["year"] == 2025
    masks["date_default"]         = df["date"].between(facets["date_min"], facets["date_max"])
    masks["compliance_pass"]      = df["failure"] == 0
    masks["compliance_fail"]      = df["failure"] == 1
    masks["sev_none"]             = df["severity"] == "none"
    masks["sev_indicator_only"]   = df["severity"] == "indicator_only"
    masks["sev_pathogen"]         = df["severity"] == "pathogen"
    masks["sev_multi_pathogen"]   = df["severity"] == "multi_pathogen"
    masks["sector_east"]          = df["sector"] == "فرع أمانة في الشرق"
    masks["sector_north"]         = df["sector"] == "فرع أمانة في الشمال"
    masks["sector_west"]          = df["sector"] == "فرع أمانة في الغرب"
    masks["sector_central"]       = df["sector"] == "فرع أمانة في المنطقة الوسطى"
    masks["sector_south"]         = df["sector"] == "فرع أمانة في الجنوب"
    masks["mun_baladiya"]         = df["mun_type"] == "بلدية"
    masks["mun_qita"]             = df["mun_type"] == "قطاع"
    masks["mun_khas"]             = df["mun_type"] == "خاص"
    for st in facets["sample_types"]:
        masks[f"st_{st}"]         = df["sample_type"] == st
    for cat in facets["gso_categories"][:6]:
        masks[f"gso_cat:{cat[:20]}"] = df["gso_category"] == cat
    masks["microbe_salmonella"]   = df["failed_tests"].apply(lambda lst: "السالمونيلا" in (lst or []))
    masks["microbe_indicator_any"] = df["failed_tests"].apply(lambda lst: has_any(lst, indicators))
    masks["pathogen_only_toggle"] = df["pathogen"] == 1
    masks["repeat_offender"]      = df["ro_count"] >= 2
    masks["panel_incomplete"]     = df["panel_complete"] == 0
    masks["lab_disagree"]         = df["lab_disagree"] == 1
    masks["exclude_raw_meat"]     = ~df["sample_type"].isin(raw_meat)
    masks["exclude_animal_feed"]  = ~df["sample_type"].isin(animal_feed)
    masks["exclude_tbc"]          = df["failed_tests"].apply(lambda lst: not has_any(lst, tbc_names))
    masks["exclude_ym"]           = df["failed_tests"].apply(lambda lst: not has_any(lst, ym_names))
    masks["exclude_indicator_only"] = df["severity"] != "indicator_only"

    # ---- Sanity: each filter selects a sensible count, none are dead ----
    print(f"=== Filter coverage ({n} total rows) ===")
    print(f"{'filter':40s} {'rows':>7s} {'%':>7s}")
    for name, m in masks.items():
        m_count = int(m.sum())
        print(f"  {name:38s} {m_count:7d}  {100*m_count/n:5.1f}%")

    dead = [k for k, v in masks.items() if v.sum() == 0]
    print(f"\nDEAD filters (zero matches): {dead}")

    # ---- Pairwise duplication: any two filters with the EXACT same row set? ----
    print("\n=== Pairwise duplicates (filters with identical row sets) ===")
    keys = list(masks.keys())
    dups = []
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            if masks[keys[i]].equals(masks[keys[j]]):
                dups.append((keys[i], keys[j]))
    if dups:
        for a, b in dups:
            print(f"  {a}  ≡  {b}")
    else:
        print("  (none — every filter has a unique row set)")

    # ---- Semantic overlap: filter A ⊆ filter B (subset)?
    # Identifies redundancies like "Severity=pathogen" ⊆ "Compliance=fail".
    print("\n=== Subset relationships (top 15 by tightness) ===")
    subsets = []
    for a in keys:
        for b in keys:
            if a == b:
                continue
            ma, mb = masks[a], masks[b]
            na, nb = int(ma.sum()), int(mb.sum())
            if na == 0 or nb == 0:
                continue
            if (ma & ~mb).sum() == 0 and na < nb:
                tightness = na / nb
                subsets.append((tightness, a, b, na, nb))
    subsets.sort(key=lambda x: -x[0])
    for t, a, b, na, nb in subsets[:15]:
        print(f"  {a:30s} ⊆ {b:30s}  ({na}/{nb} = {t*100:.0f}%)")

    # ---- Composition test: do the filters AND together correctly?
    # We pick a basket of known-good combinations.
    print("\n=== Composition tests ===")
    tests = [
        ("year=2024 ∧ sev=pathogen",                 masks["year_2024"] & masks["sev_pathogen"]),
        ("year=2024 ∧ sev=pathogen ∧ exclude_raw_meat", masks["year_2024"] & masks["sev_pathogen"] & masks["exclude_raw_meat"]),
        ("year=2025 ∧ sector_central",                masks["year_2025"] & masks["sector_central"]),
        ("year=2024 ∧ panel_incomplete",              masks["year_2024"] & masks["panel_incomplete"]),
        ("year=2024 ∧ lab_disagree",                  masks["year_2024"] & masks["lab_disagree"]),
        ("year=2025 ∧ panel_incomplete",              masks["year_2025"] & masks["panel_incomplete"]),  # should be 0
        ("compliance_pass ∧ sev_pathogen",            masks["compliance_pass"] & masks["sev_pathogen"]),  # should be 0
        ("compliance_fail ∧ sev_none",                masks["compliance_fail"] & masks["sev_none"]),    # should be 0
        ("exclude_tbc ∧ exclude_ym ∧ exclude_indicator_only", masks["exclude_tbc"] & masks["exclude_ym"] & masks["exclude_indicator_only"]),
    ]
    for label, m in tests:
        print(f"  {label:55s} → {int(m.sum())}")


if __name__ == "__main__":
    main()
