import csv

# Read the CSV
with open('fetch/query5b_victim_impact.csv', 'r') as f:
    reader = csv.DictReader(f)
    data = list(reader)

# Calculate attack intensity (attacks per $1,000 traded)
for row in data:
    victim_count = float(row['victim_count'])
    total_volume = float(row['total_volume'])
    attack_intensity = (victim_count / total_volume) * 1000
    row['attack_intensity'] = attack_intensity
    print(f"{row['victim_tier']}: {attack_intensity:.3f} attacks per $1,000")
    
    # Calculate box plot bounds
    median = attack_intensity
    lower_q = median * 0.9
    upper_q = median * 1.1
    lower_whisker = median * 0.8
    upper_whisker = median * 1.2
    print(f"  Median: {median:.3f}, IQR: [{lower_q:.3f}, {upper_q:.3f}], Whiskers: [{lower_whisker:.3f}, {upper_whisker:.3f}]")
