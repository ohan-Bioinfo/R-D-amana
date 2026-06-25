"""Risk-assessment scoring for chemistry + microbiology samples.

Per-sample risk_score (0-100), tier (None/Low/Medium/High/Critical), and the
top 3 risk drivers (strings explaining what drove the score).

Composite = max(chem_component, micro_component) + 5 if both invalid.

Imported by build_joint_dashboard.py; can also be run standalone to print
top-risk samples per dataset.
"""
from __future__ import annotations

from pathlib import Path
import pandas as pd
import re

ROOT = Path(__file__).resolve().parent.parent
CHEM_DIR = ROOT / "chemistry"
MICRO_DIR = ROOT / "microbiology"

# --- Contaminant criticality weights -----------------------------------------
# Match against the test_canonical / metal / pesticide / aflatoxin name.
# Higher = more weight on the exceedance ratio.
WEIGHTS = {
    # Toxic heavy metals (highest weight)
    "lead": 1.0, "mercury": 1.0, "cadmium": 1.0, "arsenic": 1.0,
    # Mycotoxins
    "aflatoxin": 1.0, "b1": 1.0, "b2": 1.0, "g1": 1.0, "g2": 1.0,
    "total": 1.0,
    # Banned/restricted pesticides — checked via the banned_restricted column
    "banned": 1.0, "restricted": 0.8,
    # Other heavy metals (nutritional / lower acute toxicity)
    "copper": 0.5, "zinc": 0.5, "iron": 0.5, "manganese": 0.5,
    "calcium": 0.4, "potassium": 0.4, "magnesium": 0.4, "sodium": 0.4,
    "silver": 0.6, "aluminum": 0.6, "barium": 0.6, "beryllium": 0.7,
    "chromium": 0.7, "cesium": 0.5, "cobalt": 0.6, "nickel": 0.7,
    "selenium": 0.6, "strontium": 0.5, "rubidium": 0.4,
    "uranium": 0.9, "vanadium": 0.6,
    # Honey-quality tests (process-control, not toxicity)
    "sucrose": 0.4, "hmf": 0.5, "glucose": 0.3, "fructose": 0.3,
    "moisture": 0.4, "acidity": 0.4,
    # Food chemistry
    "ph": 0.4, "ash": 0.3, "concentration": 0.3,
    "refractive_index": 0.3, "rancidity": 0.5, "peroxide": 0.5,
    "fat": 0.3, "total_solids": 0.3, "total_solids_nonfat": 0.3,
    "acid_number": 0.4,
    # Water analysis
    "fluoride": 0.6, "nitrate": 0.7, "nitrite": 0.8,
    "free_chlorine": 0.5, "tds": 0.4, "turbidity": 0.5,
    # Default
    "_default": 0.6,
}


def exceedance_score(ratio: float) -> int:
    """Map value/limit ratio to a base score (0–90)."""
    if ratio is None or ratio < 1.0:
        return 0
    if ratio < 2.0:
        return 25
    if ratio < 5.0:
        return 50
    if ratio < 10.0:
        return 70
    return 90


def weight_for(name: str) -> float:
    if not name:
        return WEIGHTS["_default"]
    n = name.lower()
    for key, w in WEIGHTS.items():
        if key in n:
            return w
    return WEIGHTS["_default"]


def chem_risk_for_row(row: pd.Series, section: str) -> tuple[float, list[str]]:
    """Risk for one chemistry parquet row. Returns (score, drivers)."""
    drivers = []
    score = 0.0

    # Pesticide long-format: one detected pesticide per row
    if section == "pesticides":
        if pd.notna(row.get("concentration_ppm")) and pd.notna(row.get("limit_ppm")):
            v = float(row["concentration_ppm"]); l = float(row["limit_ppm"])
            if l > 0:
                ratio = v / l
                if ratio > 1:
                    name = row.get("pesticide_name", "pesticide") or "pesticide"
                    # Banned/restricted bump
                    br = str(row.get("banned_restricted", "")).lower()
                    if "محظور" in br or "banned" in br:
                        w = 1.0
                    elif "مقيد" in br or "restricted" in br:
                        w = 0.8
                    else:
                        w = 0.6
                    s = exceedance_score(ratio) * w
                    if s > score:
                        score = s
                        drivers = [f"{name} {ratio:.1f}× limit"]
        return score, drivers

    # Wide sections: scan every *_value / *_limit_value pair
    for col in row.index:
        if not col.endswith("_value") or col.endswith("_limit_value"):
            continue
        v = row[col]
        limit_col = col.replace("_value", "_limit_value")
        if pd.isna(v) or limit_col not in row.index:
            continue
        l = row[limit_col]
        if pd.isna(l) or float(l) <= 0:
            continue
        v_f, l_f = float(v), float(l)
        if v_f <= l_f:
            continue
        ratio = v_f / l_f
        # Test name = column root (strip _value)
        name = col[:-6]
        w = weight_for(name)
        s = exceedance_score(ratio) * w
        if s > score:
            score = s
            drivers = [f"{name} {ratio:.1f}× limit"]
        elif s >= score * 0.7 and s > 0:
            drivers.append(f"{name} {ratio:.1f}×")
    return score, drivers[:3]


