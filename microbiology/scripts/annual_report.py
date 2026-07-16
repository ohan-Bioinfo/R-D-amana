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
    out: dict = {"year": year, "source": "Annual Report"}
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


def compute_annual_from_data(base_dir, year: int) -> dict | None:
    """Compute a per-year figures block from our cleaned parquets (NOT the
    official report). Used for years that have no Annual Report file. Clearly
    marked source='our cleaned data' so it is never mistaken for official."""
    base = Path(base_dir)
    wide_p = base / "cleaned" / f"data{year}.parquet"
    if not wide_p.exists():
        return None
    df = pd.read_parquet(wide_p)
    out: dict = {"year": year, "source": "our cleaned data"}
    total = len(df)
    nc = int((df["is_failure"] == True).sum()) if "is_failure" in df.columns else 0  # noqa: E712
    out["total_samples"] = total
    out["compliant"] = total - nc
    out["compliance_rate"] = round(100 * (total - nc) / total, 2) if total else 0.0

    long_p = base / "cleaned" / f"data{year}_long.parquet"
    if long_p.exists():
        lg = pd.read_parquet(long_p)
        tcol = "test_canonical" if "test_canonical" in lg.columns else "test"
        out["total_tests"] = len(lg)
        out["non_compliant_tests"] = int((lg["validity"] == False).sum())  # noqa: E712
        per = []
        for name, grp in lg.groupby(tcol):
            tot = len(grp)
            inv = int((grp["validity"] == False).sum())  # noqa: E712
            per.append({"name_en": str(name), "name_ar": str(name),
                        "total": tot, "invalid": inv,
                        "rate": round(100 * inv / tot, 1) if tot else 0.0})
        per.sort(key=lambda t: -t["rate"])
        out["per_test"] = per

    # 2024 has no geography → empty sector list (rendered as a note).
    if "sector" in df.columns and df["sector"].notna().any():
        vc = df["sector"].dropna().value_counts()
        tot_s = int(vc.sum()) or 1
        out["sectors"] = [{"name_ar": str(k), "samples": int(v), "pct": round(100 * v / tot_s, 1)}
                          for k, v in vc.items()]
    else:
        out["sectors"] = []
    return out


def load_all_annual_figures(base_dir) -> dict:
    """Per-year figures {year: block}. A year uses its Annual Report if the file
    exists; otherwise it is computed from our cleaned parquet (marked as such)."""
    import re as _re
    base = Path(base_dir)
    figs: dict = {}
    p25 = base / "2025-original" / "Annual Report 2025.xlsx"
    if p25.exists():
        figs[2025] = load_annual_report(p25, 2025)
    p24 = base / "2024-original" / "Annual Report 2024.xlsx"
    if p24.exists():
        figs[2024] = load_annual_report(p24, 2024)
    # Fill any remaining cleaned year from our data.
    for pq in sorted((base / "cleaned").glob("data*.parquet")):
        m = _re.match(r"^data(\d{4})\.parquet$", pq.name)
        if not m:
            continue
        y = int(m.group(1))
        if y not in figs:
            blk = compute_annual_from_data(base, y)
            if blk:
                figs[y] = blk
    return figs
