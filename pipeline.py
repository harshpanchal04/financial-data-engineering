"""
Data Engineering Intern Assignment - Stock Data Monthly Aggregation & Technical Indicators

Transforms daily stock price data into monthly summaries with technical indicators.
Outputs one CSV per ticker symbol with exactly 24 rows (Jan 2018 - Dec 2019).

Author: Harsh
"""

import pandas as pd
import os
from typing import Dict

 
# CONFIGURATION
 

INPUT_FILE = "output_file.csv"
OUTPUT_DIR = "output"

# Technical indicator window periods
SMA_SHORT = 10
SMA_LONG = 20
EMA_SHORT = 10
EMA_LONG = 20
DONCHIAN_WINDOW = 20
BOLLINGER_WINDOW = 20
BOLLINGER_K = 2  # Standard deviation multiplier for Bollinger Bands
ZSCORE_WINDOW = 20


 
# DATA LOADING
 

def load_data(filepath: str) -> pd.DataFrame:
    """Load and validate the input CSV dataset.
    
    Args:
        filepath: Path to the input CSV file.
        
    Returns:
        DataFrame with parsed dates, sorted by ticker and date.
        
    Raises:
        FileNotFoundError: If the input file doesn't exist.
        ValueError: If required columns are missing or data validation fails.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Input file not found: {filepath}")

    df = pd.read_csv(filepath, parse_dates=["date"])

    # Validate required columns
    required_cols = {"date", "volume", "open", "high", "low", "close", "adjclose", "ticker"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # Validate no nulls in critical columns
    null_counts = df[["date", "open", "high", "low", "close", "ticker"]].isnull().sum()
    if null_counts.any():
        raise ValueError(f"Null values found in critical columns:\n{null_counts[null_counts > 0]}")

    # Sort by ticker and date for correct chronological processing
    df = df.sort_values(["ticker", "date"]).reset_index(drop=True)

    return df


 
# MONTHLY AGGREGATION (OHLCV)
 

def resample_to_monthly(df: pd.DataFrame) -> pd.DataFrame:
    """Resample daily data to monthly OHLCV for each ticker.
    
    Aggregation logic:
        - Open:   First trading day's opening price of the month
        - High:   Maximum daily high during the month
        - Low:    Minimum daily low during the month
        - Close:  Last trading day's closing price of the month
        - Volume: Sum of daily volume over the month
    
    Args:
        df: Daily stock data sorted by ticker and date.
        
    Returns:
        Monthly OHLCV DataFrame with one row per ticker per month (24 months each).
    """
    monthly_records = []

    for ticker, group in df.groupby("ticker"):
        # Set date as index for resampling; 'MS' = Month Start frequency
        group = group.set_index("date")

        # Use resample with 'MS' (month start) to get calendar month groups
        monthly = group.resample("MS").agg(
            open=("open", "first"),      # First trading day's open
            high=("high", "max"),        # Month's highest high
            low=("low", "min"),          # Month's lowest low
            close=("close", "last"),     # Last trading day's close
            volume=("volume", "sum"),    # Total monthly volume
        )

        monthly["ticker"] = ticker
        monthly_records.append(monthly)

    monthly_df = pd.concat(monthly_records).reset_index()
    monthly_df.rename(columns={"date": "month"}, inplace=True)

    return monthly_df


 
# TECHNICAL INDICATORS
 

def compute_sma(series: pd.Series, window: int) -> pd.Series:
    """Compute Simple Moving Average.
    
    SMA = Sum of closing prices over 'window' periods / window
    
    Args:
        series: Price series (monthly close).
        window: Number of periods for the moving average.
        
    Returns:
        SMA series with NaN for the first (window - 1) periods.
    """
    return series.rolling(window=window, min_periods=window).mean()


def compute_ema(series: pd.Series, span: int) -> pd.Series:
    """Compute Exponential Moving Average.
    
    Uses the standard EMA recursive formula:
        Multiplier = 2 / (span + 1)
        EMA_t = (Price_t - EMA_{t-1}) * Multiplier + EMA_{t-1}
    
    The first EMA value is seeded with the SMA of the first 'span' periods,
    matching the standard financial definition from Investopedia.
    
    Note: We intentionally avoid pandas ewm(adjust=False) here because it
    seeds from the first data point rather than from the SMA, producing
    different values than the standard financial convention requires.
    
    Args:
        series: Price series (monthly close).
        span: Number of periods for the EMA.
        
    Returns:
        EMA series with NaN for the first (span - 1) periods.
    """
    ewm(adjust=False)
    sma_seed = series.iloc[:span].mean()
    multiplier = 2 / (span + 1)
    
    result = pd.Series(index=series.index, dtype="float64")
    result.iloc[:span - 1] = None  # Not enough data
    result.iloc[span - 1] = sma_seed  # Seed with SMA
    
    for i in range(span, len(series)):
        result.iloc[i] = (series.iloc[i] - result.iloc[i - 1]) * multiplier + result.iloc[i - 1]
    
    return result


def compute_bollinger_bands(series: pd.Series, window: int, k: float) -> Dict[str, pd.Series]:
    """Compute Bollinger Bands.
    
    - Middle Band: SMA of closing prices over 'window' periods
    - Upper Band:  Middle Band + k * rolling standard deviation
    - Lower Band:  Middle Band - k * rolling standard deviation
    
    Args:
        series: Price series (monthly close).
        window: Rolling window for mean and std.
        k: Multiplier for standard deviation (typically 2).
        
    Returns:
        Dictionary with 'bb_middle', 'bb_upper', 'bb_lower' Series.
    """
    mid = series.rolling(window=window, min_periods=window).mean()
    sd = series.rolling(window=window, min_periods=window).std()

    return {
        "bb_middle": mid,
        "bb_upper": mid + k * sd,
        "bb_lower": mid - k * sd,
    }


def compute_donchian_channels(high: pd.Series, low: pd.Series, window: int) -> Dict[str, pd.Series]:
    """Compute Donchian Channels.
    
    - Upper Channel: Rolling maximum of high prices over 'window' periods
    - Lower Channel: Rolling minimum of low prices over 'window' periods
    
    Args:
        high: Monthly high price series.
        low: Monthly low price series.
        window: Rolling window period.
        
    Returns:
        Dictionary with 'dc_upper' and 'dc_lower' Series.
    """
    return {
        "dc_upper": high.rolling(window=window, min_periods=window).max(),
        "dc_lower": low.rolling(window=window, min_periods=window).min(),
    }


def compute_zscore(series: pd.Series, window: int) -> pd.Series:
    """Compute Z-Score volatility indicator.
    
    Z-Score = (Current Price - Rolling Mean) / Rolling Std Dev
    
    Measures how many standard deviations the current price is from
    the rolling mean, indicating overbought/oversold conditions.
    
    Args:
        series: Price series (monthly close).
        window: Rolling window for mean and standard deviation.
        
    Returns:
        Z-score series.
    """
    rolling_mean = series.rolling(window=window, min_periods=window).mean()
    rolling_std = series.rolling(window=window, min_periods=window).std()
    return (series - rolling_mean) / rolling_std


def add_technical_indicators(monthly_df: pd.DataFrame) -> pd.DataFrame:
    """Compute and attach all technical indicators per ticker.
    
    All indicators are calculated on monthly closing prices (or monthly
    high/low for Donchian Channels), applied independently per ticker
    to avoid cross-contamination between symbols.
    
    Args:
        monthly_df: Monthly OHLCV data with 'ticker', 'close', 'high', 'low' columns.
        
    Returns:
        DataFrame with additional indicator columns appended.
    """
    result_frames = []

    for ticker, group in monthly_df.groupby("ticker"):
        group = group.sort_values("month").copy()
        close = group["close"]
        high = group["high"]
        low = group["low"]

        # Moving Averages
        group["sma_10"] = compute_sma(close, SMA_SHORT)
        group["sma_20"] = compute_sma(close, SMA_LONG)
        group["ema_10"] = compute_ema(close.reset_index(drop=True), EMA_SHORT).values
        group["ema_20"] = compute_ema(close.reset_index(drop=True), EMA_LONG).values

        # Bollinger Bands
        bb = compute_bollinger_bands(close, BOLLINGER_WINDOW, BOLLINGER_K)
        group["bb_middle"] = bb["bb_middle"].values
        group["bb_upper"] = bb["bb_upper"].values
        group["bb_lower"] = bb["bb_lower"].values

        # Donchian Channels
        dc = compute_donchian_channels(high, low, DONCHIAN_WINDOW)
        group["dc_upper"] = dc["dc_upper"].values
        group["dc_lower"] = dc["dc_lower"].values

        # Z-Score
        group["zscore"] = compute_zscore(close, ZSCORE_WINDOW).values

        result_frames.append(group)

    return pd.concat(result_frames).reset_index(drop=True)


 
# OUTPUT / PARTITIONING
 

def write_partitioned_output(monthly_df: pd.DataFrame, output_dir: str) -> None:
    """Write one CSV file per ticker symbol.
    
    Each file contains exactly 24 rows (one per month) with OHLCV data
    and all technical indicator columns.
    
    File naming convention: result_{SYMBOL}.csv
    
    Args:
        monthly_df: Complete monthly DataFrame with indicators.
        output_dir: Directory to write output files.
    """
    os.makedirs(output_dir, exist_ok=True)

    for ticker, group in monthly_df.groupby("ticker"):
        group = group.sort_values("month").copy()

        # Validate 24 rows per ticker
        assert len(group) == 24, (
            f"Expected 24 rows for {ticker}, got {len(group)}"
        )

        # Format month column as YYYY-MM for cleaner output
        group["month"] = group["month"].dt.strftime("%Y-%m")

        # Drop ticker column from individual files (redundant - it's in the filename)
        output_cols = [col for col in group.columns if col != "ticker"]
        
        filepath = os.path.join(output_dir, f"result_{ticker}.csv")
        group[output_cols].to_csv(filepath, index=False, float_format="%.4f")
        print(f"  [OK] Written: {filepath} ({len(group)} rows)")


 
# MAIN PIPELINE
 

def main():
    """Main pipeline orchestrator: Load → Resample → Compute → Partition."""
    print("=" * 60)
    print("Stock Data Monthly Aggregation Pipeline")
    print("=" * 60)

    # Step 1: Load & validate
    print("\n[1/4] Loading dataset...")
    df = load_data(INPUT_FILE)
    tickers = sorted(df["ticker"].unique())
    print(f"  Loaded {len(df)} rows for {len(tickers)} tickers: {tickers}")
    print(f"  Date range: {df['date'].min().date()} to {df['date'].max().date()}")

    # Step 2: Monthly resampling
    print("\n[2/4] Resampling to monthly frequency...")
    monthly_df = resample_to_monthly(df)
    print(f"  Generated {len(monthly_df)} monthly records "
          f"({len(monthly_df) // len(tickers)} months × {len(tickers)} tickers)")

    # Step 3: Technical indicators
    print("\n[3/4] Computing technical indicators...")
    monthly_df = add_technical_indicators(monthly_df)
    indicator_cols = ["sma_10", "sma_20", "ema_10", "ema_20",
                      "bb_middle", "bb_upper", "bb_lower",
                      "dc_upper", "dc_lower", "zscore"]
    print(f"  Added {len(indicator_cols)} indicator columns: {indicator_cols}")

    # Step 4: Partition & write output
    print(f"\n[4/4] Writing partitioned output to '{OUTPUT_DIR}/'...")
    write_partitioned_output(monthly_df, OUTPUT_DIR)

    print("\n" + "=" * 60)
    print("Pipeline complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
