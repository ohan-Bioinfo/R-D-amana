"""Build a self-contained HTML classification-review table for verification.

For every sample it replays the EXACT GSO-category derivation the dashboard uses
(per-sample_id correction → native 2024 GSO → sample_type bucket → name keyword →
Miscellaneous) and records WHICH step decided it. Rows are grouped by
(year, raw category, sample_type bucket, final GSO, source) with counts and
example sample names, so mis-classifications are easy to spot.

Run:  microbiology/.venv/bin/python microbiology/scripts/build_classification_table.py
Out:  microbiology/reports/classification_review.html
"""
from __future__ import annotations

import html as _html
from collections import defaultdict
from pathlib import Path

import pandas as pd

from build_dashboard_combined import (
    GSO_CORRECTIONS, SAMPLE_TYPE_TO_GSO, classify_sample_name,
)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "reports" / "classification_review.html"


def _val(x):
    if x is None:
        return None
    if isinstance(x, float) and pd.isna(x):
        return None
    if isinstance(x, str) and not x.strip():
        return None
    return x


def classify(row) -> tuple[str, str]:
    """Return (gso_category, source) exactly as build_data derives it."""
    sid = _val(row.get("sample_id"))
    if sid is not None:
        cat = GSO_CORRECTIONS.get(str(sid).strip().lower())
        if cat:
            return cat, "id-correction"
    native = _val(row.get("gso_category_name_en"))
    if native is not None:
        return native, "native-2024"
    st = _val(row.get("sample_type"))
    if st is not None:
        mapped = SAMPLE_TYPE_TO_GSO.get(st)
        if mapped:
            return mapped, "sample_type-bucket"
    named = classify_sample_name(_val(row.get("sample_name")))
    if named is not None:
        return named, "name-keyword"
    return "Miscellaneous Foods", "Miscellaneous-fallback"


SRC_COLOR = {
    "id-correction":          "#7c3aed",
    "native-2024":            "#0891b2",
    "sample_type-bucket":     "#059669",
    "name-keyword":           "#d97706",
    "Miscellaneous-fallback": "#dc2626",
}
# Sources that warrant a closer look (keyword guess / fell back to Misc).
SOFT = {"name-keyword", "Miscellaneous-fallback"}


def build():
    frames = []
    for y in (2024, 2025):
        p = ROOT / "cleaned" / f"data{y}.parquet"
        if p.exists():
            d = pd.read_parquet(p)
            d["__year"] = y
            frames.append(d)
    df = pd.concat(frames, ignore_index=True)

    # group key → {n, examples set, soft}
    groups: dict[tuple, dict] = defaultdict(lambda: {"n": 0, "ex": set(), "soft": False})
    src_counts: dict[str, int] = defaultdict(int)
    gso_counts: dict[str, int] = defaultdict(int)
    for r in df.to_dict("records"):
        gso, src = classify(r)
        key = (r["__year"], str(_val(r.get("category_canonical")) or "—"),
               str(_val(r.get("sample_type")) or "—"), gso, src)
        g = groups[key]
        g["n"] += 1
        nm = _val(r.get("sample_name"))
        if nm and len(g["ex"]) < 4:
            g["ex"].add(str(nm))
        src_counts[src] += 1
        gso_counts[gso] += 1

    rows = [(k[0], k[1], k[2], k[3], k[4], v["n"], sorted(v["ex"]))
            for k, v in groups.items()]
    # sort: GSO category, then descending count
    rows.sort(key=lambda t: (t[3], -t[5]))

    total = int(len(df))
    esc = _html.escape

    # ---- summary chips ----
    gso_chips = "".join(
        f'<span class="pill">{esc(k)} <b>{v:,}</b></span>'
        for k, v in sorted(gso_counts.items(), key=lambda x: -x[1]))
    src_chips = "".join(
        f'<span class="pill" style="border-color:{SRC_COLOR[k]}; color:{SRC_COLOR[k]}">'
        f'{esc(k)} <b>{v:,}</b></span>'
        for k, v in sorted(src_counts.items(), key=lambda x: -x[1]))

    # ---- table rows ----
    trs = []
    for yr, cat, st, gso, src, n, ex in rows:
        soft = " soft" if src in SOFT else ""
        exs = esc(" · ".join(ex)) if ex else "—"
        trs.append(
            f'<tr class="r{soft}" data-y="{yr}" data-src="{esc(src)}">'
            f'<td>{yr}</td>'
            f'<td class="ar">{esc(cat)}</td>'
            f'<td>{esc(st)}</td>'
            f'<td class="gso">{esc(gso)}</td>'
            f'<td><span class="src" style="background:{SRC_COLOR[src]}22; color:{SRC_COLOR[src]}; '
            f'border:1px solid {SRC_COLOR[src]}55">{esc(src)}</span></td>'
            f'<td class="num">{n:,}</td>'
            f'<td class="ar ex">{exs}</td></tr>')
    tbody = "\n".join(trs)

    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Microbiology — GSO Classification Review</title>
