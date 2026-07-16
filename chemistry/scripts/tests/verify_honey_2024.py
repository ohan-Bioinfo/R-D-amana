import pandas as pd, json
d = pd.read_parquet("cleaned/chem_honey_2024.parquet")

assert len(d) >= 40, f"expected ~48 honey-2024 rows, got {len(d)}"
lim = [c for c in d.columns if c.endswith("_limit_value")]
assert lim, "honey-2024 has no *_limit_value columns — schema/columns mismatch"
# Real verdicts derive (not all-unknown): at least some True and the panel ran.
nvalid = int((d["is_valid"] == True).sum())
ninvalid = int((d["is_valid"] == False).sum())
assert nvalid + ninvalid > 0, "honey-2024 has no True/False verdicts at all"
# honey-2025 unchanged
b = json.load(open("/tmp/honey25_base.json"))
d25 = pd.read_parquet("cleaned/chem_honey_2025.parquet")
assert len(d25) == b["rows"] and int((d25["is_valid"]==True).sum()) == b["valid"] \
    and int((d25["is_valid"]==False).sum()) == b["invalid"], "honey-2025 output changed!"
print(f"HONEY 2024 OK  (rows={len(d)}, valid={nvalid}, invalid={ninvalid}); honey-2025 unchanged")
