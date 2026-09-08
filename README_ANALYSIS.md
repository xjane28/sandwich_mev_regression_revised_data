# Journal-Grade Statistical Analysis of the Sandwich-MEV Dataset (Ethereum 2024–2025)

This repository contains the complete, offline empirical-finance analysis suite for studying the distributional incidence of sandwich attacks on Ethereum during 2024–2025.

## Quickstart

### 1. Environment Setup
To ensure strict reproducibility and isolate dependencies, create and activate a Python virtual environment and install the pinned dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Run All Analysis Modules
Execute the full end-to-end analysis pipeline. This will load the raw CSV data from `./fetch/` (copying to `./data/` for clean checkouts), validate schemas and identities, run all statistical regressions, bootstraps, and permutations, and generate all tables, figures, and reports under `./output/`:

```bash
python src/run_all.py
```

### 3. Verify Acceptance Checks
Run the automated standalone self-check suite to verify that every numerical ground-truth anchor, tolerance, schema identity, LaTeX booktabs format, and figure resolution requirement is met:

```bash
python src/acceptance_checks.py
```

## Directory Structure
- `fetch/` / `data/`: Read-only input directory containing the six pre-aggregated Dune Analytics CSVs.
- `src/`: Core Python modules (`m0_validate.py` through `m7_reports.py`), `run_all.py`, and `acceptance_checks.py`.
- `output/tables/`: Generated CSV and LaTeX tables (`.csv` and `.tex` with booktabs, captions, labels, and table notes).
- `output/figures/`: Generated vector PDF and high-resolution PNG (300 DPI) figures.
- `output/reports/`: Markdown reports including `validation_report.md`, `results_summary.md`, `referee_gap_analysis.md`, and `MANIFEST.md`.
- `output/logs/`: Detailed execution log (`run_log.txt`).
