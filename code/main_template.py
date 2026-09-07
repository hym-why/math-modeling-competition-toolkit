"""
Contest entry template.

Copy this file to code/main.py during the contest, then replace each TODO block.
Keep every exported result stable so the paper and supporting materials match.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from modeling_toolkit import clean_numeric_frame, export_table, load_table, regression_report, topsis_score


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUTPUTS = ROOT / "outputs"


def load_and_clean() -> pd.DataFrame:
    # TODO: replace filename and parsing options according to the contest data.
    raw_path = DATA / "contest_data.csv"
    df = load_table(raw_path)

    # TODO: replace numeric columns with the variables used in the model.
    numeric_columns = [col for col in df.columns if col != "id"]
    return clean_numeric_frame(df, numeric_columns)


def solve_problem_1(df: pd.DataFrame) -> pd.DataFrame:
    # TODO: define positive/negative indicators based on the problem statement.
    positive_cols = []
    negative_cols = []
    scores = topsis_score(df, positive_cols=positive_cols, negative_cols=negative_cols)
    result = pd.concat([df, scores], axis=1).sort_values("rank")
    export_table(result, OUTPUTS / "problem_1_result.csv")
    return result


def solve_problem_2(df: pd.DataFrame) -> pd.DataFrame:
    # TODO: replace with prediction, optimization, clustering, or simulation.
    result = df.copy()
    export_table(result, OUTPUTS / "problem_2_result.csv")
    return result


def validate_model(y_true, y_pred) -> pd.DataFrame:
    report = regression_report(y_true, y_pred)
    result = pd.DataFrame([report.__dict__])
    export_table(result, OUTPUTS / "validation_metrics.csv")
    return result


def main() -> None:
    df = load_and_clean()
    solve_problem_1(df)
    solve_problem_2(df)
    print(f"Finished. Results exported to {OUTPUTS}")


if __name__ == "__main__":
    main()

