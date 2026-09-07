"""Run narrow baseline-vs-candidate diagnostics on five official C problems.

These diagnostics test model families and validation discipline. They are not
intended to be complete contest solutions.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.optimize import linprog
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    balanced_accuracy_score,
    f1_score,
    mean_absolute_error,
    r2_score,
)
from sklearn.model_selection import GroupKFold, StratifiedGroupKFold, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from modeling_toolkit import clr_transform, gestational_week, valid_composition_mask  # noqa: E402


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

RAW = ROOT / "benchmarks" / "raw" / "official"
DEFAULT_OUTPUT = ROOT / "benchmarks" / "runs" / "model_comparison.json"


def percentile_score(series: pd.Series, higher_is_better: bool = True) -> pd.Series:
    return series.rank(pct=True, ascending=higher_is_better)


def supplier_scores(order: pd.DataFrame, supply: pd.DataFrame) -> pd.DataFrame:
    order_values = order.iloc[:, 2:].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    supply_values = supply.iloc[:, 2:].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    factors = order.iloc[:, 1].map({"A": 1 / 0.6, "B": 1 / 0.66, "C": 1 / 0.72}).astype(float)
    ordered = order_values.sum(axis=1)
    shortage = (order_values - supply_values).clip(lower=0).sum(axis=1)
    active = (supply_values > 0).sum(axis=1)
    active_supply = supply_values.where(supply_values > 0)
    features = pd.DataFrame(
        {
            "supplier": order.iloc[:, 0].astype(str),
            "production_equivalent": supply_values.sum(axis=1) * factors,
            "active_weeks": active,
            "shortage_rate": shortage / ordered.replace(0, np.nan),
            "q10_active_supply": active_supply.quantile(0.10, axis=1).fillna(0.0) * factors,
        }
    ).fillna({"shortage_rate": 1.0})
    features["baseline_score"] = features["production_equivalent"]
    features["robust_score"] = (
        0.40 * percentile_score(features["production_equivalent"])
        + 0.20 * percentile_score(features["active_weeks"])
        + 0.25 * percentile_score(features["shortage_rate"], higher_is_better=False)
        + 0.15 * percentile_score(features["q10_active_supply"])
    )
    return features


def benchmark_2021() -> dict[str, Any]:
    path = RAW / "2021" / "C" / "附件1 近5年402家供应商的相关数据.xlsx"
    order = pd.read_excel(path, sheet_name=0)
    supply = pd.read_excel(path, sheet_name=1)
    scores = supplier_scores(order, supply)
    baseline = scores.nlargest(50, "baseline_score")
    robust = scores.nlargest(50, "robust_score")
    rng = np.random.default_rng(2026)
    week_indices = np.arange(2, order.shape[1])
    reference = set(robust["supplier"])
    jaccards: list[float] = []
    for _ in range(60):
        sampled = rng.choice(week_indices, size=len(week_indices), replace=True)
        sampled_order = pd.concat([order.iloc[:, :2], order.iloc[:, sampled]], axis=1)
        sampled_supply = pd.concat([supply.iloc[:, :2], supply.iloc[:, sampled]], axis=1)
        chosen = set(supplier_scores(sampled_order, sampled_supply).nlargest(50, "robust_score")["supplier"])
        jaccards.append(len(reference & chosen) / len(reference | chosen))
    return {
        "case": "2021C",
        "task": "supplier ranking",
        "baseline": {
            "method": "total production-equivalent supply",
            "selected_shortage_rate": float(baseline["shortage_rate"].mean()),
            "selected_active_weeks": float(baseline["active_weeks"].mean()),
        },
        "candidate": {
            "method": "domain-weighted downside reliability score",
            "selected_shortage_rate": float(robust["shortage_rate"].mean()),
            "selected_active_weeks": float(robust["active_weeks"].mean()),
            "bootstrap_top50_jaccard": float(np.mean(jaccards)),
        },
        "selection": "domain-weighted downside reliability score",
        "guardrail": "Ranking is only a screening stage; ordering and transport still require constrained optimization.",
    }


def artifact_id(value: object) -> int | None:
    match = re.match(r"\s*(\d+)", str(value))
    return int(match.group(1)) if match else None


def benchmark_2022() -> dict[str, Any]:
    path = RAW / "2022" / "C_problem" / "附件.xlsx"
    info = pd.read_excel(path, sheet_name=0)
    composition = pd.read_excel(path, sheet_name=1)
    component_columns = list(composition.columns[1:])
    composition["artifact_id"] = composition.iloc[:, 0].map(artifact_id)
    type_map = info.set_index(info.columns[0])[info.columns[2]]
    composition["target"] = composition["artifact_id"].map(type_map)
    valid = valid_composition_mask(composition[component_columns]) & composition["target"].notna()
    data = composition.loc[valid].copy()
    raw_x = data[component_columns].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    clr_x = clr_transform(raw_x, zero_replacement=0.01)
    y = data["target"].astype(str)
    groups = data["artifact_id"]
    cv = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=2026)

    baseline = make_pipeline(SimpleImputer(strategy="constant", fill_value=0), DecisionTreeClassifier(max_depth=3, random_state=2026))
    candidate = make_pipeline(StandardScaler(), LogisticRegression(max_iter=4000, class_weight="balanced"))
    baseline_pred = cross_val_predict(baseline, raw_x, y, groups=groups, cv=cv)
    candidate_pred = cross_val_predict(candidate, clr_x, y, groups=groups, cv=cv)

    def metrics(prediction: np.ndarray) -> dict[str, float]:
        return {
            "balanced_accuracy": float(balanced_accuracy_score(y, prediction)),
            "macro_f1": float(f1_score(y, prediction, average="macro")),
        }

    return {
        "case": "2022C",
        "task": "glass-type classification",
        "valid_samples": int(len(data)),
        "baseline": {"method": "raw-percentage decision tree", **metrics(baseline_pred)},
        "candidate": {"method": "CLR plus group-aware logistic regression", **metrics(candidate_pred)},
        "selection": "raw-percentage shallow decision tree for classification; CLR for compositional inference",
        "guardrail": "Samples from the same artifact stay in one fold; zeros are treated as non-detects before CLR.",
    }


def wape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.abs(y_true - y_pred).sum() / max(np.abs(y_true).sum(), 1e-12))


def benchmark_2023() -> dict[str, Any]:
    base = RAW / "2023" / "C_problem"
    cache = ROOT / "benchmarks" / "runs" / "2023C" / "daily_category.csv"
    if cache.exists():
        daily = pd.read_csv(cache, parse_dates=["date"])
    else:
        products = pd.read_excel(base / "附件1.xlsx")
        sales = pd.read_excel(base / "附件2.xlsx")
        product_code = products.columns[0]
        sales_code = sales.columns[2]
        products = products.assign(**{product_code: products[product_code].astype(str)})
        sales = sales.assign(**{sales_code: sales[sales_code].astype(str)})
        sales[sales.columns[0]] = pd.to_datetime(sales.iloc[:, 0])
        merged = sales.merge(
            products.iloc[:, [0, 3]], left_on=sales.columns[2], right_on=products.columns[0], how="left"
        )
        daily = merged.groupby([sales.columns[0], products.columns[3]], as_index=False)[sales.columns[3]].sum()
        daily.columns = ["date", "category", "quantity"]
        cache.parent.mkdir(parents=True, exist_ok=True)
        daily.to_csv(cache, index=False, encoding="utf-8-sig")
    categories = sorted(daily["category"].dropna().unique())
    full_dates = pd.date_range(daily["date"].min(), daily["date"].max(), freq="D")
    grid = pd.MultiIndex.from_product([full_dates, categories], names=["date", "category"]).to_frame(index=False)
    daily = grid.merge(daily, on=["date", "category"], how="left").fillna({"quantity": 0.0})
    daily = daily.sort_values(["category", "date"])
    grouped = daily.groupby("category")["quantity"]
    daily["lag1"] = grouped.shift(1)
    daily["lag7"] = grouped.shift(7)
    daily["lag14"] = grouped.shift(14)
    daily["rolling7"] = grouped.transform(lambda value: value.shift(1).rolling(7).mean())
    daily["day_index"] = (daily["date"] - daily["date"].min()).dt.days
    daily["dow_sin"] = np.sin(2 * np.pi * daily["date"].dt.dayofweek / 7)
    daily["dow_cos"] = np.cos(2 * np.pi * daily["date"].dt.dayofweek / 7)
    daily["category_code"] = pd.Categorical(daily["category"], categories=categories).codes
    data = daily.dropna().copy()
    cutoff = data["date"].max() - pd.Timedelta(days=27)
    train = data[data["date"] < cutoff]
    test = data[data["date"] >= cutoff]
    features = ["lag1", "lag7", "lag14", "rolling7", "day_index", "dow_sin", "dow_cos", "category_code"]
    model = HistGradientBoostingRegressor(max_iter=250, max_leaf_nodes=15, l2_regularization=1.0, random_state=2026)
    model.fit(train[features], train["quantity"])
    prediction = np.clip(model.predict(test[features]), 0, None)
    truth = test["quantity"].to_numpy()
    baseline_prediction = test["lag7"].to_numpy()
    return {
        "case": "2023C",
        "task": "category-level daily demand forecast",
        "test_days": 28,
        "baseline": {
            "method": "seasonal naive lag-7",
            "mae": float(mean_absolute_error(truth, baseline_prediction)),
            "wape": wape(truth, baseline_prediction),
        },
        "candidate": {
            "method": "lagged histogram gradient boosting",
            "mae": float(mean_absolute_error(truth, prediction)),
            "wape": wape(truth, prediction),
        },
        "selection": "lagged histogram gradient boosting",
        "guardrail": "The final 28 calendar days are held out; random train-test splitting is forbidden.",
    }


def midpoint_price(value: object) -> float:
    numbers = [float(item) for item in re.findall(r"\d+(?:\.\d+)?", str(value))]
    return float(np.mean(numbers)) if numbers else float("nan")


def benchmark_2024() -> dict[str, Any]:
    base = RAW / "2024" / "CUMCM2024Problems" / "C题"
    land = pd.read_excel(base / "附件1.xlsx", sheet_name=0)
    planting = pd.read_excel(base / "附件2.xlsx", sheet_name=0)
    stats = pd.read_excel(base / "附件2.xlsx", sheet_name=1)
    land[land.columns[1]] = land.iloc[:, 1].astype("string").str.strip()
    planting[planting.columns[5]] = planting.iloc[:, 5].astype("string").str.strip()
    stats[stats.columns[3]] = stats.iloc[:, 3].astype("string").str.strip()
    stats[stats.columns[4]] = stats.iloc[:, 4].astype("string").str.strip()
    land_map = land.set_index(land.columns[0])[land.columns[1]]
    area_by_type = land.groupby(land.columns[1])[land.columns[2]].sum().to_dict()
    planting[planting.columns[0]] = planting.iloc[:, 0].ffill()
    planting["land_type"] = planting.iloc[:, 0].map(land_map)
    stats = stats.copy()
    stats["price"] = stats.iloc[:, 7].map(midpoint_price)
    stats["yield"] = pd.to_numeric(stats.iloc[:, 5], errors="coerce")
    stats["cost"] = pd.to_numeric(stats.iloc[:, 6], errors="coerce")
    stats = stats.dropna(subset=[stats.columns[1], stats.columns[3], stats.columns[4], "price", "yield", "cost"]).reset_index(drop=True)
    smart_first = stats[(stats.iloc[:, 3] == "普通大棚") & (stats.iloc[:, 4] == "第一季")].copy()
    smart_first[smart_first.columns[3]] = "智慧大棚"
    stats = pd.concat([stats, smart_first], ignore_index=True)

    production_rows = planting.merge(
        stats[[stats.columns[1], stats.columns[3], stats.columns[4], "yield", "cost", "price"]],
        left_on=[planting.columns[1], "land_type", planting.columns[5]],
        right_on=[stats.columns[1], stats.columns[3], stats.columns[4]],
        how="left",
    )
    if production_rows[["yield", "cost", "price"]].isna().any().any():
        raise RuntimeError("2024 planting rows could not be matched to land-type statistics")
    production_rows["production"] = production_rows.iloc[:, 4] * production_rows["yield"]
    demand = production_rows.groupby(planting.columns[1])["production"].sum().to_dict()
    baseline_profit = float(
        (production_rows["production"] * production_rows["price"] - production_rows.iloc[:, 4] * production_rows["cost"]).sum()
    )

    n = len(stats)
    objective = np.concatenate([stats["cost"].to_numpy(), -stats["price"].to_numpy()])
    a_ub: list[np.ndarray] = []
    b_ub: list[float] = []
    for i, row in stats.iterrows():
        constraint = np.zeros(2 * n)
        constraint[n + i] = 1
        constraint[i] = -row["yield"]
        a_ub.append(constraint)
        b_ub.append(0.0)
    for crop_id, crop_demand in demand.items():
        constraint = np.zeros(2 * n)
        indices = np.flatnonzero(stats.iloc[:, 1].to_numpy() == crop_id)
        constraint[n + indices] = 1
        a_ub.append(constraint)
        b_ub.append(float(crop_demand))
    for land_type, capacity in area_by_type.items():
        seasons = stats.loc[stats.iloc[:, 3] == land_type, stats.columns[4]].dropna().unique()
        if land_type == "水浇地":
            season_pairs = [("单季", "第一季"), ("单季", "第二季")]
        else:
            season_pairs = [(season,) for season in seasons]
        for season_group in season_pairs:
            constraint = np.zeros(2 * n)
            mask = (stats.iloc[:, 3] == land_type) & stats.iloc[:, 4].isin(season_group)
            constraint[np.flatnonzero(mask.to_numpy())] = 1
            a_ub.append(constraint)
            b_ub.append(float(capacity))
    result = linprog(objective, A_ub=np.vstack(a_ub), b_ub=np.asarray(b_ub), bounds=(0, None), method="highs")
    if not result.success:
        raise RuntimeError(f"2024 relaxed LP failed: {result.message}")
    upper_profit = float(-result.fun)
    return {
        "case": "2024C",
        "task": "one-year aggregate planting upper bound",
        "baseline": {"method": "reported 2023 planting", "profit": baseline_profit},
        "candidate": {"method": "demand-capped aggregate linear program", "profit_upper_bound": upper_profit},
        "selection": "not selectable as a final plan; use only as an upper-bound regression test",
        "guardrail": "This is an upper bound only; plot-level rotation, bean windows, minimum area and dispersion must be added before submission.",
    }


def group_regression_predictions(model: Any, x: pd.DataFrame, y: pd.Series, groups: pd.Series) -> np.ndarray:
    prediction = np.full(len(y), np.nan)
    for train_index, test_index in GroupKFold(n_splits=5).split(x, y, groups):
        model.fit(x.iloc[train_index], y.iloc[train_index])
        prediction[test_index] = model.predict(x.iloc[test_index])
    return prediction


def benchmark_2025() -> dict[str, Any]:
    path = RAW / "2025" / "C题" / "附件.xlsx"
    male = pd.read_excel(path, sheet_name=0)
    female = pd.read_excel(path, sheet_name=1)
    male["week_numeric"] = male["检测孕周"].map(gestational_week)
    regression_features = ["week_numeric", "孕妇BMI", "年龄", "身高", "体重"]
    male_data = male.dropna(subset=regression_features + ["Y染色体浓度", "孕妇代码"]).reset_index(drop=True)
    x = male_data[regression_features]
    y = male_data["Y染色体浓度"]
    groups = male_data["孕妇代码"]
    linear = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), LinearRegression())
    nonlinear = HistGradientBoostingRegressor(max_iter=220, max_leaf_nodes=12, l2_regularization=1.0, random_state=2026)
    linear_prediction = group_regression_predictions(linear, x, y, groups)
    nonlinear_prediction = group_regression_predictions(nonlinear, x, y, groups)

    label_column = "染色体的非整倍体"
    z_columns = ["13号染色体的Z值", "18号染色体的Z值", "21号染色体的Z值"]
    classification_features = z_columns + [
        "X染色体的Z值",
        "GC含量",
        "原始读段数",
        "在参考基因组上比对的比例",
        "重复读段的比例",
        "被过滤掉读段数的比例",
        "孕妇BMI",
        "年龄",
    ]
    female_data = female.dropna(subset=["孕妇代码"] + z_columns).reset_index(drop=True)
    target = female_data[label_column].notna().astype(int)
    female_x = female_data[classification_features]
    female_groups = female_data["孕妇代码"]
    rule_prediction = (female_data[z_columns].abs().max(axis=1) >= 3).astype(int)
    classifier = make_pipeline(
        SimpleImputer(strategy="median"),
        StandardScaler(),
        LogisticRegression(max_iter=3000, class_weight="balanced"),
    )
    cv = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=2026)
    probability = cross_val_predict(classifier, female_x, target, groups=female_groups, cv=cv, method="predict_proba")[:, 1]
    learned_prediction = (probability >= 0.5).astype(int)
    return {
        "case": "2025C",
        "task": "longitudinal concentration plus female anomaly screening",
        "regression": {
            "baseline": {
                "method": "group-aware linear regression",
                "mae": float(mean_absolute_error(y, linear_prediction)),
                "r2": float(r2_score(y, linear_prediction)),
            },
            "candidate": {
                "method": "group-aware nonlinear boosting",
                "mae": float(mean_absolute_error(y, nonlinear_prediction)),
                "r2": float(r2_score(y, nonlinear_prediction)),
            },
            "selection": "group-aware linear regression; nonlinear candidate rejected on held-out women",
        },
        "classification": {
            "baseline": {
                "method": "absolute chromosome Z-score >= 3",
                "balanced_accuracy": float(balanced_accuracy_score(target, rule_prediction)),
                "f1": float(f1_score(target, rule_prediction)),
            },
            "candidate": {
                "method": "group-aware balanced logistic regression",
                "balanced_accuracy": float(balanced_accuracy_score(target, learned_prediction)),
                "f1": float(f1_score(target, learned_prediction)),
                "average_precision": float(average_precision_score(target, probability)),
            },
            "selection": "balanced logistic regression is provisional; current scores are not submission-ready",
        },
        "guardrail": "Rows from one pregnant woman never cross validation folds; screening metrics do not establish clinical safety.",
    }


BENCHMARKS = {
    "2021C": benchmark_2021,
    "2022C": benchmark_2022,
    "2023C": benchmark_2023,
    "2024C": benchmark_2024,
    "2025C": benchmark_2025,
}


def clean_numbers(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: clean_numbers(item) for key, item in value.items()}
    if isinstance(value, list):
        return [clean_numbers(item) for item in value]
    if isinstance(value, float):
        return round(value, 6) if math.isfinite(value) else None
    return value


def write_markdown(records: list[dict[str, Any]], output: Path) -> None:
    lines = ["# Five-year model diagnostics", ""]
    for record in records:
        lines.extend([f"## {record['case']}: {record['task']}", "", "```json", json.dumps(record, ensure_ascii=False, indent=2), "```", ""])
    output.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run five official C-problem model diagnostics.")
    parser.add_argument("--case", choices=["all", *BENCHMARKS], default="all")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selected = list(BENCHMARKS) if args.case == "all" else [args.case]
    records: list[dict[str, Any]] = []
    for case_id in selected:
        print(f"Running {case_id}...")
        records.append(clean_numbers(BENCHMARKS[case_id]()))
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {"schema_version": 1, "purpose": "diagnostic baselines, not full contest solutions", "cases": records}
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(records, output.with_suffix(".md"))
    print(f"PASS: completed {len(records)} model diagnostics")
    print(f"Saved: {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
