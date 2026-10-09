# Stock Data Monthly Aggregation Pipeline

A Python pipeline that transforms daily stock price data into monthly summaries with technical indicators — built as a Data Engineering Intern assignment for **Fam**.

## Quick Start

```bash
pip install -r requirements.txt
python pipeline.py
# Output files are written to output/ directory
```

## What It Does

```
output_file.csv (5030 daily rows, 10 tickers, 2 years)
        │
        ▼
  ┌─────────────┐
  │  pipeline.py │
  └──────┬──────┘
         │  1. Load & validate
         │  2. Resample daily → monthly OHLCV
         │  3. Compute technical indicators
         │  4. Partition by ticker
         ▼
  output/
  ├── result_AAPL.csv  (24 rows)
  ├── result_AMD.csv   (24 rows)
  ├── result_AMZN.csv  (24 rows)
  ├── result_AVGO.csv  (24 rows)
  ├── result_CSCO.csv  (24 rows)
  ├── result_MSFT.csv  (24 rows)
  ├── result_NFLX.csv  (24 rows)
  ├── result_PEP.csv   (24 rows)
  ├── result_TMUS.csv  (24 rows)
  └── result_TSLA.csv  (24 rows)
```

The pipeline is **idempotent** — running it multiple times on the same input always produces identical output files, with no side effects from previous runs.

## Output Schema

Each output CSV has **24 rows** (one per month, Jan 2018 – Dec 2019) with these columns:

| Column | Description |
|---|---|
| `month` | Year-month label (e.g. `2018-01`) |
| `open` | Opening price on the **first** trading day of the month |
| `high` | **Maximum** daily high during the month |
| `low` | **Minimum** daily low during the month |
| `close` | Closing price on the **last** trading day of the month |
| `volume` | Sum of daily trading volume for the month |
| `sma_10` | 10-period Simple Moving Average of monthly close |
| `sma_20` | 20-period Simple Moving Average of monthly close |
| `ema_10` | 10-period Exponential Moving Average of monthly close |
| `ema_20` | 20-period Exponential Moving Average of monthly close |
| `bb_middle` | Bollinger Band middle (20-period SMA of close) |
| `bb_upper` | Bollinger Band upper (middle + 2 × rolling std) |
| `bb_lower` | Bollinger Band lower (middle − 2 × rolling std) |
| `dc_upper` | Donchian Channel upper (20-period rolling max of monthly high) |
| `dc_lower` | Donchian Channel lower (20-period rolling min of monthly low) |
| `zscore` | Z-Score volatility indicator (20-period) |

## Assumptions

### OHLC Aggregation
- **Open** is the `open` price of the chronologically **first** trading day in the month (not an average).
- **Close** is the `close` price of the chronologically **last** trading day in the month (not an average).
- **High** and **Low** are the max/min across all trading days in the month, taken from the daily `high` and `low` columns respectively.
- **Volume** is summed across all trading days in the month.

### Technical Indicators
- All indicators are computed on **monthly** close prices (or monthly high/low for Donchian Channels), **per ticker independently** — no cross-ticker contamination.
- **SMA** uses a standard rolling mean with `min_periods = window` — produces `NaN` until enough data points are available.
- **EMA** is seeded with the SMA of the first *N* periods, then applies the standard recursive formula:  
  `EMA_t = (Price_t − EMA_{t−1}) × Multiplier + EMA_{t−1}`  
  where `Multiplier = 2 / (N + 1)`. This matches the [Investopedia EMA definition](https://www.investopedia.com/terms/e/ema.asp).  
  I intentionally avoided pandas `ewm(adjust=False)` because it initialises from the first data point rather than from SMA, producing slightly different values than the standard financial convention.
- **Bollinger Bands** use `n = 20` (window) and `k = 2` (standard deviation multiplier) — the widely accepted defaults. Standard deviation uses `ddof=1` (sample std), matching financial platforms like Bloomberg and TradingView.
- **Donchian Channels** use a 20-period rolling window on monthly high (upper) and monthly low (lower).
- **Z-Score** = `(close − rolling_mean) / rolling_std` over a 20-period window, measuring how many standard deviations the current price deviates from the mean.

### Window Periods
- The assignment specifies SMA and EMA at 10 and 20 periods.
- Donchian, Bollinger, and Z-Score windows are set to **20 periods** (the most common default in financial analysis). Since we only have 24 monthly data points, using a 20-period window means these indicators produce values only for the last 5 months. This is mathematically correct — using a smaller window would sacrifice the standard.

### NaN Handling
- Indicators that require a minimum number of historical data points produce `NaN` for early months where the window hasn't been filled. This is expected — fabricating values for insufficient data would be misleading.

### Data Quality
- The input data has **no nulls, no duplicate (date, ticker) pairs**, and exactly **503 trading days** per ticker across **24 calendar months**.
- The dataset is sorted by `(ticker, date)` during loading to ensure chronological correctness — the raw CSV is shuffled.
- Column presence and null checks run on every pipeline execution, failing loudly before any transformation if something is wrong.

## Code Structure

```
pipeline.py           # Main script — single entry point
├── load_data()       # Data loading with schema & null validation
├── resample_to_monthly()  # Daily → Monthly OHLCV aggregation
├── add_technical_indicators()  # Orchestrates all indicator computations
│   ├── compute_sma()          # Simple Moving Average
│   ├── compute_ema()          # Exponential Moving Average (SMA-seeded)
│   ├── compute_bollinger_bands()  # Mid / Upper / Lower bands
│   ├── compute_donchian_channels() # Upper / Lower channels
│   └── compute_zscore()       # Z-Score volatility
├── write_partitioned_output() # Validates row counts & writes 10 CSVs
└── main()            # Pipeline orchestrator
```

Calculation logic is cleanly separated from I/O logic, with each indicator in its own function. No third-party technical analysis libraries — all computations use pandas aggregate, window, and custom functions as required.

## Validation

A separate `validate.py` script cross-checks the pipeline output against manually computed values:
- OHLC values vs. first/last/max/min from raw daily data
- SMA values vs. manual rolling mean
- EMA values vs. hand-computed recursive formula step by step
- Bollinger Band values vs. manual rolling mean ± 2σ
- Row counts (24 per file for all 10 tickers)

```bash
python validate.py
```

## How This Would Scale

This pipeline processes ~5K rows in under a second, but the same design maps to production scale:

- **Larger data volumes:** The `groupby → resample → agg` pattern maps directly to Spark's `groupBy` + window functions. The pandas logic would become a Spark SQL transform reading from a partitioned lakehouse table.
- **Orchestration:** `main()` currently runs all four steps linearly. In production, each step would be a separate Airflow DAG task with dependencies, so failures can be retried at the step level rather than re-running everything.
- **Output format:** CSV works for 24 rows; at scale, Parquet with ticker-based partitioning (`output/ticker=AAPL/data.parquet`) saves storage and enables partition pruning on queries.
- **Idempotency:** The pipeline already overwrites output files deterministically. In a lakehouse, this maps to an `INSERT OVERWRITE PARTITION` pattern — re-running a month never creates duplicates.
- **Data quality:** The `assert len(group) == 24` check is a basic version of what Great Expectations or dbt tests do in production — validate row counts, null rates, and value ranges before publishing data downstream.

## Dependencies

- **Python 3.8+**
- **pandas** (tested with 2.x)

No other libraries required. See `requirements.txt`.
