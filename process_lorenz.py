#!/usr/bin/env python3
"""Process bot distribution data to generate Lorenz curve coordinates."""

import csv
import sys

def process_lorenz_data(input_file, output_file):
    """Read bot distribution CSV and output cumulative percentages for Lorenz curve."""
    volumes = []
    
    # Read volumes from CSV
    with open(input_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            volume = float(row['total_volume_usd']) if row['total_volume_usd'] else 0.0
            volumes.append(volume)
    
    # Sort in descending order (already sorted, but ensure)
    volumes.sort(reverse=True)
    
    # Calculate totals
    total_volume = sum(volumes)
    total_bots = len(volumes)
    
    # Calculate cumulative percentages
    cumulative_volume = 0
    cumulative_bots = 0
    
    results = []
    
    # Add starting point (0, 0)
    results.append((0.0, 0.0))
    
    for i, volume in enumerate(volumes):
        cumulative_volume += volume
        cumulative_bots += 1
        
        pct_bots = (cumulative_bots / total_bots) * 100
        pct_volume = (cumulative_volume / total_volume) * 100
        
        results.append((pct_bots, pct_volume))
    
    # Add ending point (100, 100) if not already there
    if results[-1][0] < 100.0:
        results.append((100.0, 100.0))
    
    # Write to output file in format suitable for pgfplots
    with open(output_file, 'w') as f:
        f.write("cumulative_pct_bots,cumulative_pct_volume\n")
        for pct_bots, pct_volume in results:
            f.write(f"{pct_bots},{pct_volume}\n")
    
    # Calculate Gini coefficient
    # Gini = 1 - 2 * area_under_lorenz
    # We'll approximate using trapezoidal rule
    area_under_lorenz = 0
    for i in range(len(results) - 1):
        x1, y1 = results[i]
        x2, y2 = results[i + 1]
        # Convert percentages to proportions
        area_under_lorenz += ((x2 - x1) / 100.0) * ((y1 + y2) / 2.0) / 100.0
    
    gini = 1 - 2 * area_under_lorenz
    print(f"Gini coefficient: {gini:.6f}", file=sys.stderr)
    
    return gini

if __name__ == "__main__":
    input_file = "fetch/query3_full_bot_distribution.csv"
    output_file = "lorenz_data.csv"
    process_lorenz_data(input_file, output_file)
