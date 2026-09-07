"""Calculate and rank the six-dimension problem-selection scorecard."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "templates" / "problem_selection_scorecard.csv"
DEFAULT_OUTPUT = ROOT / "outputs" / "problem_selection_ranked.csv"
WEIGHTS = {
    "data_score": 0.20,
    "coding_score": 0.15,
    "metric_score": 0.20,
    "writing_score": 0.15,
    "team_score": 0.15,
    "innovation_score": 0.15,
}


def score_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    scored: list[dict[str, str]] = []
    errors: list[str] = []
    for row in rows:
        problem = row.get("problem", "?")
        values: dict[str, float] = {}
        for field in WEIGHTS:
            raw = (row.get(field) or "").strip()
            try:
                value = float(raw)
            except ValueError:
                errors.append(f"{problem}: {field} must be a number from 1 to 5")
                continue
            if not 1 <= value <= 5:
                errors.append(f"{problem}: {field}={value:g} is outside 1..5")
            values[field] = value
        if len(values) != len(WEIGHTS):
            continue

        item = dict(row)
        item["weighted_score"] = f"{sum(values[key] * weight for key, weight in WEIGHTS.items()):.3f}"
        if values["data_score"] == 1 or values["team_score"] == 1:
            item["veto"] = "yes"
        else:
            item["veto"] = "yes" if (row.get("veto") or "").strip().lower() == "yes" else "no"
        scored.append(item)

    if errors:
        raise ValueError("\n".join(errors))
    return sorted(
        scored,
        key=lambda item: (item["veto"] == "yes", -float(item["weighted_score"]), item.get("problem", "")),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rank A/B/C using the six-dimension scorecard.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    with args.input.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or not set(WEIGHTS).issubset(reader.fieldnames):
            print("FAIL: scorecard columns do not match the six-dimension template")
            return 1
        rows = list(reader)
        fieldnames = reader.fieldnames

    try:
        ranked = score_rows(rows)
    except ValueError as exc:
        print(f"FAIL:\n{exc}")
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(ranked)

    print("Problem ranking:")
    for index, row in enumerate(ranked, start=1):
        print(f"{index}. {row['problem']}: {row['weighted_score']} veto={row['veto']}")
    print(f"Saved: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
