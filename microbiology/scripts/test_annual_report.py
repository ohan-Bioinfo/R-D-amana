"""Standalone tests for annual_report.py (no pytest dependency).

Run: microbiology/.venv/bin/python microbiology/scripts/test_annual_report.py
"""
from pathlib import Path
from annual_report import load_annual_report, load_all_annual_figures

BASE = Path(__file__).resolve().parent.parent
REPORT = BASE / "2025-original" / "Annual Report 2025.xlsx"


def test_2025_totals():
    b = load_annual_report(REPORT, 2025)
    assert b["total_samples"] == 11404, b.get("total_samples")
    assert b["compliant"] == 8345, b.get("compliant")
    assert round(b["compliance_rate"], 2) == 73.18, b.get("compliance_rate")
    assert b["total_tests"] == 46309, b.get("total_tests")
    assert b["non_compliant_tests"] == 4211, b.get("non_compliant_tests")


def test_2025_per_test_ranked_by_rate():
    b = load_annual_report(REPORT, 2025)
    top = b["per_test"][0]
    assert top["name_en"] == "Aerobic plate count", top["name_en"]
    assert top["rate"] == 22.8, top["rate"]
    rates = [t["rate"] for t in b["per_test"]]
    assert rates == sorted(rates, reverse=True), "per_test not sorted by rate"
    assert all(t["name_en"].lower() != "total" for t in b["per_test"]), "Total row leaked into per_test"


def test_2025_sectors_central_largest():
    b = load_annual_report(REPORT, 2025)
    assert b["sectors"][0]["name_ar"].strip() == "القطاع الأوسط", b["sectors"][0]
    assert b["sectors"][0]["samples"] == 6790, b["sectors"][0]


def test_load_all_has_2025():
    figs = load_all_annual_figures(BASE)
    assert 2025 in figs and figs[2025]["total_samples"] == 11404


if __name__ == "__main__":
    tests = [test_2025_totals, test_2025_per_test_ranked_by_rate,
             test_2025_sectors_central_largest, test_load_all_has_2025]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except Exception as e:
            failed += 1
            print(f"FAIL  {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(tests)-failed} passed, {failed} failed")
    raise SystemExit(1 if failed else 0)
