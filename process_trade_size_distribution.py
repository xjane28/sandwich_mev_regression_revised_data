#!/usr/bin/env python3
"""Process victim impact data to generate trade size distribution violin plot data."""

import pandas as pd
import numpy as np
import sys

def gaussian_kde_simple(data, eval_points, bandwidth=None):
    """Simple KDE implementation using numpy."""
    data = np.array(data)
    eval_points = np.array(eval_points)
    
    # Silverman's rule of thumb for bandwidth
    if bandwidth is None:
        n = len(data)
        std = np.std(data)
        bandwidth = 1.06 * std * (n ** (-1.0/5.0))
    
    # Evaluate KDE at each point
    kde_values = np.zeros(len(eval_points))
    for i, point in enumerate(eval_points):
        # Gaussian kernel
        kde_values[i] = np.mean(np.exp(-0.5 * ((data - point) / bandwidth) ** 2)) / (bandwidth * np.sqrt(2 * np.pi))
    
    return kde_values

def process_trade_size_distribution(input_file, output_file):
    """Read victim impact CSV and generate violin plot data."""
    
    # Read the CSV
    df = pd.read_csv(input_file)
    
    # Ensure tiers are in the correct order
    tier_order = ['Retail', 'Small', 'Institutional']
    df['tier_index'] = df['victim_tier'].map({tier: i for i, tier in enumerate(tier_order)})
    df = df.sort_values('tier_index').reset_index(drop=True)
    
    # Calculate global min and max for y-axis range
    global_min = df['min_tx'].min()
    global_max = df['max_tx'].max()
    
    # Add 10% padding on log scale
    log_min = np.log10(global_min)
    log_max = np.log10(global_max)
    log_range = log_max - log_min
    log_min_padded = log_min - 0.1 * log_range
    log_max_padded = log_max + 0.1 * log_range
    ymin = 10 ** log_min_padded
    ymax = 10 ** log_max_padded
    
    # Generate violin data for each tier
    all_violin_data = []
    stats_data = []
    
    n_samples = 10000
    n_points = 200  # Number of points for KDE curve
    
    for idx, row in df.iterrows():
        tier = row['victim_tier']
        avg_tx = row['avg_tx_size']
        min_tx = row['min_tx']
        max_tx = row['max_tx']
        
        # Estimate log-normal parameters
        # Mean of log-normal = exp(mu + sigma^2/2) = avg_tx
        # We'll estimate sigma from the spread
        if min_tx > 0:
            spread_ratio = max_tx / min_tx
            log_spread = np.log(spread_ratio)
            # Use sigma in range 0.7-1.0 as suggested
            sigma = min(max(0.7, log_spread / 6), 1.0)
        else:
            sigma = 0.8  # Default
        
        # Calculate mu such that exp(mu + sigma^2/2) = avg_tx
        mu = np.log(avg_tx) - (sigma**2) / 2
        
        # Generate synthetic samples from log-normal distribution
        samples = np.random.lognormal(mean=mu, sigma=sigma, size=n_samples)
        
        # Clip samples to [min_tx, max_tx]
        samples = np.clip(samples, min_tx, max_tx)
        
        # Calculate statistics
        median = np.median(samples)
        q25 = np.percentile(samples, 25)
        q75 = np.percentile(samples, 75)
        mean = np.mean(samples)  # Should be close to avg_tx
        
        # Generate KDE for violin shape
        # Use log scale for better distribution
        log_samples = np.log10(samples)
        
        # Create evaluation points
        log_eval_min = np.log10(min_tx)
        log_eval_max = np.log10(max_tx)
        log_eval_points = np.linspace(log_eval_min, log_eval_max, n_points)
        
        # Evaluate KDE
        kde_values = gaussian_kde_simple(log_samples, log_eval_points)
        
        # Normalize KDE to create violin width (scale to reasonable width)
        # Violin width should be proportional to density
        max_density = kde_values.max()
        # Scale so max width is about 0.3 units (for x-axis spacing of 1.0)
        width_scale = 0.3 / max_density
        violin_widths = kde_values * width_scale
        
        # Create left and right sides of violin
        # X position: 1, 2, 3 for Retail, Small, Institutional
        x_pos = idx + 1
        
        # Generate violin outline as closed path
        # Left side: from bottom to top
        violin_coords = []
        for i, (log_val, width) in enumerate(zip(log_eval_points, violin_widths)):
            y_val = 10 ** log_val
            x_left = x_pos - width
            violin_coords.append((x_left, y_val))
        
        # Right side: from top to bottom (reverse order)
        for i in range(len(log_eval_points) - 1, -1, -1):
            log_val = log_eval_points[i]
            width = violin_widths[i]
            y_val = 10 ** log_val
            x_right = x_pos + width
            violin_coords.append((x_right, y_val))
        
        # Close the path by adding first point again
        violin_coords.append(violin_coords[0])
        
        # Write to separate file for each tier
        tier_file = output_file.replace('.csv', f'_{tier.lower()}.csv')
        with open(tier_file, 'w') as f:
            f.write('x,y\n')
            for x, y in violin_coords:
                f.write(f'{x},{y}\n')
        
        # Store statistics
        stats_data.append({
            'tier': tier,
            'tier_index': idx,
            'x_pos': x_pos,
            'avg_tx_size': avg_tx,
            'min_tx': min_tx,
            'max_tx': max_tx,
            'median': median,
            'q25': q25,
            'q75': q75,
            'mean': mean,
            'max_density': max_density,
            'max_width': violin_widths.max()
        })
    
    # Write statistics to file
    stats_df = pd.DataFrame(stats_data)
    stats_file = output_file.replace('.csv', '_stats.csv')
    stats_df.to_csv(stats_file, index=False)
    
    # Print summary
    print(f"Y-axis range: {ymin:.2e} to {ymax:.2e}", file=sys.stderr)
    ratio = stats_df.iloc[2]['avg_tx_size'] / stats_df.iloc[0]['avg_tx_size']
    print(f"Ratio (Institutional/Retail): {ratio:.1f}x", file=sys.stderr)
    for _, row in stats_df.iterrows():
        print(f"{row['tier']}: μ=${row['avg_tx_size']:.2f}, median=${row['median']:.2f}", file=sys.stderr)
    
    return ymin, ymax, stats_df

if __name__ == "__main__":
    input_file = "fetch/query5b_victim_impact.csv"
    output_file = "trade_size_distribution_data.csv"
    ymin, ymax, stats = process_trade_size_distribution(input_file, output_file)
    print(f"\nProcessed data written to {output_file}")
    print(f"Y-axis range: {ymin:.2e} to {ymax:.2e}")
