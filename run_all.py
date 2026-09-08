import os
import sys
import time
from src import m0_validate, m1_prepare, m2_concentration, m3_bot_dynamics, m4_victims, m5_timeseries, m6_synthesis, m7_reports

def run_pipeline():
    start_time = time.time()
    print("================================================================================")
    print("STARTING SANDWICH-MEV EMPIRICAL ANALYSIS PIPELINE (ETHEREUM 2024–2025)")
    print("================================================================================")
    
    # Ensure directory structure
    for d in ["data", "output/tables", "output/figures", "output/logs", "output/reports"]:
        os.makedirs(d, exist_ok=True)
        
    try:
        print("\n--- [Step 0] Data Loading & Rigorous Validation ---")
        m0_validate.run_validation()
        
        print("\n--- [Step 1] Data Preparation & Table 1 Descriptives ---")
        m1_prepare.prepare_all()
        
        print("\n--- [Step 2] Searcher Concentration Analysis (H1) ---")
        m2_concentration.run_concentration()
        
        print("\n--- [Step 3] Searcher Bot Dynamics & Scaling (H1) ---")
        m3_bot_dynamics.run_bot_dynamics()
        
        print("\n--- [Step 4] Victim-Side Incidence & Inference (H2 & H5) ---")
        m4_victims.run_victims()
        
        print("\n--- [Step 5] Time-Series Analysis & Regime Shifts (H3) ---")
        m5_timeseries.run_timeseries()
        
        print("\n--- [Step 6] Cross-Base Synthesis & Protocol Vulnerability (H4 & H5) ---")
        m6_synthesis.run_synthesis()
        
        print("\n--- [Step 7] Report Generation & Synthesis Documentation ---")
        m7_reports.generate_reports()
        
        elapsed = time.time() - start_time
        print("\n================================================================================")
        print(f"PIPELINE COMPLETED SUCCESSFULLY IN {elapsed:.2f} SECONDS.")
        print("All tables, figures, and reports have been generated in ./output/")
        print("================================================================================")
        sys.exit(0)
        
    except Exception as e:
        print("\n[CRITICAL ERROR] Pipeline execution failed:", str(e))
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    run_pipeline()
