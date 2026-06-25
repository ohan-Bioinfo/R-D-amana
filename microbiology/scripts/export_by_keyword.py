"""Export one CSV per Arabic sample-name keyword under 2025/by_keyword/.

Each CSV contains all rows where sample_name CONTAINS the keyword (substring).
A row may appear in multiple keyword CSVs if its sample_name matches several.

Also writes:
  2025/by_keyword/_summary.csv  — one row per keyword with match count.

Re-runnable: reads cleaned/data2025.parquet and the keyword list below.
"""
from __future__ import annotations

from pathlib import Path
import re

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PARQUET = ROOT / "cleaned" / "data2025.parquet"
OUT_DIR = ROOT / "2025" / "by_keyword"

# Keep one entry per unique keyword.
KEYWORDS = sorted(set(filter(None, [s.strip() for s in """
بطن عجل بلدي
لحم نعيمي
كلية غنم بلدي
كلية حاشي بلدي
كلوة من نفس النعيمي
كلية نعيمي بلدي
كلية غنم روماني مستورد
كلوة لنفس العجل البلدي
كلوة غنم بلدي من نفس الخروف
كلوة بقر باكستاني
كلاوي عجل
كرش من نفس السواكني
كرش من نفس البربري
كتف حاشي بلدي
كبدة نفس الحاشي
لحم بطن غنم روماني مستورد
لحم عجل بلدي فخذ
لحم يد حاشي مستورد تربية سعودية
لحم مع بصل
لحم كتف عجل بلدي
لحم كتف عجل باكستاني
لحم فخذ هندي
لحم فخذ نعيمي بلدي
لحم فخذ حاشي بلدي
لحم عجل هولندي من الرقبة
لحم عجل كتف
لحم عجل انقوس
كبدة من نفس النعيمي
لحم عجل
لحم ضهر عجل
لحم رقبة نعيمي بلدي
لحم حاشي كتف بلدي
لحم حاشي بلدي رجل
لحم حاشي بلدي
لحم جنب نعيمي بلدي
لحم جنب سواكني بلدي
لحم بطن نعيمي بلدي من خروف اخر
لحم بطن نعيمي بلدي
كبدة غنم بلدي خاروف اخر
كبدة من نفس الحاشي
فخذ لحم عجل بلدي
فخذ عجل بلدي
ضهر عجل بلدي
قطع دجاج عادي ني
دجاج ني
دجاج متبل
قطع دجاج حراق ني
قطعة ظهروفخذ عجل كشميري
كبدة لنفس العجل البلدي
قلب من نفس سواكني بلدي
كبدة لحم نعيمي بلدي
كبدة غنم بلدي
كبدة عجل بلدي
كبدة عجل
كبدة حاشي من حاشي اخر
كبدة جل بتلو بلدي
كبابا لحم ني
كبابا دجاج ني
قلب من نفس النعيمي
قلب بقر باكستاني
قلب من نفس السواكني
قلب لنفس العجل البلدي
قلب غنم بلدي من نفس الخروف
قلب غنم بلدي
قلب عجل بتلو بلدي
قلب عجل
قلب حاشي من حاشي اخر
قلب حاشي بلدي
مصارين خاروف اخر
مكعب وافي
فيدكو
شعير حب
ذرة
رودس
برسيم
موية حوض
مياه
شعير
يرسيم
تبن
مكعب حملان بلس
مكعب فكتو
""".splitlines()])))


SAFE_FILENAME_RE = re.compile(r"[^\w؀-ۿ -]")


def safe_filename(keyword: str) -> str:
    """Use the keyword verbatim, only stripping characters unsafe across filesystems."""
    return SAFE_FILENAME_RE.sub("_", keyword).strip()


def serialize_lists(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in ["invalid_tests", "failed_pathogens", "failed_indicators"]:
        if col in out.columns:
            out[col] = out[col].apply(
                lambda lst: " | ".join(lst) if lst is not None and len(lst) > 0 else ""
            )
    return out


def main() -> None:
    df = pd.read_parquet(PARQUET)
    df = df.sort_values(by=["sampling_date", "sample_id"], na_position="last")
    df = serialize_lists(df)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    summary_rows = []
    sample_names = df["sample_name"].fillna("")
    for kw in KEYWORDS:
        mask = sample_names.str.contains(kw, regex=False)
        n = int(mask.sum())
        if n == 0:
            summary_rows.append({"keyword": kw, "matches": 0, "csv_filename": ""})
            continue
        sub = df[mask]
        # Also include the non-compliance count so the summary is decision-useful
        n_nc = int((sub["is_failure"] == True).sum())
        fname = f"{safe_filename(kw)}.csv"
        path = OUT_DIR / fname
        sub.to_csv(path, index=False, encoding="utf-8-sig")
        summary_rows.append({
            "keyword": kw,
            "matches": n,
            "non_compliant": n_nc,
            "non_compliance_rate_%": round(100 * n_nc / n, 1),
            "csv_filename": fname,
        })
        print(f"  {n:4d} matches ({n_nc} non-compliant) → {fname}")

    summary = pd.DataFrame(summary_rows)
    summary = summary.sort_values(by=["matches"], ascending=False)
    summary_path = OUT_DIR / "_summary.csv"
    summary.to_csv(summary_path, index=False, encoding="utf-8-sig")
    print(f"\nwrote {summary_path.relative_to(ROOT)}  ({len(summary)} keywords)")
    print(f"wrote {len([r for r in summary_rows if r['matches'] > 0])} per-keyword CSVs in {OUT_DIR.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
