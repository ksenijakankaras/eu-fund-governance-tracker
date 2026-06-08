# EU Fund Governance Tracker

An end-to-end data pipeline and governance dashboard built on real EU structural fund data, demonstrating automated data cleaning, interactive visualisation, and scheduled reporting — mirroring the mandate management workflows used by institutions such as the European Investment Fund (EIF).

---

## Project Overview

The European Structural and Investment Funds (ESIF) programme allocated over €62 billion to 23 EU member states across the 2014–2020 programming period. Tracking payment progress, identifying underspend risk, and delivering automated governance summaries are core activities for any mandate management team.

This project builds a lightweight version of that infrastructure from scratch:

- A **Python pipeline** that ingests raw EU payment data, applies data quality checks, and exports analysis-ready tables
- A **Power BI dashboard** that visualises fund performance across countries, fund types, and time
- A **Power Automate flow** that delivers a scheduled weekly governance summary email automatically every Monday

All components are built on real, publicly available EU Open Data and the Microsoft 365 stack.

---

## Repository Structure

```
eu-fund-governance-tracker/
│
├── data/
│   ├── esif_2014_2020_payments.csv        # Raw source data (EU Open Data Portal)
│   └── clean/
│       ├── esif_snapshot_2023.csv         # Main analysis table (2023 snapshot)
│       └── esif_timeseries.csv            # Aggregated time series 2014–2024
│
├── scripts/
│   └── clean_data.py                      # Full data cleaning pipeline
│
├── docs/
│   ├── screenshots/                       # Dashboard and flow screenshots
│   └── data-dictionary.md                 # Column definitions and data notes
│
└── README.md
```

---

## Data Source

