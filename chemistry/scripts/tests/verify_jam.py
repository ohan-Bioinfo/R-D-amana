import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
df = pd.read_parquet("cleaned/chem_jam_2024.parquet")

assert len(df) == 83, f"expected 83 jam rows, got {len(df)}"
cats = set(df["sample_category_canonical"].dropna().unique())
assert cats == {"المربى والجلي"}, f"all jam rows must be Jelly/Jam, got {cats}"

# Validity: exactly one غير مطابقة (is_valid False), the rest unknown (null).
false_n = (df["is_valid"] == False).sum()
assert false_n == 1, f"expected 1 non-compliant jam row, got {false_n}"

# Sugar panel populated (display-only values present for most rows).
for col in ["fructose_value", "glucose_value", "glucose_plus_fructose_value",
            "sucrose_value", "hmf_value", "moisture_value", "ph_value"]:
    assert col in df.columns, f"missing column {col}"
    assert df[col].notna().sum() >= 70, f"{col} mostly empty ({df[col].notna().sum()}/84)"

print("JAM VERIFY OK  (rows:", len(df), ")")
