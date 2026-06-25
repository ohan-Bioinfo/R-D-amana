"""Generate a professional lab-dashboard HTML from a cleaned parquet file.

Single self-contained HTML output — no external CSS/JS dependencies.
Designed as a prototype that can later be expanded to a multi-file dashboard.

Usage: python build_dashboard.py <input.parquet> <output.html>
"""
from __future__ import annotations

import html
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

import pandas as pd


# ---------------------------------------------------------------------------
# Palette + small helpers
# ---------------------------------------------------------------------------
PALETTE = {
    "bg": "#f6f8fa",
    "card": "#ffffff",
    "border": "#e1e4e8",
    "border_strong": "#d0d7de",
    "fg": "#1f2328",
    "fg_muted": "#57606a",
    "accent": "#0969da",
    "accent_dark": "#0550ae",
    "success": "#1a7f37",
    "success_bg": "#dafbe1",
    "danger": "#cf222e",
    "danger_bg": "#ffebe9",
    "warning": "#9a6700",
    "warning_bg": "#fff8c5",
    "neutral": "#6e7781",
    "neutral_bg": "#eaeef2",
}

# English labels for Arabic test names (used for tooltips / dual labels)
TEST_EN = {
    "السالمونيلا": "Salmonella",
    "ايشيريشيا كولاي": "E. coli",
    "استافيلوكوكس اورياس": "Staphylococcus aureus",
    "انتيروباكتريسي": "Enterobacteriaceae",
    "العدد الكلي للبكتيريا": "Total bacterial count",
    "كوليفورم": "Coliform",
    "باصلص سيرز": "Bacillus cereus",
    "الخمائر والاعفان": "Yeasts & moulds",
    "سيدومومناس": "Pseudomonas",
}

CODE_LABEL = {
    "VALID": ("Valid", PALETTE["success"], PALETTE["success_bg"]),
    "INVALID_TOTAL_BACTERIA": ("Invalid — Total bacteria", PALETTE["danger"], PALETTE["danger_bg"]),
    "INVALID_SALMONELLA": ("Invalid — Salmonella", PALETTE["danger"], PALETTE["danger_bg"]),
    "INVALID_ENTEROBACTERIACEAE_SALMONELLA": ("Invalid — Entero. + Salm.", PALETTE["danger"], PALETTE["danger_bg"]),
    "INVALID_MULTIPLE_TBC_ENTERO_YEAST": ("Invalid — Multiple", PALETTE["danger"], PALETTE["danger_bg"]),
    "INVALID_YEAST_MOULD": ("Invalid — Yeast & mould", PALETTE["danger"], PALETTE["danger_bg"]),
    "INVALID_ENTEROBACTERIACEAE": ("Invalid — Enterobact.", PALETTE["danger"], PALETTE["danger_bg"]),
    "INVALID_E_COLI": ("Invalid — E. coli", PALETTE["danger"], PALETTE["danger_bg"]),
    "INVALID_WATER_COLIFORM": ("Invalid — Water coliform", PALETTE["danger"], PALETTE["danger_bg"]),
    "UNKNOWN": ("Unknown", PALETTE["warning"], PALETTE["warning_bg"]),
}

FLAG_LABEL = {
    "msno_value_4223_suspect_typo": "M.S.No suspected typo",
    "gso_code_was_iso_placeholder": "GSO code missing (was 'ISO')",
    "final_report_truncation": "Final-report text truncation",
    "pseudomonas_spelling_unverified": "Pseudomonas spelling unverified",
    "dilution_value_nonstandard": "Non-standard dilution value",
    "result_numeric_comparison_prefix:>": "Result has '>' prefix",
    "limit_numeric_comparison_prefix:<": "Limit has '<' prefix",
}


