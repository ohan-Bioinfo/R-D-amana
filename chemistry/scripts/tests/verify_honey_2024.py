import pandas as pd
d = pd.read_parquet("cleaned/chem_honey_2024.parquet")

assert len(d) >= 40, f"expected ~45 honey-2024 rows, got {len(d)}"
lim = [c for c in d.columns if c.endswith("_limit_value")]
assert lim, "honey-2024 has no *_limit_value columns — schema/columns mismatch"
# Real verdicts derive — BOTH pass and fail buckets non-empty (not all-unknown).
nvalid = int((d["is_valid"] == True).sum())
ninvalid = int((d["is_valid"] == False).sum())
assert nvalid > 0 and ninvalid > 0, \
    f"honey-2024 verdicts not both present: valid={nvalid} invalid={ninvalid}"
# honey-2025 unchanged — pinned to its known baseline (self-contained, no scratch file).
HONEY25 = {"rows": 25, "valid": 16, "invalid": 9}
d25 = pd.read_parquet("cleaned/chem_honey_2025.parquet")
g = {"rows": len(d25), "valid": int((d25["is_valid"] == True).sum()),
     "invalid": int((d25["is_valid"] == False).sum())}
assert g == HONEY25, f"honey-2025 output changed! got {g}, expected {HONEY25}"
print(f"HONEY 2024 OK  (rows={len(d)}, valid={nvalid}, invalid={ninvalid}); honey-2025 unchanged")