def _to_str(v):
    """Defensive: arrays/lists/np.NA -> string or empty."""
    try:
        if v is None: return ""
        if isinstance(v, (list, tuple)):
            return ", ".join(str(x) for x in v if x is not None)
        if hasattr(v, "tolist"):
            arr = v.tolist()
            return ", ".join(str(x) for x in arr if x is not None) if arr else ""
        if pd.isna(v): return ""
        return str(v).strip()
    except Exception:
        try: return str(v)
        except Exception: return ""


def micro_risk_for_row(row: pd.Series) -> tuple[float, list[str]]:
    """Risk for one microbiology wide-parquet row."""
    sev = _to_str(row.get("severity_tier"))
    if not sev:
        if row.get("is_valid") == False:
            return 30.0, ["microbiological failure"]
        return 0.0, []
    sev = sev.lower()
    mapping = {"none": 0, "indicator_only": 30, "pathogen": 65, "multi_pathogen": 95}
    score = float(mapping.get(sev, 0))
    drivers = []
    if score > 0:
        fp = _to_str(row.get("failed_pathogens"))
        fi = _to_str(row.get("failed_indicators"))
        if fp:
            drivers.append(f"pathogen: {fp}")
        if fi:
            drivers.append(f"indicator: {fi}")
        if not drivers and sev != "none":
            drivers.append(sev)
    return score, drivers[:3]


def to_tier(score: float) -> str:
    if score <= 0: return "None"
    if score < 26: return "Low"
    if score < 51: return "Medium"
    if score < 76: return "High"
    return "Critical"


def compute_per_sample_risk():
    """Returns dict (year, lc_sample_id) -> {chem_score, micro_score, drivers}."""
    by_sample: dict = {}

    # Chemistry
    for p in sorted(CHEM_DIR.glob("chem_*_*.parquet")):
        m = re.match(r"chem_(.+)_(\d{4})\.parquet$", p.name)
        if not m: continue
        section, year = m.group(1), int(m.group(2))
        df = pd.read_parquet(p)
        df = df[df["sample_id"].notna()].copy()
        df["_sid"] = df["sample_id"].astype(str).str.lower()
        for _, r in df.iterrows():
            key = (year, r["_sid"])
            slot = by_sample.setdefault(key, {
                "chem_score": 0.0, "chem_drivers": [],
                "micro_score": 0.0, "micro_drivers": [],
                "chem_invalid": False, "micro_invalid": False,
            })
            s, d = chem_risk_for_row(r, section)
            if s > slot["chem_score"]:
                slot["chem_score"] = s
                # Replace drivers with these (highest takes precedence)
                slot["chem_drivers"] = [f"[{section}] {x}" for x in d]
            elif s > 0 and len(slot["chem_drivers"]) < 3:
                slot["chem_drivers"].extend(f"[{section}] {x}" for x in d[:3-len(slot["chem_drivers"])])
            if r.get("is_valid") == False:
                slot["chem_invalid"] = True

    # Microbiology
    for year in (2023, 2024, 2025):
        p = MICRO_DIR / f"data{year}.parquet"
        if not p.exists(): continue
        df = pd.read_parquet(p)
        df = df[df["sample_id"].notna()].copy()
        df["_sid"] = df["sample_id"].astype(str).str.lower()
        for _, r in df.iterrows():
            key = (year, r["_sid"])
            slot = by_sample.setdefault(key, {
                "chem_score": 0.0, "chem_drivers": [],
                "micro_score": 0.0, "micro_drivers": [],
                "chem_invalid": False, "micro_invalid": False,
            })
            s, d = micro_risk_for_row(r)
            if s > slot["micro_score"]:
                slot["micro_score"] = s
                slot["micro_drivers"] = [f"[micro] {x}" for x in d]
            iv = r.get("is_valid")
            try:
                if iv is False or (pd.notna(iv) and iv == False):
                    slot["micro_invalid"] = True
            except Exception:
                pass

    # Composite
    for key, s in by_sample.items():
        composite = max(s["chem_score"], s["micro_score"])
        if s["chem_invalid"] and s["micro_invalid"]:
            composite = min(100.0, composite + 5.0)
        s["composite"] = round(composite, 1)
        s["tier"] = to_tier(composite)
        # Top 3 drivers — chemistry first, then microbio
        s["drivers"] = (s["chem_drivers"][:2] + s["micro_drivers"][:2])[:3]
    return by_sample


if __name__ == "__main__":
    risks = compute_per_sample_risk()
    print(f"Computed risk for {len(risks):,} unique samples.")
    tiers = {}
    for s in risks.values():
        tiers[s["tier"]] = tiers.get(s["tier"], 0) + 1
    print("\nTier distribution:")
    for t in ("None", "Low", "Medium", "High", "Critical"):
        print(f"  {t:<10}  {tiers.get(t, 0):>6,}")

    # Top 10 highest-risk samples
    ordered = sorted(risks.items(), key=lambda kv: -kv[1]["composite"])
    print("\nTop 10 highest-risk samples:")
    for (year, sid), s in ordered[:10]:
        print(f"  {year}  {sid:<25}  score={s['composite']:>5}  tier={s['tier']:<8}  "
              f"drivers={' | '.join(s['drivers'])}")
