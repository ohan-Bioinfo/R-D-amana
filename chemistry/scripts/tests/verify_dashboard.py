import re, json
html = open("reports/chemistry_dashboard.html", encoding="utf-8").read()
m = re.search(r"const DATA = (\{.*?\});\n\s*const COLS", html, re.S)
assert m, "could not extract DATA payload"
DATA = json.loads(m.group(1))
cols = {c: i for i, c in enumerate(DATA["cols"])}
assert "sample_name_group" in cols, "sample_name_group missing from payload"
FRUIT = {"ليمون","برتقال","يوسفي","فراولة","تفاح","عنب","بصل","طماطم","خس","شطة","فلفل"}
DAIRY = "الحليب ومنتجات الألبان"   # C_DAIRY — payload slot "sample_category" is the canonical category
bad = []
for sec in DATA["sections"].values():
    for row in sec["rows"]:
        g = row[cols["sample_name_group"]]
        if row[cols["sample_category"]] == DAIRY and g in FRUIT:
            bad.append(row[cols["sample_name"]])
assert not bad, f"dairy rows grouped as fruit: {bad[:5]}"
print("DASHBOARD VERIFY OK")
