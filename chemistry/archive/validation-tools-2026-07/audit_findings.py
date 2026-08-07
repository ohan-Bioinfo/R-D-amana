"""Comprehensive audit across the 7 v2 chemistry parquets.

Four analytical dimensions:
  1. Worst-offender ranking — biggest exceedances by ratio (value / limit)
  2. Facility-level repeat-offenders
  3. Sample-category pass/fail breakdown
  4. Monthly time trend

Writes a Markdown report at reports/AUDIT_FINDINGS_2025.md.
"""
from __future__ import annotations
import pandas as pd
from pathlib import Path
import sys

CLEAN = Path(__file__).resolve().parent.parent / "cleaned"
OUT   = Path(__file__).resolve().parent.parent / "reports" / "AUDIT_FINDINGS.md"
SECTIONS = ["aflatoxins", "food_chemistry", "heavy_metals", "honey",
            "hormones_antibiotics", "pesticides", "water_analysis"]


def load_all() -> dict[str, pd.DataFrame]:
    """Concatenate every year's parquet per section into one frame."""
    import re as _re
    out = {}
    for sec in SECTIONS:
        frames = []
        for p in sorted(CLEAN.glob(f"chem_{sec}_*.parquet")):
            m = _re.search(r"_(\d{4})\.parquet$", p.name)
            if not m:
                continue
            year = int(m.group(1))
            df = pd.read_parquet(p)
            if "year" not in df.columns:
                df = df.assign(year=year)
            frames.append(df)
        if frames:
            out[sec] = pd.concat(frames, ignore_index=True, sort=False)
    return out


def severity_table(df: pd.DataFrame, value_col: str, limit_col: str, direction="max", top=10) -> pd.DataFrame:
    """Return top N rows sorted by exceedance ratio."""
    mask = df[value_col].notna() & df[limit_col].notna()
    sub = df.loc[mask].copy()
    sub["_val"] = sub[value_col].astype(float)
    sub["_lim"] = sub[limit_col].astype(float)
    if direction == "max":
        sub["ratio"] = sub["_val"] / sub["_lim"].replace(0, pd.NA)
        sub = sub[sub["_val"] > sub["_lim"]]
    else:  # min — fail when value < limit
        sub["ratio"] = sub["_lim"] / sub["_val"].replace(0, pd.NA)
        sub = sub[sub["_val"] < sub["_lim"]]
    return sub.sort_values("ratio", ascending=False).head(top)


def fmt_row(r, fields):
    return " | ".join(str(r.get(f, "—"))[:30] for f in fields)


