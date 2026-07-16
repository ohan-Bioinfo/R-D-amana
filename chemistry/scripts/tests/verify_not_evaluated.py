import re, json, sys
html = open("reports/chemistry_dashboard.html", encoding="utf-8").read()
m = re.search(r"const DATA = (\{.*?\});\n\s*const COLS", html, re.S)
assert m, "could not extract DATA payload"
tc = json.loads(m.group(1))["test_counts"]

# grand split has not_evaluated and the invariant holds
gs = tc["compliance_split"]
assert "not_evaluated" in gs, "grand split missing not_evaluated"
assert gs["compliant"] + gs["non_compliant"] + gs["not_evaluated"] == tc["grand"], \
    f"grand invariant broken: {gs} vs grand {tc['grand']}"
assert gs["not_evaluated"] > 0, "expected non-zero not_evaluated (jam)"

# jam section is entirely not_evaluated
jam = tc["compliance_split_by_section_year"]["jam"]
for yr, s in jam.items():
    assert s["compliant"] == 0 and s["non_compliant"] == 0 and s["not_evaluated"] > 0, \
        f"jam {yr} should be all not_evaluated, got {s}"
    assert s["not_evaluated"] == tc["by_section_year"]["jam"][yr], "jam not_evaluated != jam total"

# a limit-bearing section keeps real compliance (regression guard)
hm = tc["compliance_split_by_section_year"]["heavy_metals"]
assert any(s["compliant"] > 0 for s in hm.values()), "heavy_metals lost its compliant count!"
assert all(s["not_evaluated"] == 0 for s in hm.values()), "heavy_metals wrongly not_evaluated"

# per-year invariant
for yr, s in tc["compliance_split_by_year"].items():
    assert s["compliant"] + s["non_compliant"] + s["not_evaluated"] == tc["by_year"][yr], \
        f"year {yr} invariant broken"

assert "Not evaluated" in html, "test-banner 'Not evaluated' item missing"
print("NOT_EVALUATED OK  (jam not_evaluated =", gs["not_evaluated"], ")")
