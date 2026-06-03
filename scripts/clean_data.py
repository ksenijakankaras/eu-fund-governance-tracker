import pandas as pd
import os

# data
raw = pd.read_csv("data/esif_2014_2020_payments.csv", encoding="utf-8-sig")
print(f"Raw shape: {raw.shape}")

# we use 2023 as the main snapshot year; 100 rows, 23 countries, most complete
snap = raw[raw["year"] == 2023].copy()

# renaming for dashboard readability
snap = snap[[
    "ms", "ms_name", "cci", "title", "fund",
    "category_of_region", "year",
    "net_planned_eu_amount",
    "total_net_payments",
    "eu_payment_rate_on_planned_eu_amount",
    "cumulative_interim_payments",
    "net_pre_financing"
]].rename(columns={
    "ms":                                    "country_code",
    "ms_name":                               "country",
    "cci":                                   "programme_code",
    "title":                                 "programme_title",
    "fund":                                  "fund_type",
    "category_of_region":                    "region_category",
    "year":                                  "snapshot_year",
    "net_planned_eu_amount":                 "planned_eur",
    "total_net_payments":                    "total_payments_eur",
    "eu_payment_rate_on_planned_eu_amount":  "payment_rate_on_planned_amount",
    "cumulative_interim_payments":           "interim_payments_eur",
    "net_pre_financing":                     "pre_financing_eur",
})

# types
money_cols = ["planned_eur", "total_payments_eur", "interim_payments_eur", "pre_financing_eur"]

rate_cols = ["payment_rate_on_planned_amount"]

for col in money_cols + rate_cols:
    snap[col] = pd.to_numeric(snap[col], errors="coerce")

# deriving new columns; remaining eur amount to be paid, cleaned fund type and payment status

snap["remaining_eur"] = snap["planned_eur"] - snap["total_payments_eur"]

# simplify verbose YEI fund variants into one label for cleaner charts
fund_map = {
    "YEI ESF Matching Component":  "YEI",
    "YEI Specific Allocation":     "YEI",
    "IPAE-contribution from ERDF": "IPAE"
}
snap["fund_type"] = snap["fund_type"].replace(fund_map)

# Payment status: governance traffic-light categorisation
# 85%+ = high progress, 50-84% = moderate progress, <50% = risky
def payment_status(rate):
    if pd.isna(rate):    
        return "Unknown"
    elif rate >= 85:     
        return "High progress"
    elif rate >= 50:     
        return "Medium progress"
    else:                
        return "Low progress"

snap["payment_status"] = snap["payment_rate_on_planned_amount"].apply(payment_status)

# TIME SERIES TABLE (for the trend chart) 
# aggregate all years — this powers the payment rate over time line chart
ts = (raw
    .groupby("year")
    .agg(
        planned_eur=("net_planned_eu_amount", "sum"),
        total_payments_eur=("total_net_payments", "sum")
    )
    .reset_index()
)
ts["payment_rate_on_planned_amount"] = (
    ts["total_payments_eur"] / ts["planned_eur"] * 100
).round(1)

# we drop 2025/2026 from time series — incomplete coverage skews the rate upward
ts = ts[ts["year"] <= 2024]

# data quality report
print("\n=== DATA QUALITY REPORT ===")
print(f"Snapshot year: 2023 | Programmes: {len(snap)} | Countries: {snap['country'].nunique()}")

print("\nMissing values:")
missing = snap.isnull().sum()
missing = missing[missing > 0]
print("  None" if len(missing) == 0 else missing.to_string())

print("\nPayment status breakdown:")
print(snap["payment_status"].value_counts().to_string())

print("\nTop 5 countries by planned amount:")
top5 = (snap.groupby("country")["planned_eur"]
            .sum().sort_values(ascending=False).head(5))
for country, val in top5.items():
    print(f"  {country}: €{val/1e9:.1f}B")

print("\nTop 5 countries by remaining planned amount:")
top_unspent = (snap.groupby("country")["remaining_eur"]
                   .sum().sort_values(ascending=False).head(5))
for country, val in top_unspent.items():
    print(f"  {country}: €{val/1e9:.1f}B")

print("\nOverall programme figures:")
print(f"  Total planned:  €{snap['planned_eur'].sum()/1e9:.1f}B")
print(f"  Total paid:     €{snap['total_payments_eur'].sum()/1e9:.1f}B")
print(f"  Total remaining planned amount :  €{snap['remaining_eur'].sum()/1e9:.1f}B")
print(f"  Overall rate:   {snap['total_payments_eur'].sum()/snap['planned_eur'].sum()*100:.1f}%")

# exporting
os.makedirs("data/clean", exist_ok=True)

snap.to_csv("data/clean/esif_snapshot_2023.csv",
            index=False, encoding="utf-8-sig")

ts.to_csv("data/clean/esif_timeseries.csv",
          index=False, encoding="utf-8-sig")

print("\n✓ Saved: data/clean/esif_snapshot_2023.csv")
print("✓ Saved: data/clean/esif_timeseries.csv")
print(f"  Snapshot shape: {snap.shape}")
print(f"  Time series shape: {ts.shape}")