<style>
  :root {{ --line:#e5e7eb; --muted:#64748b; }}
  * {{ box-sizing:border-box; }}
  body {{ font-family:'Segoe UI',Tahoma,sans-serif; color:#1c2742; margin:0; background:#f8fafc; }}
  .wrap {{ max-width:1500px; margin:0 auto; padding:18px 22px 60px; }}
  h1 {{ font-size:20px; margin:6px 0; }}
  .sub {{ color:var(--muted); font-size:13px; margin-bottom:12px; }}
  .ar {{ direction:rtl; text-align:right; unicode-bidi:plaintext; }}
  .pill {{ display:inline-block; border:1px solid var(--line); border-radius:999px;
           padding:3px 10px; margin:3px 4px 3px 0; font-size:12px; background:#fff; }}
  .pill b {{ font-variant-numeric:tabular-nums; }}
  .bar {{ position:sticky; top:0; background:#f8fafc; padding:10px 0; z-index:5;
          border-bottom:1px solid var(--line); }}
  input#q {{ width:min(420px,60vw); padding:8px 12px; border:1px solid var(--line);
             border-radius:8px; font-size:14px; }}
  .toggle {{ display:inline-block; padding:6px 12px; border:1px solid var(--line);
             border-radius:8px; font-size:12px; cursor:pointer; margin-left:6px; background:#fff; }}
  .toggle.active {{ background:#1c2742; color:#fff; border-color:#1c2742; }}
  table {{ width:100%; border-collapse:collapse; font-size:13px; background:#fff;
           border:1px solid var(--line); border-radius:10px; overflow:hidden; }}
  thead th {{ position:sticky; top:56px; background:#f1f5f9; text-align:left; padding:9px 12px;
              font-size:11px; text-transform:uppercase; letter-spacing:.5px; color:var(--muted);
              cursor:pointer; white-space:nowrap; border-bottom:1px solid var(--line); }}
  tbody td {{ padding:7px 12px; border-bottom:1px solid #f1f5f9; vertical-align:top; }}
  tbody tr:hover {{ background:#f8fafc; }}
  td.num {{ text-align:right; font-variant-numeric:tabular-nums; font-weight:600; }}
  td.gso {{ font-weight:600; }}
  td.ex {{ color:var(--muted); font-size:12px; max-width:360px; }}
  .src {{ font-size:11px; padding:1px 8px; border-radius:999px; white-space:nowrap; }}
  tr.soft {{ background:#fffbeb; }}
  tr.soft:hover {{ background:#fef3c7; }}
  .count {{ color:var(--muted); font-size:12px; margin-left:8px; }}
</style></head><body><div class="wrap">
  <h1>Microbiology — GSO Classification Review</h1>
  <div class="sub">Replays the dashboard's exact derivation: per-sample correction →
     native 2024 GSO → sample_type bucket → name keyword → Miscellaneous. Amber rows =
     keyword-guess or Miscellaneous fallback (review first). {total:,} samples · 2024 + 2025.</div>
  <div><b style="font-size:12px">GSO categories:</b><br>{gso_chips}</div>
  <div style="margin-top:8px"><b style="font-size:12px">Classification source:</b><br>{src_chips}</div>
  <div class="bar" style="margin-top:12px">
    <input id="q" placeholder="Search category / bucket / GSO / example name…">
    <span class="toggle" data-f="all">All</span>
    <span class="toggle" data-f="soft">Needs review (amber)</span>
    <span class="toggle" data-f="2024">2024</span>
    <span class="toggle" data-f="2025">2025</span>
    <span class="count" id="count"></span>
  </div>
  <table id="t"><thead><tr>
    <th data-c="0">Year</th><th data-c="1">Raw category (category_canonical)</th>
    <th data-c="2">sample_type bucket</th><th data-c="3">→ GSO category</th>
    <th data-c="4">Source</th><th data-c="5">N</th><th data-c="6">Example sample names</th>
  </tr></thead><tbody>
{tbody}
  </tbody></table>
</div>
<script>
  const tb = document.querySelector('#t tbody');
  const allRows = Array.from(tb.rows);
  const q = document.getElementById('q');
  const countEl = document.getElementById('count');
  let filterMode = 'all';
  function apply() {{
    const term = q.value.trim().toLowerCase();
    let shown = 0;
    for (const r of allRows) {{
      let ok = true;
      if (filterMode === 'soft') ok = r.classList.contains('soft');
      else if (filterMode === '2024') ok = r.dataset.y === '2024';
      else if (filterMode === '2025') ok = r.dataset.y === '2025';
      if (ok && term) ok = r.textContent.toLowerCase().includes(term);
      r.style.display = ok ? '' : 'none';
      if (ok) shown++;
    }}
    countEl.textContent = shown.toLocaleString() + ' / ' + allRows.length.toLocaleString() + ' groups';
  }}
  q.addEventListener('input', apply);
  document.querySelectorAll('.toggle').forEach(t => t.addEventListener('click', () => {{
    document.querySelectorAll('.toggle').forEach(x => x.classList.remove('active'));
    t.classList.add('active'); filterMode = t.dataset.f; apply();
  }}));
  // column sort
  let sortCol = -1, asc = true;
  document.querySelectorAll('#t thead th').forEach(th => th.addEventListener('click', () => {{
    const c = +th.dataset.c; asc = (sortCol === c) ? !asc : true; sortCol = c;
    const num = (c === 0 || c === 5);
    const vis = allRows.filter(r => r.style.display !== 'none');
    vis.sort((a, b) => {{
      let x = a.cells[c].textContent.trim(), y = b.cells[c].textContent.trim();
      if (num) {{ x = parseFloat(x.replace(/,/g,''))||0; y = parseFloat(y.replace(/,/g,''))||0; return asc? x-y : y-x; }}
      return asc ? x.localeCompare(y) : y.localeCompare(x);
    }});
    vis.forEach(r => tb.appendChild(r));
  }}));
  document.querySelector('.toggle[data-f="all"]').classList.add('active');
  apply();
</script></body></html>"""
    OUT.write_text(doc, encoding="utf-8")
    print(f"wrote {OUT}  ({len(rows)} groups, {total:,} samples)")


if __name__ == "__main__":
    build()
