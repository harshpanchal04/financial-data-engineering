"""Validation script - cross-checks pipeline output against manually computed values."""
import pandas as pd

# Load raw data
raw = pd.read_csv('output_file.csv', parse_dates=['date']).sort_values(['ticker', 'date'])

# Load pipeline output
aapl_out = pd.read_csv('output/result_AAPL.csv')

# ---- OHLC Validation for AAPL Jan 2018 ----
aapl_jan = raw[(raw['ticker'] == 'AAPL') & (raw['date'].dt.year == 2018) & (raw['date'].dt.month == 1)].sort_values('date')
print("=== OHLC Validation: AAPL Jan 2018 ===")
print(f"  Expected Open (first day):  {aapl_jan.iloc[0]['open']:.4f}")
print(f"  Pipeline Open:              {aapl_out.iloc[0]['open']:.4f}")
print(f"  Match: {abs(aapl_jan.iloc[0]['open'] - aapl_out.iloc[0]['open']) < 0.01}")
print()
print(f"  Expected Close (last day):  {aapl_jan.iloc[-1]['close']:.4f}")
print(f"  Pipeline Close:             {aapl_out.iloc[0]['close']:.4f}")
print(f"  Match: {abs(aapl_jan.iloc[-1]['close'] - aapl_out.iloc[0]['close']) < 0.01}")
print()
print(f"  Expected High (max):        {aapl_jan['high'].max():.4f}")
print(f"  Pipeline High:              {aapl_out.iloc[0]['high']:.4f}")
print(f"  Match: {abs(aapl_jan['high'].max() - aapl_out.iloc[0]['high']) < 0.01}")
print()
print(f"  Expected Low (min):         {aapl_jan['low'].min():.4f}")
print(f"  Pipeline Low:               {aapl_out.iloc[0]['low']:.4f}")
print(f"  Match: {abs(aapl_jan['low'].min() - aapl_out.iloc[0]['low']) < 0.01}")

# ---- SMA Validation ----
print("\n=== SMA-10 Validation: AAPL (month 10 = Oct 2018) ===")
closes_1_to_10 = aapl_out['close'].iloc[0:10]
manual_sma10 = closes_1_to_10.mean()
print(f"  Manual SMA-10: {manual_sma10:.4f}")
print(f"  Pipeline SMA-10: {aapl_out.iloc[9]['sma_10']:.4f}")
print(f"  Match: {abs(manual_sma10 - aapl_out.iloc[9]['sma_10']) < 0.01}")

# ---- EMA Validation ----
print("\n=== EMA-10 Validation: AAPL ===")
closes = aapl_out['close'].tolist()
# Seed: SMA of first 10 closes
ema_seed = sum(closes[:10]) / 10
multiplier = 2 / (10 + 1)
ema_values = [None] * 9 + [ema_seed]
for i in range(10, 24):
    ema_values.append((closes[i] - ema_values[-1]) * multiplier + ema_values[-1])

print(f"  Seed (SMA of first 10): {ema_seed:.4f}")
print(f"  Pipeline EMA-10 @month10: {aapl_out.iloc[9]['ema_10']:.4f}")
print(f"  Match seed: {abs(ema_seed - aapl_out.iloc[9]['ema_10']) < 0.01}")

for i in [10, 15, 23]:
    print(f"  Manual EMA-10 @{i}: {ema_values[i]:.4f}, Pipeline: {aapl_out.iloc[i]['ema_10']:.4f}, Match: {abs(ema_values[i] - aapl_out.iloc[i]['ema_10']) < 0.01}")

# ---- Row Count Validation ----
print("\n=== Row Count Validation ===")
import os
all_ok = True
for f in sorted(os.listdir('output')):
    if f.startswith('result_') and f.endswith('.csv'):
        df = pd.read_csv(f'output/{f}')
        ok = len(df) == 24
        if not ok:
            all_ok = False
        print(f"  {f}: {len(df)} rows {'OK' if ok else 'FAIL'}")
print(f"\n  All files have 24 rows: {all_ok}")

# ---- Bollinger Band Validation ----
print("\n=== Bollinger Band Validation: AAPL @ month 20 (Aug 2019) ===")
closes_series = pd.Series(closes)
window = 20
idx = 19  # 0-indexed, month 20
rolling_mean = closes_series.iloc[idx-window+1:idx+1].mean()
rolling_std = closes_series.iloc[idx-window+1:idx+1].std()
print(f"  Manual BB Mid: {rolling_mean:.4f}, Pipeline: {aapl_out.iloc[idx]['bb_middle']:.4f}")
print(f"  Manual BB Upper: {rolling_mean + 2*rolling_std:.4f}, Pipeline: {aapl_out.iloc[idx]['bb_upper']:.4f}")
print(f"  Manual BB Lower: {rolling_mean - 2*rolling_std:.4f}, Pipeline: {aapl_out.iloc[idx]['bb_lower']:.4f}")
