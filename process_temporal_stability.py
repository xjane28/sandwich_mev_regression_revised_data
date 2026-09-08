#!/usr/bin/env python3
"""Process MEV volume data to generate temporal stability figure data."""

import csv
import pandas as pd
import numpy as np
from datetime import datetime

def process_temporal_stability_data(input_file, output_file):
    """Read daily MEV volume CSV and output processed data for temporal stability figure."""
    
    # Read the CSV
    df = pd.read_csv(input_file)
    
    # Parse dates
    df['date'] = pd.to_datetime(df['date'])
    
    # Convert volume to millions of USD
    df['volume_millions'] = df['total_sandwich_volume_usd'] / 1_000_000
    
    # Sort by date to ensure proper ordering
    df = df.sort_values('date').reset_index(drop=True)
    
    # Calculate 7-day moving average
    df['ma7'] = df['volume_millions'].rolling(window=7, center=True, min_periods=1).mean()
    
    # Calculate 95% confidence band using rolling standard error
    # Using 7-day rolling window for consistency
    rolling_std = df['volume_millions'].rolling(window=7, center=True, min_periods=1).std()
    # 95% CI: mean ± 1.96 * std
    df['ci_upper'] = df['ma7'] + 1.96 * rolling_std
    df['ci_lower'] = df['ma7'] - 1.96 * rolling_std
    
    # Ensure CI bounds are positive and above ymin for log scale (ymin=10)
    # Clip to 10 to match the graph's ymin on log scale
    df['ci_lower'] = df['ci_lower'].clip(lower=10.0)
    
    # Calculate statistics for annotations
    mean_daily_volume = df['volume_millions'].mean()
    total_volume = df['total_sandwich_volume_usd'].sum() / 1_000_000_000  # Billions
    
    # Convert dates to numeric format for pgfplots (days since 2024-01-01)
    # Handle timezone-aware dates
    if df['date'].dt.tz is not None:
        base_date = pd.Timestamp('2024-01-01', tz='UTC')
    else:
        base_date = pd.Timestamp('2024-01-01')
    df['days_since_start'] = (df['date'] - base_date).dt.days
    
    # Write processed data to CSV
    output_df = df[['days_since_start', 'volume_millions', 'ma7', 'ci_upper', 'ci_lower']].copy()
    output_df.to_csv(output_file, index=False)
    
    # Print statistics
    print(f"Mean daily volume: ${mean_daily_volume:.1f}M/day", file=sys.stderr)
    print(f"Total volume: ${total_volume:.1f}B over 2 years", file=sys.stderr)
    print(f"Date range: {df['date'].min()} to {df['date'].max()}", file=sys.stderr)
    
    return mean_daily_volume, total_volume

if __name__ == "__main__":
    import sys
    input_file = "fetch/query1_mev_volume.csv"
    output_file = "temporal_stability_data.csv"
    mean_vol, total_vol = process_temporal_stability_data(input_file, output_file)
    print(f"\nProcessed data written to {output_file}")
    print(f"Use mean_vol={mean_vol:.1f} and total_vol={total_vol:.1f} in LaTeX annotations")