def main():
    dfs = load_all()
    total_rows = sum(len(df) for df in dfs.values())
    years = sorted({int(y) for df in dfs.values() for y in df["year"].dropna().unique()})
    by_year = {y: sum(int((df["year"]==y).sum()) for df in dfs.values()) for y in years}
    lines: list[str] = ["# Riyadh Chemistry Lab — Audit Findings (2024 + 2025)\n"]
    lines.append(f"Generated from `cleaned/chem_*_*.parquet` ({total_rows:,} total rows "
                 f"across {len(dfs)} sections, years: " +
                 ", ".join(f"{y} ({by_year[y]:,})" for y in years) + ").\n")

    # ────────────────────────────────────────────────────────────────────────
    # 1. WORST-OFFENDER RANKING (severity = value / limit ratio)
    # ────────────────────────────────────────────────────────────────────────
    lines.append("## 1. Worst-offender ranking (by exceedance ratio)\n")

    # 1a. Heavy metals — find worst for each metal
    df = dfs["heavy_metals"]
    metals = ["lead", "arsenic", "cadmium", "mercury", "selenium", "copper",
              "iron", "manganese", "nickel", "zinc", "barium", "beryllium"]
    lines.append("### Heavy metals — top exceedance per metal\n")
    lines.append("| Metal | Sample ID | Sample name | Value | Limit | Ratio | Facility |")
    lines.append("|---|---|---|---:|---:|---:|---|")
    for m in metals:
        vcol, lcol = f"{m}_value", f"{m}_limit_value"
        if vcol not in df.columns or lcol not in df.columns: continue
        top = severity_table(df, vcol, lcol, top=3)
        for _, r in top.iterrows():
            lines.append(f"| {m} | {r.get('sample_id','—')} | {str(r.get('sample_name','—'))[:25]} | "
                         f"{r['_val']:.1f} | {r['_lim']:.1f} | **{r['ratio']:.1f}×** | "
                         f"{str(r.get('facility_name','—'))[:25]} |")
    lines.append("")

    # 1b. Honey — Glucose+Fructose (MIN direction), HMF, Sucrose
    df = dfs["honey"]
    lines.append("### Honey — sugar / HMF failures\n")
    lines.append("| Test | Sample name | Value | Limit | Direction | Ratio | Facility |")
    lines.append("|---|---|---:|---:|---|---:|---|")
    for test, vcol, lcol, direction in [
        ("Glucose+Fructose", "glucose_plus_fructose_value", "glucose_plus_fructose_limit_value", "min"),
        ("Sucrose",          "sucrose_value",                "sucrose_limit_value",                "max"),
        ("HMF",              "hmf_value",                    "hmf_limit_value",                    "max"),
        ("Moisture",         "moisture_value",               "moisture_limit_value",               "max"),
    ]:
        if vcol not in df.columns: continue
        top = severity_table(df, vcol, lcol, direction=direction, top=5)
        for _, r in top.iterrows():
            lines.append(f"| {test} | {str(r.get('sample_name','—'))[:25]} | "
                         f"{r['_val']:.2f} | {r['_lim']:.2f} | {direction} | "
                         f"**{r['ratio']:.2f}×** | {str(r.get('facility_name','—'))[:25]} |")
    lines.append("")

    # 1c. Aflatoxins — Total + B1
    df = dfs["aflatoxins"]
    lines.append("### Aflatoxins — Total + B1 exceedances\n")
    lines.append("| Sample ID | Sample name | Total ppb | Limit | B1 ppb | Facility |")
    lines.append("|---|---|---:|---:|---:|---|")
    fails = df[df["n_failed_tests_derived"].astype(float) > 0].copy()
    fails["_t"] = fails["total_ppb_value"].astype(float)
    fails["_l"] = fails["limit_ppb_value"].astype(float)
    fails = fails.sort_values("_t", ascending=False)
    for _, r in fails.iterrows():
        lines.append(f"| {r['sample_id']} | {str(r.get('sample_name','—'))[:25]} | "
                     f"{r['_t']:.2f} | {r['_l']:.1f} | {r.get('b1_ppb_value',0):.2f} | "
                     f"{str(r.get('facility_name','—'))[:25]} |")
    lines.append("")

    # 1d. Pesticides — highest concentration / limit ratios
    df = dfs["pesticides"]
    lines.append("### Pesticides — top concentration / limit ratios\n")
    lines.append("| Pesticide | Sample | Sample name | Conc (ppm) | Limit | Ratio | Facility |")
    lines.append("|---|---|---|---:|---:|---:|---|")
    mask = df["concentration_ppm"].notna() & df["limit_ppm"].notna()
    sub = df.loc[mask].copy()
    sub["_c"] = sub["concentration_ppm"].astype(float)
    sub["_l"] = sub["limit_ppm"].astype(float)
    sub["ratio"] = sub["_c"] / sub["_l"].replace(0, pd.NA)
    sub = sub[sub["_c"] > sub["_l"]].sort_values("ratio", ascending=False).head(15)
    for _, r in sub.iterrows():
        lines.append(f"| {r.get('pesticide_name','—')} | {r.get('sample_id','—')} | "
                     f"{str(r.get('sample_name','—'))[:25]} | {r['_c']:.3f} | "
                     f"{r['_l']:.2f} | **{r['ratio']:.1f}×** | "
                     f"{str(r.get('facility_name','—'))[:25]} |")
    lines.append("")

    # 1e. Food chemistry — pH
    df = dfs["food_chemistry"]
    lines.append("### Food chemistry — pH failures (sorted)\n")
    lines.append("| Sample ID | Sample name | pH | Limit | Facility |")
    lines.append("|---|---|---:|---:|---|")
    mask = df["ph_value"].notna() & df["ph_limit_value"].notna()
    sub = df.loc[mask].copy()
    sub["_p"] = sub["ph_value"].astype(float)
    sub["_l"] = sub["ph_limit_value"].astype(float)
    sub = sub[sub["_p"] > sub["_l"]].sort_values("_p", ascending=False).head(15)
    for _, r in sub.iterrows():
        lines.append(f"| {r['sample_id']} | {str(r.get('sample_name','—'))[:25]} | "
                     f"{r['_p']:.2f} | {r['_l']:.2f} | {str(r.get('facility_name','—'))[:25]} |")
    lines.append("")

    # ────────────────────────────────────────────────────────────────────────
    # 2. FACILITY-LEVEL REPEAT OFFENDERS
    # ────────────────────────────────────────────────────────────────────────
    lines.append("## 2. Facility-level repeat offenders\n")
    facility_stats = []
    for sec, df in dfs.items():
        if "facility_name" not in df.columns or "is_valid" not in df.columns:
            continue
        sub = df[df["facility_name"].notna()].copy()
        g = sub.groupby("facility_name").agg(
            total=("is_valid", "size"),
            invalid=("is_valid", lambda s: (s == False).sum()),
        )
        g["section"] = sec
        g = g.reset_index()
        facility_stats.append(g)
    fdf = pd.concat(facility_stats, ignore_index=True)
    agg = fdf.groupby("facility_name", as_index=False).agg(
        total=("total", "sum"), invalid=("invalid", "sum"),
        sections=("section", lambda s: ", ".join(sorted(set(s)))),
    )
    agg["fail_rate_pct"] = (agg["invalid"] * 100 / agg["total"]).round(1)
    agg = agg[agg["invalid"] >= 2].sort_values(["invalid", "fail_rate_pct"], ascending=False).head(20)
    lines.append("Facilities with ≥ 2 invalid samples (top 20):\n")
    lines.append("| Facility | Total | Invalid | Fail % | Sections |")
    lines.append("|---|---:|---:|---:|---|")
    for _, r in agg.iterrows():
        lines.append(f"| {str(r['facility_name'])[:50]} | {r['total']} | **{r['invalid']}** | "
                     f"{r['fail_rate_pct']}% | {r['sections']} |")
    lines.append("")

    # ────────────────────────────────────────────────────────────────────────
    # 3. SAMPLE-CATEGORY BREAKDOWN
    # ────────────────────────────────────────────────────────────────────────
    lines.append("## 3. Sample-category breakdown (pass/fail rates)\n")
    for sec, df in dfs.items():
        if "sample_category" not in df.columns or "is_valid" not in df.columns: continue
        sub = df[df["sample_category"].notna()].copy()
        if sub.empty: continue
        g = sub.groupby("sample_category").agg(
            total=("is_valid", "size"),
            valid=("is_valid", lambda s: (s == True).sum()),
            invalid=("is_valid", lambda s: (s == False).sum()),
            unknown=("is_valid", lambda s: s.isna().sum()),
        )
        g["fail_pct"] = (g["invalid"] * 100 / g["total"]).round(1)
        g = g.reset_index().sort_values(["invalid", "fail_pct"], ascending=False).head(15)
        if (g["invalid"] > 0).any():
            lines.append(f"### {sec}\n")
            lines.append("| Category | Total | Valid | Invalid | Unknown | Fail % |")
            lines.append("|---|---:|---:|---:|---:|---:|")
            for _, r in g.iterrows():
                lines.append(f"| {str(r['sample_category'])[:40]} | {r['total']} | "
                             f"{r['valid']} | **{r['invalid']}** | {r['unknown']} | "
                             f"{r['fail_pct']}% |")
            lines.append("")

    # ────────────────────────────────────────────────────────────────────────
    # 4. MONTHLY TIME TREND
    # ────────────────────────────────────────────────────────────────────────
    lines.append("## 4. Monthly time trend\n")
    for sec, df in dfs.items():
        if "sheet_year_month" not in df.columns: continue
        sub = df[df["sheet_year_month"].notna()].copy()
        if sub.empty: continue
        g = sub.groupby("sheet_year_month").agg(
            total=("is_valid", "size"),
            invalid=("is_valid", lambda s: (s == False).sum()),
        )
        g["fail_pct"] = (g["invalid"] * 100 / g["total"]).round(1)
        g = g.reset_index().sort_values("sheet_year_month")
        if g["total"].sum() == 0: continue
        lines.append(f"### {sec}\n")
        lines.append("| Month | Samples | Invalid | Fail % |")
        lines.append("|---|---:|---:|---:|")
        for _, r in g.iterrows():
            flag = " ⚠️" if r["fail_pct"] >= 15 else ""
            lines.append(f"| {r['sheet_year_month']} | {r['total']} | "
                         f"{r['invalid']} | {r['fail_pct']}%{flag} |")
        lines.append("")

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
