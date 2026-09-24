import os
import sys
import time

from src import (
    m0_validate,
    m1_prepare,
    m2_concentration,
    m3_bot_dynamics,
    m4_victims,
    m5_timeseries,
    m6_synthesis,
    m7_reports,
    m8_h1_test,
    m9a_h2_test,
    m9b_h2_test,
    m10_h3_test,
    m11_h4_test,
)


def run_pipeline():
    start_time = time.time()

    print("=" * 80)
    print("STARTING SANDWICH-MEV EMPIRICAL ANALYSIS PIPELINE")
    print("=" * 80)

    # Ensure directory structure exists.
    for d in [
        "data",
        "output/tables",
        "output/figures",
        "output/logs",
        "output/reports",
    ]:
        os.makedirs(d, exist_ok=True)

    try:
        # ------------------------------------------------------------------
        # Core analysis pipeline
        # ------------------------------------------------------------------

        print("\n--- [Step 0] Data Loading & Rigorous Validation ---")
        m0_validate.run_validation()

        print("\n--- [Step 1] Data Preparation & Table 1 Descriptives ---")
        m1_prepare.prepare_all()

        print("\n--- [Step 2] Searcher Concentration Analysis ---")
        m2_concentration.run_concentration()

        print("\n--- [Step 3] Searcher Bot Dynamics & Scaling ---")
        m3_bot_dynamics.run_bot_dynamics()

        print("\n--- [Step 4] Victim-Side Incidence & Inference ---")
        m4_victims.run_victims()

        print("\n--- [Step 5] Time-Series Analysis & Regime Shifts ---")
        m5_timeseries.run_timeseries()

        print("\n--- [Step 6] Cross-Base Synthesis & Protocol Analysis ---")
        m6_synthesis.run_synthesis()

        print("\n--- [Step 7] Report Generation & Synthesis Documentation ---")
        m7_reports.generate_reports()

        print("\n--- [Step 8] H1 Hypothesis Tests ---")
        m8_h1_test.run_h1_tests()

        print("\n--- [Step 9a] H2 Conservative / Assumption-Light Analysis ---")
        m9a_h2_test.main([])

        print("\n--- [Step 9b] H2 Grouped-Binomial Regression Analysis ---")
        m9b_h2_test.main()

        print("\n--- [Step 10] H3 Persistence & Temporal Evolution Tests ---")
        m10_h3_test.run_h3_tests()

        print("\n--- [Step 11] H4 Protocol-Level Analysis ---")
        m11_h4_test.run_all_h4_tests()

        elapsed = time.time() - start_time

        print("\n" + "=" * 80)
        print(f"PIPELINE COMPLETED SUCCESSFULLY IN {elapsed:.2f} SECONDS.")
        print("All requested analysis stages completed.")
        print("Check ./output/ for generated tables, figures, and reports.")
        print("=" * 80)

        return 0

    except Exception as e:
        print("\n" + "=" * 80)
        print("[CRITICAL ERROR] Pipeline execution failed:")
        print(str(e))
        print("=" * 80)

        import traceback
        traceback.print_exc()

        return 1


if __name__ == "__main__":
    sys.exit(run_pipeline())
