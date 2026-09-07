"""Create and verify a compact data contract for CUMCM input files."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "state" / "data_contract.json"
SUPPORTED_SUFFIXES = {".csv", ".xlsx", ".xls", ".json"}


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def display_path(path: Path) -> str:
    resolved = path.resolve()
    return resolved.relative_to(ROOT).as_posix() if resolved.is_relative_to(ROOT) else str(resolved)


def json_value(value: Any) -> Any:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def read_csv_robust(path: Path) -> pd.DataFrame:
    errors: list[str] = []
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            return pd.read_csv(path, encoding=encoding)
        except UnicodeDecodeError as exc:
            errors.append(f"{encoding}: {exc}")
    raise ValueError(f"Cannot decode CSV {path}: {'; '.join(errors)}")


def load_tables(path: Path) -> dict[str, pd.DataFrame]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return {path.stem: read_csv_robust(path)}
    if suffix in {".xlsx", ".xls"}:
        workbook = pd.ExcelFile(path)
        return {sheet: workbook.parse(sheet_name=sheet) for sheet in workbook.sheet_names}
    if suffix == ".json":
        return {path.stem: pd.read_json(path)}
    raise ValueError(f"Unsupported data format: {path.suffix}")


def profile_column(series: pd.Series) -> dict[str, Any]:
    non_null = series.dropna()
    profile: dict[str, Any] = {
        "name": str(series.name),
        "dtype": str(series.dtype),
        "missing_count": int(series.isna().sum()),
        "missing_pct": round(float(series.isna().mean() * 100), 3),
        "unique_count": int(non_null.nunique(dropna=True)),
    }
    if pd.api.types.is_numeric_dtype(series) and not non_null.empty:
        profile["numeric"] = {
            "min": json_value(non_null.min()),
            "max": json_value(non_null.max()),
            "mean": json_value(non_null.mean()),
            "median": json_value(non_null.median()),
            "std": json_value(non_null.std(ddof=1)) if len(non_null) > 1 else None,
        }
    elif not non_null.empty:
        profile["examples"] = [json_value(value) for value in non_null.astype(str).unique()[:3]]
    return profile


def profile_table(name: str, frame: pd.DataFrame) -> tuple[dict[str, Any], list[str]]:
    rows = len(frame)
    warnings: list[str] = []
    columns = [profile_column(frame[column]) for column in frame.columns]
    for column in columns:
        label = f"{name}.{column['name']}"
        if column["missing_pct"] >= 20:
            warnings.append(f"{label}: missing rate is {column['missing_pct']}%")
        if rows > 0 and column["unique_count"] <= 1:
            warnings.append(f"{label}: constant or empty column")
        normalized_name = column["name"].lower()
        unique_ratio = column["unique_count"] / rows if rows else 0
        if unique_ratio >= 0.95 and any(token in normalized_name for token in ("id", "编号", "序号", "代码")):
            warnings.append(f"{label}: likely identifier; do not use as a numeric feature without justification")
    if rows == 0:
        warnings.append(f"{name}: table has no rows")
    if len(frame.columns) == 0:
        warnings.append(f"{name}: table has no columns")
    return (
        {
            "name": name,
            "rows": rows,
            "columns_count": len(frame.columns),
            "duplicate_rows": int(frame.duplicated().sum()),
            "columns": columns,
        },
        warnings,
    )


def create_contract(paths: list[Path], output: Path) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    warnings: list[str] = []
    for path in paths:
        resolved = path.resolve()
        if not resolved.exists() or not resolved.is_file():
            raise ValueError(f"Input file does not exist: {path}")
        if resolved.suffix.lower() not in SUPPORTED_SUFFIXES:
            raise ValueError(f"Unsupported input file: {path}")
        tables = load_tables(resolved)
        table_records: list[dict[str, Any]] = []
        for name, frame in tables.items():
            table_record, table_warnings = profile_table(name, frame)
            table_records.append(table_record)
            warnings.extend(f"{display_path(resolved)}::{warning}" for warning in table_warnings)
        records.append(
            {
                "path": display_path(resolved),
                "bytes": resolved.stat().st_size,
                "sha256": file_hash(resolved),
                "tables": table_records,
            }
        )

    contract = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "files": records,
        "warnings": warnings,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return contract


def verify_contract(contract_path: Path) -> list[str]:
    if not contract_path.exists():
        return [f"Missing data contract: {contract_path}"]
    try:
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return [f"Cannot read data contract: {exc}"]

    issues: list[str] = []
    for record in contract.get("files", []):
        stored_path = Path(record["path"])
        path = stored_path if stored_path.is_absolute() else ROOT / stored_path
        if not path.exists():
            issues.append(f"Missing input: {record['path']}")
        elif file_hash(path) != record.get("sha256"):
            issues.append(f"Input changed: {record['path']}")
    if not contract.get("files"):
        issues.append("Data contract contains no files")
    return issues


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create or verify a data contract.")
    subparsers = parser.add_subparsers(dest="action", required=True)
    create_parser = subparsers.add_parser("create")
    create_parser.add_argument("files", nargs="+", type=Path)
    create_parser.add_argument("--output", type=Path, default=DEFAULT_CONTRACT)
    check_parser = subparsers.add_parser("check")
    check_parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.action == "create":
        try:
            contract = create_contract(args.files, args.output.resolve())
        except (ValueError, OSError, ImportError) as exc:
            print(f"FAIL: {exc}")
            return 1
        print(f"PASS: profiled {len(contract['files'])} data files")
        print(f"Warnings: {len(contract['warnings'])}")
        print(f"Saved: {args.output.resolve()}")
        return 0

    issues = verify_contract(args.contract.resolve())
    if issues:
        print("FAIL: data inputs no longer match the contract")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print("PASS: data inputs match the contract")
    return 0


if __name__ == "__main__":
    sys.exit(main())
