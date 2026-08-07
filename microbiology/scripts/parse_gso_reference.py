"""Parse Classification.html (GSO 1016 standards table) into a structured YAML
reference. Run once whenever Classification.html changes.

Output: schemas/gso_1016_reference.yaml — keyed by gso_code (e.g. A-1, A-13,
P-6/1). Used by enrich_2024 / clean_2025 to decode codes into product names,
required test panels, and limits.
"""
from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent
# Source table lives outside the pipeline; re-run only when it changes. Look for
# it in-tree first, then fall back to the legacy absolute path.
CLASS_HTML = next((p for p in (
    ROOT / "schemas" / "Classification.html",
    ROOT.parent / "Docoment-organisation" / "Classification.html",
    Path("/home/bioinfo/Documents/Data-Analysis-Muhannad/Classification.html"),
) if p.exists()), ROOT / "schemas" / "Classification.html")
OUT_YAML = ROOT / "schemas" / "gso_1016_reference.yaml"

SECTION_HEADER_RE = re.compile(r"^(\d+)\s*\.\s*(.+?)(?:\s*\(([A-Z])\))?\s*$")
GSO_CODE_RE = re.compile(r"^[A-Z]-\d+(/\d+)?$")


def _norm(s) -> str | None:
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return None
    s = str(s)
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s or None


def _split_en_ar(s: str | None) -> tuple[str | None, str | None]:
    """Column I contains '<English Title Case> <Arabic>' concatenated.
    Split on the first Arabic character."""
    if not s:
        return None, None
    m = re.search(r"[؀-ۿ]", s)
    if not m:
        return s.strip() or None, None
    en = s[:m.start()].strip() or None
    ar = s[m.start():].strip() or None
    return en, ar


def _parse_limit(raw: str | None) -> tuple[float | None, bool, str | None]:
    """Returns (limit_numeric, is_zero_tolerance, raw_value).

    'غير موجودة' / 'Not detected' / 0-equivalent → zero-tolerance (limit_numeric=0).
    Numeric strings are parsed; comparison prefixes stripped.
    """
    if raw is None:
        return None, False, None
    s = str(raw).strip()
    if not s or s in ("-",):
        return None, False, s or None
    if any(p in s for p in ("غير موجودة", "Not detected", "Absent", "absent")):
        return 0.0, True, s
    # Strip thousand separators, comparison prefixes.
    cleaned = re.sub(r"[<>≤≥]", "", s).strip()
    cleaned = cleaned.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
    cleaned = cleaned.replace(",", "").replace("٬", "")
    try:
        return float(cleaned), False, s
    except ValueError:
        return None, False, s


def parse_classification(path: Path) -> dict:
    df = pd.read_html(path)[0]

    # Walk rows, tracking the current section header.
    current_section_num: int | None = None
    current_section_name: str | None = None
    current_section_letter: str | None = None

    codes: dict[str, dict] = {}

    for _, row in df.iterrows():
        h_val = _norm(row.get("H"))
        g_val = _norm(row.get("G"))

        # Detect section header (e.g. "1. Dairy Products (A)").
        if h_val and not GSO_CODE_RE.match(g_val or ""):
            m = SECTION_HEADER_RE.match(h_val)
            if m:
                section_num = int(m.group(1))
                section_name = m.group(2).strip()
                section_letter = m.group(3)
                # Only update on a new section number.
                if section_num != current_section_num:
                    current_section_num = section_num
                    current_section_name = section_name
                    current_section_letter = section_letter
                continue

        if not g_val or not GSO_CODE_RE.match(g_val):
            continue

        code = g_val
        # Derive section letter from the code if the section header didn't have one.
        code_letter = code.split("-", 1)[0]
        letter = current_section_letter or code_letter

        if code not in codes:
            short_en, sample_ar = _split_en_ar(_norm(row.get("I")))
            codes[code] = {
                "code": code,
                "code_short": _norm(row.get("F")),
                "category_letter": letter,
                "category_section_number": current_section_num,
                "category_name_en": current_section_name,
                "name_en": _norm(row.get("H")),
                "name_en_long": short_en,         # fuller English (from col I)
                "name_ar": sample_ar,
                "sub_products_ar": _norm(row.get("J")),
                "in_scope": _norm(row.get("E")) == "🟢",
                "lims_progress": _norm(row.get("D")) == "✔️",
                "notes": _norm(row.get("N")),
                "required_tests": [],
            }

        test_name = _norm(row.get("K"))
        if not test_name:
            continue
        # Strip the '*' annotation prefix and trailing '**' markers (used in the
        # source to indicate optional/conditional tests).
        clean_test = test_name.lstrip("*").strip()
        optional = "*" in test_name
        clean_test = clean_test.rstrip("*").strip()
        limit_raw = _norm(row.get("L"))
        limit_num, zero_tol, raw = _parse_limit(limit_raw)
        codes[code]["required_tests"].append({
            "test": clean_test,
            "limit_raw": raw,
            "limit_numeric": limit_num,
            "zero_tolerance": zero_tol,
            "optional": optional,
        })

    # Order section names by letter for the categories block.
    categories: dict[str, dict] = {}
    for c in codes.values():
        letter = c["category_letter"]
        if letter and letter not in categories:
            categories[letter] = {
                "letter": letter,
                "name_en": c["category_name_en"],
                "section_number": c["category_section_number"],
                "codes": [],
            }
        if letter:
            categories[letter]["codes"].append(c["code"])

    return {
        "schema_name": "gso_1016_reference",
        "schema_version": 1,
        "source": "Classification.html (GSO 1016 standards table)",
        "categories": [categories[l] for l in sorted(categories.keys())],
        "codes": [codes[k] for k in sorted(codes.keys(), key=lambda x: (x.split("-")[0], int(x.split("-")[1].split("/")[0]), x))],
    }


def main() -> int:
    if not CLASS_HTML.exists():
        print(f"missing source: {CLASS_HTML}", file=sys.stderr)
        return 2
    parsed = parse_classification(CLASS_HTML)

    OUT_YAML.parent.mkdir(parents=True, exist_ok=True)
    with OUT_YAML.open("w", encoding="utf-8") as f:
        yaml.safe_dump(parsed, f, allow_unicode=True, sort_keys=False, width=140)

    n_codes = len(parsed["codes"])
    n_cats = len(parsed["categories"])
    n_tests = sum(len(c["required_tests"]) for c in parsed["codes"])
    print(f"wrote {OUT_YAML}")
    print(f"  {n_cats} categories · {n_codes} gso_codes · {n_tests} test-requirement rows")

    # Coverage check: how many gso_codes in our cleaned data are NOT in the reference?
    long_path = ROOT / "cleaned" / "data2024_long.parquet"
    if long_path.exists():
        long = pd.read_parquet(long_path)
        data_codes = set(long["gso_code"].dropna().unique().tolist())
        ref_codes = set(c["code"] for c in parsed["codes"])
        missing = sorted(data_codes - ref_codes)
        covered = data_codes & ref_codes
        print(f"  2024 data coverage: {len(covered)}/{len(data_codes)} codes match the reference")
        if missing:
            print(f"  unmatched data codes (not in reference): {missing[:30]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
