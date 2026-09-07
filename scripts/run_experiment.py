"""Run a contest Python entry point and save reproducibility evidence."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "experiments"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def snapshot(directory: Path) -> dict[str, dict[str, Any]]:
    if not directory.exists():
        return {}
    records: dict[str, dict[str, Any]] = {}
    for path in sorted(directory.rglob("*")):
        if not path.is_file() or path.name == ".gitkeep" or "__pycache__" in path.parts:
            continue
        records[path.relative_to(ROOT).as_posix()] = {"bytes": path.stat().st_size, "sha256": sha256(path)}
    return records


def package_versions() -> dict[str, str | None]:
    result: dict[str, str | None] = {}
    for package in ("numpy", "pandas", "matplotlib", "scipy", "scikit-learn", "openpyxl", "statsmodels", "pulp", "scikit-criteria"):
        try:
            result[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            result[package] = None
    return result


def git_revision() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        return result.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def parse_parameters(values: list[str]) -> dict[str, str]:
    parameters: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"Parameter must use key=value: {value}")
        key, parameter_value = value.split("=", 1)
        if not key.strip():
            raise ValueError(f"Parameter name is empty: {value}")
        parameters[key.strip()] = parameter_value.strip()
    return parameters


def safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip()).strip("-.")
    return cleaned or "experiment"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run and record a reproducible contest experiment.")
    parser.add_argument("--name", required=True)
    parser.add_argument("--entry", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--parameter", action="append", default=[])
    parser.add_argument("entry_args", nargs=argparse.REMAINDER)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    entry = args.entry.resolve()
    if not entry.exists() or not entry.is_file():
        print(f"FAIL: entry point does not exist: {entry}")
        return 1
    try:
        parameters = parse_parameters(args.parameter)
    except ValueError as exc:
        print(f"FAIL: {exc}")
        return 1

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = EXPERIMENTS / f"{timestamp}_{safe_name(args.name)}"
    counter = 2
    while run_dir.exists():
        run_dir = EXPERIMENTS / f"{timestamp}_{safe_name(args.name)}_{counter}"
        counter += 1
    run_dir.mkdir(parents=True)

    entry_args = args.entry_args[1:] if args.entry_args[:1] == ["--"] else args.entry_args
    command = [sys.executable, str(entry), *entry_args]
    environment = os.environ.copy()
    environment.update(
        {
            "PYTHONHASHSEED": str(args.seed),
            "PYTHONIOENCODING": "utf-8",
            "MATH_MODEL_SEED": str(args.seed),
            "MATH_MODEL_PARAMETERS": json.dumps(parameters, ensure_ascii=False),
        }
    )

    inputs_before = snapshot(ROOT / "data")
    code_before = snapshot(ROOT / "code")
    outputs_before = snapshot(ROOT / "outputs")
    started_at = datetime.now(timezone.utc).isoformat()
    start = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    elapsed = time.perf_counter() - start
    outputs_after = snapshot(ROOT / "outputs")
    inputs_after = snapshot(ROOT / "data")
    code_after = snapshot(ROOT / "code")

    (run_dir / "stdout.log").write_text(completed.stdout, encoding="utf-8")
    (run_dir / "stderr.log").write_text(completed.stderr, encoding="utf-8")
    produced_or_changed = {
        path: metadata
        for path, metadata in outputs_after.items()
        if outputs_before.get(path) != metadata
    }
    warnings: list[str] = []
    if inputs_after != inputs_before:
        warnings.append("Files under data/ changed during the experiment")
    if code_after != code_before:
        warnings.append("Files under code/ changed during the experiment")
    if not produced_or_changed:
        warnings.append("Experiment produced no new or changed files under outputs/")

    manifest = {
        "schema_version": 1,
        "name": args.name,
        "started_at": started_at,
        "elapsed_seconds": round(elapsed, 3),
        "command": command,
        "entry": entry.relative_to(ROOT).as_posix() if entry.is_relative_to(ROOT) else str(entry),
        "seed": args.seed,
        "parameters": parameters,
        "return_code": completed.returncode,
        "git_revision": git_revision(),
        "package_versions": package_versions(),
        "inputs": inputs_before,
        "source_files": code_before,
        "outputs": produced_or_changed,
        "warnings": warnings,
    }
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(completed.stdout, end="")
    if completed.stderr:
        print(completed.stderr, file=sys.stderr, end="")
    print(f"Experiment evidence: {run_dir}")
    if warnings:
        for warning in warnings:
            print(f"WARNING: {warning}")
    return completed.returncode


if __name__ == "__main__":
    sys.exit(main())
