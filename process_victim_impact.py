import csv

# Read the CSV
with open('fetch/query5b_victim_impact.csv', 'r') as f:
    reader = csv.DictReader(f)
    data = list(reader)

# Calculate metrics
for row in data:
    victim_count = float(row['victim_count'])
    unique_victims = float(row['unique_victims'])
    avg_tx_size = float(row['avg_tx_size'])
    
    # Panel A: Attack Frequency
    attacks_per_victim = victim_count / unique_victims
    row['attacks_per_victim'] = attacks_per_victim
    
    # Panel B: Absolute Loss per Attack (1% MEV)
    absolute_loss = avg_tx_size * 0.01
    row['absolute_loss'] = absolute_loss
    
    # Panel C: Cumulative Loss Rate
    cumulative_loss_rate = attacks_per_victim * 1.0
    row['cumulative_loss_rate'] = cumulative_loss_rate
    
    print(f"{row['victim_tier']}: attacks={attacks_per_victim:.2f}, loss=${absolute_loss:.2f}, rate={cumulative_loss_rate:.2f}%")

# Calculate mean for Panel A
mean_attacks = sum(float(r['attacks_per_victim']) for r in data) / len(data)
print(f"\nMean attacks per victim: {mean_attacks:.2f}")

# Calculate ratio for Panel B
retail_loss = float(data[0]['absolute_loss'])
inst_loss = float(data[2]['absolute_loss'])
ratio = inst_loss / retail_loss
print(f"Institutional/Retail ratio: {ratio:.1f}x")

# Find which tier has highest cumulative loss rate
max_rate = max(float(r['cumulative_loss_rate']) for r in data)
max_tier = [r for r in data if float(r['cumulative_loss_rate']) == max_rate][0]
print(f"\nHighest cumulative loss rate: {max_tier['victim_tier']} at {max_rate:.2f}%")
