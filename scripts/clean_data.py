import pandas as pd

raw = pd.read_csv(
    "data/esif_2014_2020_payments.csv",
    encoding="utf-8-sig"
)

print("=== COLUMNS ===")
for col in raw.columns:
    print(repr(col))

print(f"\nRows: {len(raw)}")
print(f"Years in data: {sorted(raw['year'].unique())}")
print(f"Funds in data: {sorted(raw['fund'].dropna().unique())}")
print(f"Countries: {raw['ms_name'].nunique()} unique")