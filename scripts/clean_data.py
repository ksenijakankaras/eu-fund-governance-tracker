import pandas as pd
import os

# data
raw = pd.read_csv("data/esif_2014_2020_payments.csv", encoding="utf-8-sig")
print(f"Raw shape: {raw.shape}")

# VALIDATION
# Every check is recorded with its stage, value, rule and status.
# "fail" stops the pipeline before anything is exported; "warn" is reported but does not stop it.
checks = []

def check(stage, name, value, ok, rule, severity="fail"):
    checks.append({
        "stage": stage, "check": name, "value": value, "rule": rule,
        "status": "pass" if ok else severity,
    })

REQUIRED_COLS = [
    "ms", "ms_name", "cci", "title", "fund", "category_of_region", "year",
    "net_planned_eu_amount", "total_net_payments",
    "eu_payment_rate_on_planned_eu_amount",
    "cumulative_interim_payments", "net_pre_financing",
]
RAW_KEY = ["cci", "fund", "category_of_region", "year"]

# Stage 1: raw extract
missing_cols = [c for c in REQUIRED_COLS if c not in raw.columns]
check("raw", "required_columns_present", len(missing_cols), len(missing_cols) == 0, "0 missing columns")
check("raw", "duplicate_programme_fund_region_year", int(raw.duplicated(RAW_KEY).sum()),
      raw.duplicated(RAW_KEY).sum() == 0, "0 duplicates on " + "/".join(RAW_KEY))
# An extract of exactly 1,000 rows often means a download or API row limit was hit
check("raw", "row_count_not_capped", len(raw), len(raw) != 1000,
      "!= 1000 (possible export limit)", severity="warn")

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
snap["fund_type_raw"] = snap["fund_type"]
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


# Stage 2: cleaned snapshot
SNAP_KEY = ["programme_code", "fund_type_raw", "region_category"]
check("snapshot", "programme_rows_unique",
      int(snap.duplicated(SNAP_KEY).sum()), snap.duplicated(SNAP_KEY).sum() == 0,
      "0 duplicates on programme/fund/region")
key_fields = ["country", "programme_code", "planned_eur", "total_payments_eur"]
n_missing_keys = int(snap[key_fields].isnull().sum().sum())
check("snapshot", "no_missing_key_fields", n_missing_keys, n_missing_keys == 0, "0 missing in " + ", ".join(key_fields))
n_negative = int((snap[money_cols] < 0).sum().sum())
check("snapshot", "no_negative_amounts", n_negative, n_negative == 0, "0 negative amounts")
rates = snap["payment_rate_on_planned_amount"].dropna()
n_bad_rates = int(((rates < 0) | (rates > 105)).sum())
check("snapshot", "payment_rate_in_range", n_bad_rates, n_bad_rates == 0, "0 rates outside 0-105%")
n_missing_rate = int(snap["payment_rate_on_planned_amount"].isnull().sum())
check("snapshot", "payment_rate_available", n_missing_rate, n_missing_rate == 0,
      "0 programmes without a payment rate", severity="warn")
planned_pos = snap["planned_eur"] > 0
n_overpaid = int((snap.loc[planned_pos, "total_payments_eur"] > 1.05 * snap.loc[planned_pos, "planned_eur"]).sum())
check("snapshot", "payments_within_planned", n_overpaid, n_overpaid == 0, "payments <= 105% of planned")
rate_recalc = snap.loc[planned_pos, "total_payments_eur"] / snap.loc[planned_pos, "planned_eur"] * 100
rate_gap = (rate_recalc - snap.loc[planned_pos, "payment_rate_on_planned_amount"]).abs().max()
check("snapshot", "payment_rate_matches_amounts", round(float(rate_gap), 3), rate_gap < 0.5,
      "reported rate within 0.5 pp of payments / planned", severity="warn")
raw_2023 = raw[raw["year"] == 2023]
planned_raw = pd.to_numeric(raw_2023["net_planned_eu_amount"], errors="coerce").sum()
recon_gap = abs(snap["planned_eur"].sum() - planned_raw)
check("snapshot", "planned_total_reconciles_to_raw", round(float(recon_gap), 2), recon_gap < 1,
      "snapshot planned total = raw 2023 total (< EUR 1)")

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


# Stage 3: report and stop on failures (before anything is exported)
report = pd.DataFrame(checks)
print("\n=== VALIDATION CHECKS ===")
print(report.to_string(index=False))
os.makedirs("data/clean", exist_ok=True)
report.to_csv("data/clean/validation_report.csv", index=False, encoding="utf-8-sig")
failed = report[report["status"] == "fail"]
if len(failed) > 0:
    raise SystemExit(f"\n{len(failed)} validation check(s) failed - nothing exported. See data/clean/validation_report.csv")

# exporting
os.makedirs("data/clean", exist_ok=True)

snap.drop(columns=["fund_type_raw"]).to_csv("data/clean/esif_snapshot_2023.csv",
            index=False, encoding="utf-8-sig")

ts.to_csv("data/clean/esif_timeseries.csv",
          index=False, encoding="utf-8-sig")

print("\n✓ Saved: data/clean/esif_snapshot_2023.csv")
print("✓ Saved: data/clean/esif_timeseries.csv")
print(f"  Snapshot shape: {snap.drop(columns=['fund_type_raw']).shape}")
print(f"  Time series shape: {ts.shape}")