def esc(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    return html.escape(str(v))


# ---------------------------------------------------------------------------
# Aggregations
# ---------------------------------------------------------------------------
def per_sample(df: pd.DataFrame) -> pd.DataFrame:
    """Roll up the long-format frame to one row per sample."""
    grouped = df.groupby(["m_s_no", "s_no"], dropna=False)
    rows = []
    for (msno, sno), g in grouped:
        tests = g["test"].dropna().tolist()
        validities = g["validity"].dropna().tolist()
        all_valid = all(validities) if validities else None
        any_invalid = (False in validities) if validities else None
        codes = g["final_report_code"].dropna().unique().tolist()
        flags = set()
        for fl in g["data_quality_flags"].dropna().tolist():
            for f in str(fl).split("|"):
                if f:
                    flags.add(f)
        sample_name = next((v for v in g["sample_name"].dropna()), None)
        gso = next((v for v in g["gso_code"].dropna()), None)
        rows.append({
            "m_s_no": msno,
            "s_no": sno,
            "sample_name": sample_name,
            "gso_code": gso,
            "n_tests": len(tests),
            "n_valid": sum(1 for v in validities if v is True),
            "n_invalid": sum(1 for v in validities if v is False),
            "tests": tests,
            "all_valid": all_valid,
            "any_invalid": any_invalid,
            "final_codes": codes,
            "flags": sorted(flags),
        })
    out = pd.DataFrame(rows)
    out = out.sort_values(by=["s_no", "m_s_no"], na_position="last").reset_index(drop=True)
    return out


# ---------------------------------------------------------------------------
# SVG bar chart
# ---------------------------------------------------------------------------
def svg_bar_chart(items: list[tuple[str, int]], width: int = 520, bar_h: int = 22,
                  gap: int = 6, label_w: int = 220, color: str = "#0969da",
                  show_value: bool = True) -> str:
    if not items:
        return '<div class="empty">no data</div>'
    max_v = max(v for _, v in items) or 1
    chart_w = width - label_w - 60
    rows = []
    y = 0
    for label, value in items:
        bar_w = max(1, int(round(chart_w * value / max_v)))
        rows.append(f'''
            <g transform="translate(0,{y})">
                <text x="{label_w - 10}" y="{bar_h/2 + 4}" text-anchor="end"
                      font-size="12" fill="#1f2328">{esc(label)}</text>
                <rect x="{label_w}" y="0" width="{bar_w}" height="{bar_h}"
                      fill="{color}" rx="3"></rect>
                {f'<text x="{label_w + bar_w + 6}" y="{bar_h/2 + 4}" font-size="12" fill="#57606a">{value}</text>' if show_value else ''}
            </g>''')
        y += bar_h + gap
    h = y - gap + 4
    return f'<svg viewBox="0 0 {width} {h}" width="100%" height="{h}" preserveAspectRatio="xMinYMin meet">{"".join(rows)}</svg>'


def svg_donut(parts: list[tuple[str, int, str]], size: int = 180, thickness: int = 28) -> str:
    """parts = [(label, value, color), ...]"""
    total = sum(v for _, v, _ in parts) or 1
    cx = cy = size / 2
    r = (size - thickness) / 2
    import math
    out = [f'<svg viewBox="0 0 {size} {size}" width="{size}" height="{size}">']
    out.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#eaeef2" stroke-width="{thickness}"/>')
    angle_start = -math.pi / 2
    for _, v, c in parts:
        if v <= 0:
            continue
        frac = v / total
        angle_end = angle_start + frac * 2 * math.pi
        x1 = cx + r * math.cos(angle_start)
        y1 = cy + r * math.sin(angle_start)
        x2 = cx + r * math.cos(angle_end)
        y2 = cy + r * math.sin(angle_end)
        large = 1 if frac > 0.5 else 0
        d = f"M {x1:.2f} {y1:.2f} A {r:.2f} {r:.2f} 0 {large} 1 {x2:.2f} {y2:.2f}"
        out.append(f'<path d="{d}" fill="none" stroke="{c}" stroke-width="{thickness}" stroke-linecap="butt"/>')
        angle_start = angle_end
    out.append(f'<text x="{cx}" y="{cy - 4}" text-anchor="middle" font-size="22" font-weight="700" fill="#1f2328">{total}</text>')
    out.append(f'<text x="{cx}" y="{cy + 18}" text-anchor="middle" font-size="11" fill="#57606a">tests</text>')
    out.append('</svg>')
    return "".join(out)


# ---------------------------------------------------------------------------
# Page rendering
# ---------------------------------------------------------------------------
def render_dashboard(parquet_path: Path, out_path: Path) -> None:
    df = pd.read_parquet(parquet_path)

    sheet_date = df["sheet_date"].iloc[0]
    if isinstance(sheet_date, date):
        date_str = sheet_date.isoformat()
        date_long = sheet_date.strftime("%A, %d %B %Y")
    else:
        date_str = str(sheet_date)
        date_long = str(sheet_date)
    source_file = df["source_file"].iloc[0]

    samples = per_sample(df)
    n_samples = len(samples)
    n_tests = len(df)
    n_valid_tests = int((df["validity"] == True).sum())
    n_invalid_tests = int((df["validity"] == False).sum())
    n_samples_with_failure = int(samples["any_invalid"].fillna(False).sum())
    n_samples_clean = int(samples["all_valid"].fillna(False).sum())
    pass_rate = (n_valid_tests / n_tests * 100) if n_tests else 0.0
    flag_rows = int(df["data_quality_flags"].notna().sum())

    test_counts = Counter(df["test"].dropna().tolist())
    test_invalid_counts: dict = defaultdict(int)
    for t, v in zip(df["test"].dropna(), df.loc[df["test"].notna(), "validity"]):
        if v is False:
            test_invalid_counts[t] += 1

    code_counts = Counter(df["final_report_code"].dropna().tolist())

    flag_counts: Counter = Counter()
    for fl in df["data_quality_flags"].dropna().tolist():
        for f in str(fl).split("|"):
            if f:
                flag_counts[f] += 1

    # --- Build HTML ---
    P = PALETTE
    style = f"""
    :root {{
        --bg: {P['bg']};
        --card: {P['card']};
        --border: {P['border']};
        --border-strong: {P['border_strong']};
        --fg: {P['fg']};
        --fg-muted: {P['fg_muted']};
        --accent: {P['accent']};
        --success: {P['success']};
        --success-bg: {P['success_bg']};
        --danger: {P['danger']};
        --danger-bg: {P['danger_bg']};
        --warning: {P['warning']};
        --warning-bg: {P['warning_bg']};
        --neutral: {P['neutral']};
        --neutral-bg: {P['neutral_bg']};
    }}
    * {{ box-sizing: border-box; }}
    html, body {{ margin: 0; padding: 0; background: var(--bg); color: var(--fg);
                  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
                  font-size: 14px; line-height: 1.5; }}
    a {{ color: var(--accent); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}

    /* Header */
    header.topbar {{ background: white; border-bottom: 1px solid var(--border);
                     padding: 16px 32px; display: flex; align-items: center; gap: 24px; }}
    header.topbar .brand {{ display: flex; align-items: center; gap: 12px; }}
    header.topbar .brand .logo {{ width: 36px; height: 36px; border-radius: 8px;
                                   background: linear-gradient(135deg, var(--accent), {P['accent_dark']});
                                   display: grid; place-items: center; color: white; font-weight: 700; }}
    header.topbar .brand h1 {{ font-size: 16px; margin: 0; font-weight: 600; }}
    header.topbar .brand .sub {{ font-size: 12px; color: var(--fg-muted); }}
    header.topbar .meta {{ margin-left: auto; text-align: right; font-size: 12px; color: var(--fg-muted); }}
    header.topbar .meta b {{ color: var(--fg); }}

    main {{ padding: 24px 32px 64px; max-width: 1400px; margin: 0 auto; }}

    h2.section {{ font-size: 13px; text-transform: uppercase; letter-spacing: 0.06em;
                  color: var(--fg-muted); margin: 32px 0 12px; font-weight: 600; }}
    h2.section:first-of-type {{ margin-top: 8px; }}

    /* KPI cards */
    .kpis {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 16px; }}
    .kpi {{ background: var(--card); border: 1px solid var(--border); border-radius: 10px;
            padding: 16px 18px; }}
    .kpi .label {{ font-size: 12px; color: var(--fg-muted); text-transform: uppercase;
                   letter-spacing: 0.04em; }}
    .kpi .value {{ font-size: 28px; font-weight: 700; margin-top: 4px; }}
    .kpi .delta {{ font-size: 12px; color: var(--fg-muted); margin-top: 2px; }}
    .kpi.success .value {{ color: var(--success); }}
    .kpi.danger .value {{ color: var(--danger); }}
    .kpi.warning .value {{ color: var(--warning); }}

    /* Two-up grid */
    .two-up {{ display: grid; grid-template-columns: 2fr 1fr; gap: 20px; align-items: stretch; }}
    .panel {{ background: var(--card); border: 1px solid var(--border); border-radius: 10px;
              padding: 20px; }}
    .panel > .panel-title {{ font-size: 14px; font-weight: 600; margin: 0 0 4px; }}
    .panel > .panel-sub {{ font-size: 12px; color: var(--fg-muted); margin-bottom: 14px; }}
    .panel.compact {{ padding: 16px; }}

    /* Tables */
    table.data {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    table.data th {{ text-align: left; padding: 8px 10px; background: var(--bg);
                     border-bottom: 1px solid var(--border); font-weight: 600;
                     color: var(--fg-muted); font-size: 12px; text-transform: uppercase;
                     letter-spacing: 0.03em; }}
    table.data td {{ padding: 10px; border-bottom: 1px solid var(--border); vertical-align: middle; }}
    table.data tr:hover td {{ background: var(--bg); }}
    td.ar {{ direction: rtl; text-align: right; font-size: 14px; }}
    td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}

    /* Badges */
    .badge {{ display: inline-block; padding: 2px 9px; border-radius: 999px;
              font-size: 11px; font-weight: 600; }}
    .badge.success {{ background: var(--success-bg); color: var(--success); }}
    .badge.danger  {{ background: var(--danger-bg); color: var(--danger); }}
    .badge.warning {{ background: var(--warning-bg); color: var(--warning); }}
    .badge.neutral {{ background: var(--neutral-bg); color: var(--neutral); }}
    .pill-row {{ display: inline-flex; gap: 4px; flex-wrap: wrap; }}
    .pill {{ display: inline-block; padding: 1px 7px; border-radius: 4px; font-size: 11px;
             background: var(--neutral-bg); color: var(--fg-muted); border: 1px solid var(--border); }}

    /* Status dot */
    .dot {{ display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px;
            vertical-align: middle; }}
    .dot.success {{ background: var(--success); }}
    .dot.danger  {{ background: var(--danger); }}
    .dot.neutral {{ background: var(--neutral); }}

    /* Test stats per-test bar */
    .test-row {{ display: grid; grid-template-columns: 200px 1fr 56px; align-items: center;
                 gap: 10px; padding: 6px 0; border-bottom: 1px dashed var(--border); font-size: 13px; }}
    .test-row:last-child {{ border-bottom: 0; }}
    .test-row .name {{ font-size: 13px; }}
    .test-row .name small {{ display: block; color: var(--fg-muted); font-size: 11px; }}
    .test-row .bar-wrap {{ position: relative; height: 14px; background: var(--bg);
                           border-radius: 4px; overflow: hidden; }}
    .test-row .bar {{ height: 100%; background: var(--accent); border-radius: 4px; }}
    .test-row .bar.fail {{ background: var(--danger); position: absolute; top: 0; left: 0; }}
    .test-row .count {{ font-variant-numeric: tabular-nums; font-size: 12px; color: var(--fg-muted);
                        text-align: right; }}

    /* Donut legend */
    .legend {{ display: flex; flex-direction: column; gap: 6px; font-size: 12px; }}
    .legend-row {{ display: grid; grid-template-columns: 12px 1fr auto; gap: 8px; align-items: center; }}
    .legend-row .swatch {{ width: 10px; height: 10px; border-radius: 2px; }}

    /* Detail rows under sample */
    details.sample {{ border-bottom: 1px solid var(--border); }}
    details.sample > summary {{ cursor: pointer; padding: 10px 0; list-style: none;
                                display: grid; grid-template-columns: 60px 60px 80px 1fr 90px 110px 120px auto;
                                gap: 12px; align-items: center; font-size: 13px; }}
    details.sample > summary::-webkit-details-marker {{ display: none; }}
    details.sample > summary:hover {{ background: var(--bg); }}
    details.sample > summary .chev {{ color: var(--fg-muted); transition: transform 0.15s; }}
    details.sample[open] > summary .chev {{ transform: rotate(90deg); }}
    details.sample > .detail {{ padding: 0 0 12px 60px; }}
    details.sample > .detail table.data {{ background: var(--bg); border-radius: 6px; overflow: hidden; }}

    /* Footer */
    footer.bottom {{ margin-top: 48px; padding-top: 24px; border-top: 1px solid var(--border);
                     font-size: 11px; color: var(--fg-muted); display: flex; justify-content: space-between; }}
    """

    # --- Top KPIs ---
    kpis_html = f"""
    <div class="kpis">
      <div class="kpi"><div class="label">Samples tested</div><div class="value">{n_samples}</div><div class="delta">on {date_long}</div></div>
      <div class="kpi"><div class="label">Tests performed</div><div class="value">{n_tests}</div><div class="delta">{n_tests / max(n_samples,1):.1f} tests / sample</div></div>
      <div class="kpi success"><div class="label">Pass rate</div><div class="value">{pass_rate:.1f}%</div><div class="delta">{n_valid_tests} valid · {n_invalid_tests} invalid</div></div>
      <div class="kpi danger"><div class="label">Samples failed</div><div class="value">{n_samples_with_failure}</div><div class="delta">{n_samples_clean} fully clean</div></div>
      <div class="kpi warning"><div class="label">Rows flagged</div><div class="value">{flag_rows}</div><div class="delta">{len(flag_counts)} distinct issue types</div></div>
    </div>
    """

    # --- Test breakdown ---
    test_rows_html = []
    sorted_tests = sorted(test_counts.items(), key=lambda kv: -kv[1])
    max_total = max((v for _, v in sorted_tests), default=1)
    for t, total in sorted_tests:
        invalid = test_invalid_counts.get(t, 0)
        en = TEST_EN.get(t, "")
        bar_pct = total / max_total * 100
        fail_pct = invalid / max_total * 100
        test_rows_html.append(f"""
        <div class="test-row">
          <div class="name" dir="auto">
            <span dir="rtl">{esc(t)}</span>
            <small>{esc(en)}</small>
          </div>
          <div class="bar-wrap">
            <div class="bar" style="width: {bar_pct:.2f}%;"></div>
            <div class="bar fail" style="width: {fail_pct:.2f}%;"></div>
          </div>
          <div class="count">{total}{(' · ' + str(invalid) + ' fail') if invalid else ''}</div>
        </div>""")

    # --- Donut: validity rollup ---
    donut_parts = [
        ("Valid",   n_valid_tests,   P["success"]),
        ("Invalid", n_invalid_tests, P["danger"]),
    ]
    donut_html = svg_donut(donut_parts, size=200, thickness=32)
    donut_legend = f"""
    <div class="legend">
      <div class="legend-row"><span class="swatch" style="background:{P['success']}"></span><span>Valid tests</span><b>{n_valid_tests}</b></div>
      <div class="legend-row"><span class="swatch" style="background:{P['danger']}"></span><span>Invalid tests</span><b>{n_invalid_tests}</b></div>
    </div>
    """

    # --- Sample roll-up table ---
    sample_rows_html = []
    for _, r in samples.iterrows():
        if r["all_valid"] is True:
            badge = '<span class="badge success">Pass</span>'
        elif r["any_invalid"] is True:
            badge = '<span class="badge danger">Fail</span>'
        else:
            badge = '<span class="badge neutral">—</span>'
        codes = " ".join(
            f'<span class="badge" style="background:{CODE_LABEL.get(c, ("?","#000",P["neutral_bg"]))[2]}; color:{CODE_LABEL.get(c, ("?","#000",P["neutral"]))[1]}">{esc(CODE_LABEL.get(c, (c,"",""))[0])}</span>'
            for c in r["final_codes"]
        )
        flags_html = ""
        if r["flags"]:
            flags_html = ' '.join(f'<span class="pill" title="{esc(f)}">{esc(FLAG_LABEL.get(f, f))}</span>' for f in r["flags"])

        # Detail table (one row per test for this sample)
        sub = df[(df["m_s_no"] == r["m_s_no"]) & (df["s_no"] == r["s_no"])].copy()
        detail_rows = []
        for _, t in sub.iterrows():
            v_badge = ('<span class="badge success">Valid</span>' if t["validity"] is True
                       else ('<span class="badge danger">Invalid</span>' if t["validity"] is False else '<span class="badge neutral">—</span>'))
            test_en = TEST_EN.get(t["test"], "")
            detail_rows.append(f"""
              <tr>
                <td class="ar"><span dir="rtl">{esc(t['test'])}</span><br><small style="color:var(--fg-muted)">{esc(test_en)}</small></td>
                <td class="ar" dir="rtl">{esc(t['limit_raw'])}</td>
                <td class="ar" dir="rtl">{esc(t['result_raw'])}</td>
                <td>{v_badge}</td>
                <td class="ar"><span dir="rtl" title="{esc(t['final_report_raw'])[:160]}">{esc(CODE_LABEL.get(t['final_report_code'], (t['final_report_code'] or '',))[0])}</span></td>
                <td>{esc(t['data_quality_flags']) if pd.notna(t['data_quality_flags']) else ''}</td>
              </tr>""")

        sample_rows_html.append(f"""
        <details class="sample">
          <summary>
            <span class="chev">▸</span>
            <span class="num">{esc(r['s_no'])}</span>
            <span class="num">{esc(r['m_s_no'])}</span>
            <span dir="auto">{esc(r['gso_code']) or '<span class="badge warning">missing</span>'}</span>
            <span dir="rtl">{esc(r['sample_name'])}</span>
            <span class="num">{esc(r['n_tests'])}</span>
            {badge}
            <span>{codes or '<span class="badge neutral">no code</span>'}</span>
            <span>{flags_html}</span>
          </summary>
          <div class="detail">
            <table class="data">
              <thead><tr>
                <th>Test</th><th>GSO 1016 limit</th><th>Result</th><th>Validity</th>
                <th>Final report</th><th>Flags</th>
              </tr></thead>
              <tbody>{''.join(detail_rows)}</tbody>
            </table>
          </div>
        </details>
        """)

    # --- Failure breakdown ---
    failure_codes = sorted(((c, n) for c, n in code_counts.items() if c != "VALID"),
                           key=lambda kv: -kv[1])
    failure_chart = svg_bar_chart(
        [(CODE_LABEL.get(c, (c,))[0], n) for c, n in failure_codes],
        width=620, label_w=220, color=P["danger"], bar_h=22, gap=8,
    )

    # --- Data quality flags panel ---
    flag_rows_html = []
    for f, n in flag_counts.most_common():
        flag_rows_html.append(f"""
        <div class="legend-row" style="grid-template-columns:1fr auto;">
          <span><span class="dot warning" style="background:var(--warning)"></span>{esc(FLAG_LABEL.get(f, f))}</span>
          <b>{n}</b>
        </div>""")

    # --- Compose page ---
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lab report — {esc(source_file)}</title>
<style>{style}</style>
</head>
<body>

<header class="topbar">
  <div class="brand">
    <div class="logo">L</div>
    <div>
      <h1>Microbiology Lab — Daily report</h1>
      <div class="sub">GSO 1016 standard · sample &amp; test results</div>
    </div>
  </div>
  <div class="meta">
    <div><b>{esc(date_long)}</b></div>
    <div>Source: <code>{esc(source_file)}</code> · {n_samples} samples · {n_tests} tests</div>
  </div>
</header>

<main>

<h2 class="section">Overview</h2>
{kpis_html}

<h2 class="section">Test distribution &amp; outcome</h2>
<div class="two-up">
  <div class="panel">
    <div class="panel-title">Tests performed by category</div>
    <div class="panel-sub">Blue bar = total, red bar = invalid (overlay). Hover labels are English equivalents.</div>
    {''.join(test_rows_html)}
  </div>
  <div class="panel compact">
    <div class="panel-title">Validity rollup</div>
    <div class="panel-sub">All tests on this sheet</div>
    <div style="display:flex; align-items:center; gap:18px; margin-top:8px;">
      <div>{donut_html}</div>
      <div style="flex:1">{donut_legend}</div>
    </div>
  </div>
</div>

<h2 class="section">Failures by reason</h2>
<div class="panel">
  <div class="panel-title">Final-report code distribution (excluding "Valid")</div>
  <div class="panel-sub">Mapped from the lab's free-text final-report column. {sum(n for _, n in failure_codes)} invalid tests across {len(failure_codes)} categories.</div>
  {failure_chart}
</div>

<h2 class="section">Samples ({n_samples})</h2>
<div class="panel" style="padding: 8px 16px;">
  <div style="display:grid; grid-template-columns: 60px 60px 80px 1fr 90px 110px 120px auto; gap:12px;
              padding: 10px 0; border-bottom: 1px solid var(--border); font-size: 12px;
              text-transform: uppercase; color: var(--fg-muted); letter-spacing:0.04em; font-weight:600;">
    <span></span><span>S.No</span><span>M.S.No</span><span>GSO</span><span>Sample</span>
    <span># tests</span><span>Status</span><span>Final code</span><span>Flags</span>
  </div>
  {''.join(sample_rows_html)}
</div>

<h2 class="section">Data quality</h2>
<div class="two-up">
  <div class="panel">
    <div class="panel-title">Flags raised during cleaning</div>
    <div class="panel-sub">Each flag is a row-level note about something the cleaner couldn't decide on its own. Source-file values are preserved verbatim alongside the canonical fields.</div>
    {''.join(flag_rows_html) or '<div style="color:var(--fg-muted)">No flags raised.</div>'}
  </div>
  <div class="panel compact">
    <div class="panel-title">Sheet info</div>
    <div class="panel-sub">Trace back to the source workbook</div>
    <table class="data" style="margin-top:8px">
      <tr><td>File</td><td><code>{esc(source_file)}</code></td></tr>
      <tr><td>Sheet date</td><td>{esc(date_str)}</td></tr>
      <tr><td>Schema</td><td><code>lab_data_v1</code></td></tr>
      <tr><td>Rows out</td><td>{n_tests}</td></tr>
      <tr><td>Distinct samples</td><td>{n_samples}</td></tr>
      <tr><td>Distinct tests run</td><td>{len(test_counts)}</td></tr>
    </table>
  </div>
</div>

<footer class="bottom">
  <div>Lab dashboard prototype · single-file build · generated from <code>{esc(parquet_path.name)}</code></div>
  <div>Schema lab_data_v1 · GSO 1016</div>
</footer>

</main>
</body>
</html>
"""

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(page, encoding="utf-8")
    print(f"wrote {out_path} ({len(page)} bytes)")


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: python build_dashboard.py <input.parquet> <output.html>", file=sys.stderr)
        sys.exit(2)
    render_dashboard(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve())


if __name__ == "__main__":
    main()
