"""
Example pipeline for a CUMCM-style evaluation problem.

Run from the repository root:
    python code/example_pipeline.py

It creates synthetic data, evaluates alternatives with entropy-weight TOPSIS,
exports tables, and produces one sensitivity table. Replace the synthetic data
block with the contest dataset during the real contest.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from modeling_toolkit import export_table, sensitivity_one_at_a_time, topsis_score


ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def build_demo_data() -> pd.DataFrame:
    seed = int(os.environ.get("MATH_MODEL_SEED", "2026"))
    rng = np.random.default_rng(seed)
    return pd.DataFrame(
        {
            "方案": [f"S{i:02d}" for i in range(1, 13)],
            "收益": rng.normal(80, 10, 12).round(2),
            "稳定性": rng.normal(70, 8, 12).round(2),
            "成本": rng.normal(35, 6, 12).round(2),
            "风险": rng.normal(20, 5, 12).round(2),
        }
    )


def weighted_score(params: dict[str, float]) -> float:
    return 0.45 * params["收益"] + 0.35 * params["稳定性"] - 0.12 * params["成本"] - 0.08 * params["风险"]


def main() -> None:
    data = build_demo_data()
    result = topsis_score(data, positive_cols=["收益", "稳定性"], negative_cols=["成本", "风险"])
    ranked = pd.concat([data, result], axis=1).sort_values("rank")

    export_table(data, OUTPUTS / "demo_raw_data.csv")
    export_table(ranked, OUTPUTS / "demo_topsis_result.csv")

    best = ranked.iloc[0]
    base_params = {
        "收益": float(best["收益"]),
        "稳定性": float(best["稳定性"]),
        "成本": float(best["成本"]),
        "风险": float(best["风险"]),
    }
    sensitivity = sensitivity_one_at_a_time(base_params, weighted_score)
    export_table(sensitivity, OUTPUTS / "demo_sensitivity.csv")

    print("Top alternatives:")
    print(ranked[["方案", "score", "rank"]].head(5).to_string(index=False))
    print(f"\nExported results to: {OUTPUTS}")


if __name__ == "__main__":
    main()
