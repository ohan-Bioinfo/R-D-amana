"""Parse the official Annual Report workbook into per-year 'official figures'
for the Tier-1 band in build_dashboard_combined.py. MICRO stream only.

Degrades gracefully: a missing sheet or label simply omits that key rather than
raising, so a partially-populated report still builds.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

# Report's left-block English spelling (incl. its typos) -> Arabic display name.
TEST_EN_TO_AR = {
    "Aerobic plate count":     "العد الكلي للبكتيريا",
    "Staphylococcus aureas":   "استافيلوكوكس اورياس",
    "Yeasts & Molds":          "الخمائر والاعفان",
    "Enterobacteriaceae":      "انتيروباكتريسي",
    "E. coli":                 "ايشيريشيا كولاي",
    "Salmonella":              "السالمونيلا",
    "Coliforms":               "كوليفورم",
    "Bacillus cereus":         "باسيلس سيريس",
    "Pseudomonas aeruginosa":  "سيدوموناس",
    "Campylobacter jejuni":    "كامبيلوباكتر",
    "Clostridium perfringens": "كلوستريديوم بيرفرنجنز",
    "Clostridium botulinum":   "كلوستريديوم بوتولينوم",
    "E. coli O157":            "ايشيريشيا كولاي O157",
    "Listeria monocytogenes":  "الليستيريا",
    "Vibrio parahaemolyticus": "فيبريو",
}


def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(f) else f


def load_annual_report(path, year: int) -> dict:
    """Parse one Annual Report workbook into the MICRO per-year figures block."""
    xl = pd.ExcelFile(path)
    out: dict = {"year": year}
    sheets = set(xl.sheet_names)

    # --- Compliance rate: the "Total" row carries samples / valid / rate (MICRO) ---
    if "Compliance rate" in sheets:
        cr = xl.parse("Compliance rate", header=None)
        tot = cr[cr[1] == "Total"]
        if len(tot):
            r = tot.iloc[0]
            if _num(r[2]) is not None:
                out["total_samples"] = int(_num(r[2]))
            if _num(r[3]) is not None:
                out["compliant"] = int(_num(r[3]))
            rate = _num(r[4])
            if rate is not None:
                out["compliance_rate"] = round(rate * 100, 2) if rate <= 1 else round(rate, 2)

    # --- Test sheet: per-test totals (cols 1..4) with an embedded "Total" row ---
    if "Test" in sheets:
        ts = xl.parse("Test", header=None)
        per_test = []
        for i in range(len(ts)):
            name = ts.iloc[i, 1]
            if not isinstance(name, str) or not name.strip():
                continue
            name = name.strip()
            total = _num(ts.iloc[i, 2])
            nc = _num(ts.iloc[i, 4])
            if total is None:
                continue
            if name.lower() == "total":
                out["total_tests"] = int(total)
                out["non_compliant_tests"] = int(nc or 0)
                continue
            per_test.append({
                "name_en": name,
                "name_ar": TEST_EN_TO_AR.get(name, name),
                "total": int(total),
                "invalid": int(nc or 0),
                "rate": round(100 * (nc or 0) / total, 1) if total else 0.0,
            })
        per_test.sort(key=lambda t: -t["rate"])
        out["per_test"] = per_test

    # --- Municipalities: per-sector sample counts (collection basis) ---
    if "Municipalities" in sheets:
        mun = xl.parse("Municipalities", header=None)
        sectors = []
        for i in range(len(mun)):
            name = mun.iloc[i, 1]
            samples = _num(mun.iloc[i, 2])
            if not isinstance(name, str) or samples is None:
                continue
            nm = name.strip()
            if nm in ("Total", "المجموع") or "Municipality" in nm:
                continue
            if nm.startswith(("قطاع", "القطاع", "العينات")):
                sectors.append({"name_ar": nm, "samples": int(samples)})
        tot_s = sum(s["samples"] for s in sectors) or 1
        for s in sectors:
            s["pct"] = round(100 * s["samples"] / tot_s, 1)
        sectors.sort(key=lambda s: -s["samples"])
        out["sectors"] = sectors

    return out


def load_all_annual_figures(base_dir) -> dict:
    """Load every Annual Report present under base_dir into {year: figures}.

    2025 is expected; 2024 is included only if its report file has been added.
    """
    base = Path(base_dir)
    figs: dict = {}
    p25 = base / "2025-original" / "Annual Report 2025.xlsx"
    if p25.exists():
        figs[2025] = load_annual_report(p25, 2025)
    p24 = base / "2024-original" / "Annual Report 2024.xlsx"
    if p24.exists():
        figs[2024] = load_annual_report(p24, 2024)
    return figs