**ESIF 2014–2020 EU Payments (daily update)**
Published by the European Commission — Directorate-General for Regional and Urban Policy
Available at: [data.europa.eu](https://data.europa.eu)

The dataset tracks cumulative EU payments to ESI Fund programmes across member states, including ERDF, ESF, Cohesion Fund, EAFRD, EMFF, YEI, FEAD, and others.

---

## Component 1 — Python Data Pipeline

### What it does

`scripts/clean_data.py` takes the raw 1,000-row, 28-column ESIF payments CSV and produces two clean, analysis-ready tables.

### Key design decisions

**Snapshot year selection:** The dataset is cumulative — each row represents total payments from 2014 up to that year, not payments made in that year alone. Keeping all years and summing would multiply every amount by up to 13×. A single snapshot year must be chosen for cross-sectional analysis.

The `is_latest_period` flag in the raw data marks only 33 rows, all from 2026, covering just 11 countries — an incomplete snapshot that would produce a misleading dashboard. **2023 was selected as the main snapshot year** because it is the last year with full coverage: 100 rows, 23 countries, all major fund types represented.

**Fund type simplification:** Three verbose YEI variants (`YEI`, `YEI ESF Matching Component`, `YEI Specific Allocation`) were collapsed into a single `YEI` label to avoid artificial fragmentation in visualisations.

**Terminology choice:** The derived column for unspent allocation is named `remaining_eur` rather than `unspent_eur`. In EU fund governance, money not yet paid out is not necessarily problematic — it may be scheduled, pending verification, or within programme timelines. "Remaining" is a neutral, accurate term; "unspent" carries an implied negative connotation inappropriate for a governance context.

**Payment status thresholds:** Programmes are categorised into three bands:
- **High progress:** payment rate ≥ 85%
- **Medium progress:** payment rate 50–84%
- **Low progress:** payment rate < 50%

Thresholds reflect realistic expectations for a programme running since 2014 and approaching its closure period.

**Time series scope:** Years 2025 and 2026 are excluded from the trend chart because coverage is incomplete (34 and 33 rows respectively vs. 100 for full years). Including them would create a misleading visual impression of accelerated late-period spending.

### Outputs

| File | Rows | Columns | Purpose |
|------|------|---------|---------|
| `esif_snapshot_2023.csv` | 100 | 14 | Cross-sectional analysis, all dashboard visuals except trend line |
| `esif_timeseries.csv` | 11 | 4 | Annual trend line (2014–2024) |

### Data Quality Report (2023 snapshot)

| Check | Result |
|-------|--------|
| Total programmes | 100 |
| Countries covered | 23 |
| Missing: `programme_title` | 3 rows — acceptable, `programme_code` still uniquely identifies them |
| Missing: `region_category` | 36 rows — acceptable, some programmes operate at national rather than regional level |
| Missing: `payment_rate_pct` | 1 row — handled as "Unknown" in status categorisation |
| Total planned (€) | 62.30bn |
| Total paid (€) | 51.01bn |
| Total remaining (€) | 11.29bn |
| Overall payment rate | 80.4% |

### Running the pipeline

```bash
# From project root
python scripts/clean_data.py
```

Requirements: Python 3.x, pandas

```bash
pip install pandas
```

---

## Component 2 — Power BI Dashboard

### What it shows

A single-page governance dashboard with four visuals built on the two clean CSV tables.

**KPI Cards (top row)**
Four headline figures: Total Planned (€62.30bn), Total Paid (€51.01bn), Total Remaining (€11.29bn), Overall Payment Rate (80.4%).

**Programme Payment Status — 2023 Snapshot (donut chart)**
Traffic-light breakdown of all 100 programmes: 60% High Progress, 25% Medium Progress, 14% Low Progress, 1% Unknown. Immediately communicates governance health at a glance.

**Planned vs Paid by Country — 2023 (clustered bar chart)**
All 23 countries ranked by planned allocation. Poland dominates at €16.3bn planned. Italy shows the largest gap between planned and paid (€3.6bn remaining) despite being the third-largest recipient — a governance risk signal.

**EU Payment Rate Trend 2014–2024 (line chart)**
The full arc of the programming period: from 1% payment rate in 2014 to 97% by 2024. The steep acceleration from 2019 onwards reflects the programme reaching maturity and closure deadlines approaching.

### Dashboard screenshot

![Dashboard](docs/dashboard.png)

### Data model

Two tables loaded separately in Power BI Desktop:
- `esif_snapshot_2023` — powers all cross-sectional visuals
- `esif_timeseries` — powers the trend line exclusively

Tables are intentionally kept separate — no relationship defined — because they operate at different granularities (programme-level vs. year-level aggregate). Each visual queries only the table appropriate to its purpose.

---

## Component 3 — Power Automate Flow

### What it does

A scheduled cloud flow that runs every Monday and automatically delivers a governance summary email — simulating the kind of automated mandate status reporting used in fund management operations.

**Trigger:** Recurrence — every Monday
**Action:** Send an email (Office 365 Outlook) with a structured governance summary including key metrics, programme status breakdown, and top countries by planned and remaining allocation. A dynamic `utcNow()` timestamp is injected at the top of each email so every delivery is dated automatically.

### Architecture

```
[Recurrence trigger — every Monday]
            ↓
[Send email — Office 365 Outlook]
  To:      governance team / analyst
  Subject: Weekly Fund Governance Summary – ESIF 2014-2020
  Body:    Structured summary with dynamic timestamp + key metrics
```

### What this demonstrates

In a production EIF environment, this flow would query a live SharePoint list or database to populate the metrics dynamically. In this prototype, the metrics are drawn from the 2023 snapshot analysis. The key demonstration is the automation pattern: a governance summary delivered reliably on a schedule without any manual intervention, with a self-updating timestamp confirming each run.

### Flow screenshot

![Power Automate Flow](docs/power_automate.png)


---

## Key Findings

1. **Overall payment rate of 80.4%** across the 2014–2020 programming period as of 2023 — broadly on track given that some programmes run through 2025/2026 closure dates.

2. **Italy presents the largest governance risk** — third-largest recipient at €8.2bn planned but €3.6bn (44%) still remaining as of 2023, the highest unabsorbed amount of any country.

3. **14 programmes (14%) are in Low Progress** with payment rates below 50% — these would be priority cases for a mandate management team's attention.

4. **The 2019–2023 acceleration is significant** — payment rate jumped from 40% to 82% in four years, reflecting both programme maturity and pressure from approaching closure deadlines.

5. **Poland is the dominant recipient** at €16.3bn planned — nearly double Spain in second place — reflecting its status as the largest beneficiary of EU cohesion policy.

---

## Technical Stack

| Component | Tool | Purpose |
|-----------|------|---------|
| Data cleaning | Python, pandas | Pipeline, quality checks, export |
| Dashboard | Microsoft Power BI Desktop | Visualisation, data model |
| Automation | Microsoft Power Automate | Scheduled reporting flow |
| Data platform | Microsoft SharePoint / M365 | Flow integration layer |
| Version control | Git / GitHub | Repo, commits, documentation |
| Data source | EU Open Data Portal | ESIF 2014–2020 payments CSV |

---

## Relevance to Fund Governance Work

This project was designed to mirror the core activities of a mandate management unit:

| JD Requirement | Project Implementation |
|---------------|----------------------|
| Support development of data visualisation tools | Power BI dashboard with 4 visuals, clean data model, published report |
| Automate data collection and visualisation | Python pipeline automates all data preparation; Power Automate delivers automated reporting |
| At least one new visual dashboard (Tableau/Power BI) | Power BI dashboard — 4 visuals, KPIs, trend, status, country breakdown |
| At least one new Power Automate flow | Weekly scheduled governance summary flow, tested and operational |
| Draft technical documentation and guidelines | This README + data dictionary + architecture notes |
| Data quality analysis | Documented quality report: missing values, snapshot rationale, threshold decisions |

---

## Author

Ksenija Kankaras
BSc Economics, Management and Computer Science — Bocconi University
[ksenija.kankaras@studbocconi.it](mailto:ksenija.kankaras@studbocconi.it)
