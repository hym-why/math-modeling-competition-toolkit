"""Build a reproducible inventory for the official five-year C-problem benchmark."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from data_contract import create_contract


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "benchmarks" / "cases.json"
DEFAULT_OUTPUT = ROOT / "benchmarks" / "runs"
QUESTION_PATTERN = re.compile(
    r"^\s*(?:问题\s*[一二三四五六七八九十0-9]+|第\s*[一二三四五六七八九十0-9]+\s*问|[1-9]\s*[．.、])",
    re.MULTILINE,
)


def resolve_workspace_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def extract_pdf_text(path: Path) -> tuple[str, int]:
    reader = PdfReader(path)
    pages = [(page.extract_text() or "").strip() for page in reader.pages]
    return "\n\n".join(pages).strip() + "\n", len(reader.pages)


def question_headings(text: str) -> list[str]:
    headings: list[str] = []
    for line in text.splitlines():
        cleaned = " ".join(line.split())
        if QUESTION_PATTERN.match(cleaned):
            headings.append(cleaned[:160])
    return headings


def validate_case(case: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for key in ("problem_pdf", "data_files", "output_templates"):
        values = [case[key]] if isinstance(case[key], str) else case[key]
        for value in values:
            if not resolve_workspace_path(value).is_file():
                missing.append(value)
    return missing


def run_case(case: dict[str, Any], output_root: Path) -> dict[str, Any]:
    missing = validate_case(case)
    if missing:
        raise ValueError(f"{case['id']} is missing files: {', '.join(missing)}")

    case_dir = output_root / case["id"]
    case_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = resolve_workspace_path(case["problem_pdf"])
    text, page_count = extract_pdf_text(pdf_path)
    (case_dir / "problem.txt").write_text(text, encoding="utf-8")

    data_paths = [resolve_workspace_path(value) for value in case["data_files"]]
    contract = create_contract(data_paths, case_dir / "data_contract.json")
    record = {
        "id": case["id"],
        "year": case["year"],
        "problem_pdf": case["problem_pdf"],
        "page_count": page_count,
        "text_characters": len(text),
        "question_headings": question_headings(text),
        "data_file_count": len(data_paths),
        "table_count": sum(len(item["tables"]) for item in contract["files"]),
        "data_warnings": len(contract["warnings"]),
        "output_template_count": len(case["output_templates"]),
    }
    (case_dir / "summary.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return record


def write_markdown(records: list[dict[str, Any]], output: Path) -> None:
    lines = [
        "# Official five-year C-problem benchmark",
        "",
        "| Case | Pages | Questions detected | Data files | Tables | Warnings | Output templates |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for record in records:
        lines.append(
            f"| {record['id']} | {record['page_count']} | {len(record['question_headings'])} "
            f"| {record['data_file_count']} | {record['table_count']} | {record['data_warnings']} "
            f"| {record['output_template_count']} |"
        )
    lines.extend(["", "Generated from `benchmarks/cases.json`.", ""])
    output.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the official five-year C-problem inventory.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest_path = args.manifest.resolve()
    output_root = args.output.resolve()
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        records = [run_case(case, output_root) for case in manifest["cases"]]
    except (KeyError, ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"FAIL: {exc}")
        return 1

    summary = {"schema_version": 1, "scope": manifest["scope"], "cases": records}
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_markdown(records, output_root / "summary.md")
    print(f"PASS: processed {len(records)} official C problems")
    print(f"Saved: {output_root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
