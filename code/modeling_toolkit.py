"""
Reusable helpers for CUMCM-style data, evaluation, prediction, and sensitivity work.

The functions are intentionally small and explicit so a team can copy them into a
contest solution and explain every step in the paper.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence

import re

import numpy as np
import pandas as pd


def ensure_dir(path: str | Path) -> Path:
    target = Path(path)
    target.mkdir(parents=True, exist_ok=True)
    return target


def load_table(path: str | Path, **kwargs) -> pd.DataFrame:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path, **kwargs)
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path, **kwargs)
    if suffix in {".tsv", ".txt"}:
        return pd.read_csv(path, sep="\t", **kwargs)
    raise ValueError(f"Unsupported table format: {path.suffix}")


def clean_numeric_frame(df: pd.DataFrame, columns: Sequence[str] | None = None) -> pd.DataFrame:
    result = df.copy()
    target_columns = list(columns) if columns is not None else list(result.columns)
    for col in target_columns:
        result[col] = pd.to_numeric(result[col], errors="coerce")
        median = result[col].median()
        if pd.isna(median):
            median = 0.0
        result[col] = result[col].fillna(median)
    return result


def minmax_scale(
    df: pd.DataFrame,
    positive_cols: Iterable[str],
    negative_cols: Iterable[str] = (),
    eps: float = 1e-12,
) -> pd.DataFrame:
    result = pd.DataFrame(index=df.index)
    for col in positive_cols:
        x = df[col].astype(float)
        result[col] = (x - x.min()) / (x.max() - x.min() + eps)
    for col in negative_cols:
        x = df[col].astype(float)
        result[col] = (x.max() - x) / (x.max() - x.min() + eps)
    return result


def entropy_weights(scaled: pd.DataFrame, eps: float = 1e-12) -> pd.Series:
    x = scaled.clip(lower=0).astype(float)
    p = x.div(x.sum(axis=0) + eps, axis=1)
    entropy = -(p * np.log(p + eps)).sum(axis=0) / np.log(len(x) + eps)
    diversity = 1 - entropy
    weights = diversity / (diversity.sum() + eps)
    return weights.rename("weight")


def valid_composition_mask(
    df: pd.DataFrame,
    lower: float = 85.0,
    upper: float = 105.0,
) -> pd.Series:
    """Return rows whose detected component total is within the stated range."""
    totals = df.apply(pd.to_numeric, errors="coerce").fillna(0.0).sum(axis=1)
    return totals.between(lower, upper, inclusive="both")


def closure_transform(df: pd.DataFrame, zero_replacement: float = 1e-6) -> pd.DataFrame:
    """Map non-negative component data to the simplex after zero replacement."""
    if zero_replacement <= 0:
        raise ValueError("zero_replacement must be positive")
    numeric = df.apply(pd.to_numeric, errors="coerce").fillna(0.0).astype(float)
    if (numeric < 0).any().any():
        raise ValueError("compositions cannot contain negative values")
    replaced = numeric.mask(numeric <= 0, zero_replacement)
    totals = replaced.sum(axis=1)
    if (totals <= 0).any():
        raise ValueError("composition rows must have positive totals")
    return replaced.div(totals, axis=0)


def clr_transform(df: pd.DataFrame, zero_replacement: float = 1e-6) -> pd.DataFrame:
    """Apply a centered log-ratio transform to compositional rows."""
    closed = closure_transform(df, zero_replacement=zero_replacement)
    logged = np.log(closed)
    return logged.sub(logged.mean(axis=1), axis=0)


def topsis_score(
    df: pd.DataFrame,
    positive_cols: Sequence[str],
    negative_cols: Sequence[str] = (),
    weights: pd.Series | None = None,
    eps: float = 1e-12,
) -> pd.DataFrame:
    scaled = minmax_scale(df, positive_cols, negative_cols)
    if weights is None:
        weights = entropy_weights(scaled)
    weights = weights.reindex(scaled.columns).fillna(0)
    weighted = scaled * weights
    ideal_best = weighted.max(axis=0)
    ideal_worst = weighted.min(axis=0)
    d_best = np.sqrt(((weighted - ideal_best) ** 2).sum(axis=1))
    d_worst = np.sqrt(((weighted - ideal_worst) ** 2).sum(axis=1))
    score = d_worst / (d_best + d_worst + eps)
    return pd.DataFrame({"score": score, "rank": score.rank(ascending=False, method="min").astype(int)})


def ahp_weights(matrix: Sequence[Sequence[float]]) -> np.ndarray:
    a = np.asarray(matrix, dtype=float)
    eigvals, eigvecs = np.linalg.eig(a)
    idx = np.argmax(eigvals.real)
    weights = np.abs(eigvecs[:, idx].real)
    return weights / weights.sum()


@dataclass
class RegressionReport:
    mae: float
    rmse: float
    mape: float
    r2: float


def regression_report(y_true: Sequence[float], y_pred: Sequence[float], eps: float = 1e-12) -> RegressionReport:
    y_true_arr = np.asarray(y_true, dtype=float)
    y_pred_arr = np.asarray(y_pred, dtype=float)
    residual = y_true_arr - y_pred_arr
    mae = float(np.mean(np.abs(residual)))
    rmse = float(np.sqrt(np.mean(residual**2)))
    mape = float(np.mean(np.abs(residual) / (np.abs(y_true_arr) + eps)))
    ss_res = float(np.sum(residual**2))
    ss_tot = float(np.sum((y_true_arr - np.mean(y_true_arr)) ** 2))
    r2 = 1 - ss_res / (ss_tot + eps)
    return RegressionReport(mae=mae, rmse=rmse, mape=mape, r2=r2)


def sensitivity_one_at_a_time(
    base_params: dict[str, float],
    evaluator: Callable[[dict[str, float]], float],
    ratios: Sequence[float] = (0.8, 0.9, 1.0, 1.1, 1.2),
) -> pd.DataFrame:
    rows: list[dict[str, float | str]] = []
    for name, value in base_params.items():
        for ratio in ratios:
            params = dict(base_params)
            params[name] = value * ratio
            rows.append({"parameter": name, "ratio": ratio, "value": params[name], "score": evaluator(params)})
    return pd.DataFrame(rows)


def monte_carlo(
    sampler: Callable[[np.random.Generator], dict[str, float]],
    evaluator: Callable[[dict[str, float]], float],
    n: int = 1000,
    seed: int = 2026,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        params = sampler(rng)
        rows.append({"trial": i, **params, "score": evaluator(params)})
    return pd.DataFrame(rows)


def empirical_cvar(losses: Sequence[float], alpha: float = 0.95) -> float:
    """Return mean loss in the worst (1-alpha) empirical tail."""
    values = np.asarray(losses, dtype=float)
    if values.size == 0:
        raise ValueError("losses cannot be empty")
    if not 0 <= alpha < 1:
        raise ValueError("alpha must be in [0, 1)")
    threshold = np.quantile(values, alpha, method="higher")
    return float(values[values >= threshold].mean())


def gestational_week(value: object) -> float:
    """Parse values such as '12w+3' into fractional weeks."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return float("nan")
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"(\d+(?:\.\d+)?)\s*[wW周](?:\s*\+\s*(\d+))?", str(value))
    if not match:
        return float("nan")
    weeks = float(match.group(1))
    days = float(match.group(2) or 0)
    return weeks + days / 7.0


def export_table(df: pd.DataFrame, path: str | Path, index: bool = False) -> Path:
    path = Path(path)
    ensure_dir(path.parent)
    df.to_csv(path, index=index, encoding="utf-8-sig")
    return path
