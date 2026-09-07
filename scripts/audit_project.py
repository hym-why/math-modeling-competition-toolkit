"""Fail-closed audit for the lightweight CUMCM project workflow."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from data_contract import DEFAULT_CONTRACT, verify_contract
from result_freeze import DEFAULT_MANIFEST, DEFAULT_OUTPUTS, verify as verify_freeze


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "state" / "audit_report.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def resolve_artifact(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def audit_claims() -> tuple[list[str], list[str]]:
    path = ROOT / "templates" / "claim_evidence_map.csv"
    rows = read_csv(path)
    errors: list[str] = []
    warnings: list[str] = []
    active = [row for row in rows if (row.get("claim_or_number") or "").strip()]
    if not active:
        return ["Claim-evidence map contains no completed claims"], warnings
    for row in active:
        claim_id = row.get("claim_id") or "?"
        for field in ("paper_section", "evidence_file", "evidence_field_or_figure", "generator_script", "owner"):
            if not (row.get(field) or "").strip():
                errors.append(f"Claim {claim_id} is missing {field}")
        for field in ("evidence_file", "generator_script"):
            value = (row.get(field) or "").strip()
            if value and not resolve_artifact(value).exists():
                errors.append(f"Claim {claim_id} points to missing {field}: {value}")
        if (row.get("verified") or "").strip().lower() != "yes":
            errors.append(f"Claim {claim_id} is not independently verified")
    return errors, warnings


def audit_figures() -> tuple[list[str], list[str]]:
    path = ROOT / "templates" / "figure_contract.csv"
    rows = read_csv(path)
    errors: list[str] = []
    warnings: list[str] = []
    active = [row for row in rows if (row.get("claim_supported") or "").strip()]
    if not active:
        return errors, ["Figure contract contains no completed figures"]
    for row in active:
        figure_id = row.get("figure_id") or "?"
        for field in ("question", "chart_type", "figure_file", "source_data", "generator_script", "units", "paper_reference"):
            if not (row.get(field) or "").strip():
                errors.append(f"Figure {figure_id} is missing {field}")
        for field in ("figure_file", "source_data", "generator_script"):
            value = (row.get(field) or "").strip()
            if value and not resolve_artifact(value).exists():
                errors.append(f"Figure {figure_id} points to missing {field}: {value}")
        if (row.get("caption_status") or "").strip().lower() not in {"done", "yes"}:
            errors.append(f"Figure {figure_id} caption is not complete")
        if (row.get("verified") or "").strip().lower() != "yes":
            errors.append(f"Figure {figure_id} is not independently verified")
    return errors, warnings


def audit_experiments() -> tuple[list[str], list[str]]:
    manifests = sorted((ROOT / "experiments").glob("*/manifest.json")) if (ROOT / "experiments").exists() else []
    if not manifests:
        return ["No experiment manifest found under experiments/"], []
    errors: list[str] = []
    warnings: list[str] = []
    successful = 0
    for path in manifests:
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            errors.append(f"Cannot read experiment manifest {path.relative_to(ROOT)}: {exc}")
            continue
        if manifest.get("return_code") == 0:
            successful += 1
        if not manifest.get("outputs"):
            warnings.append(f"Experiment has no changed outputs: {path.parent.name}")
    if successful == 0:
        errors.append("No successful experiment run is recorded")
    return errors, warnings


def audit_assumptions() -> tuple[list[str], list[str]]:
    rows = read_csv(ROOT / "templates" / "assumption_register.csv")
    active = [row for row in rows if (row.get("assumption") or "").strip()]
    if not active:
        return [], ["Assumption register contains no completed assumptions"]
    errors: list[str] = []
    for row in active:
        assumption_id = row.get("assumption_id") or "?"
        for field in ("question", "rationale", "impact_if_false", "test_or_sensitivity", "evidence_file", "paper_reference", "owner"):
            if not (row.get(field) or "").strip():
                errors.append(f"Assumption {assumption_id} is missing {field}")
        evidence = (row.get("evidence_file") or "").strip()
        if evidence and not resolve_artifact(evidence).exists():
            errors.append(f"Assumption {assumption_id} points to missing evidence: {evidence}")
        if (row.get("status") or "").strip().lower() not in {"accepted", "verified", "closed"}:
            errors.append(f"Assumption {assumption_id} is not closed")
    return errors, []


def audit_reviewer_scorecard() -> tuple[list[str], list[str]]:
    rows = read_csv(ROOT / "templates" / "reviewer_scorecard.csv")
    if not rows:
        return ["Reviewer scorecard is missing or empty"], []
    errors: list[str] = []
    total_weight = 0.0
    weighted_score = 0.0
    for row in rows:
        dimension = row.get("dimension") or "?"
        try:
            score = float((row.get("score_1_to_5") or "").strip())
            weight = float((row.get("weight") or "").strip())
        except ValueError:
            errors.append(f"Reviewer dimension {dimension} has no valid score or weight")
            continue
        if not 1 <= score <= 5:
            errors.append(f"Reviewer dimension {dimension} score is outside 1..5")
        if weight <= 0:
            errors.append(f"Reviewer dimension {dimension} weight must be positive")
        total_weight += weight
        weighted_score += score * weight
        if score <= 2:
            errors.append(f"Reviewer dimension {dimension} has a blocking score of {score:g}")
        for field in ("evidence", "owner"):
            if not (row.get(field) or "").strip():
                errors.append(f"Reviewer dimension {dimension} is missing {field}")
        blocking = (row.get("blocking_issue") or "").strip().lower()
        if blocking not in {"", "no", "none", "无"}:
            errors.append(f"Reviewer dimension {dimension} still has a blocking issue: {row.get('blocking_issue')}")
        if (row.get("status") or "").strip().lower() not in {"pass", "closed"}:
            errors.append(f"Reviewer dimension {dimension} is not closed")
    if abs(total_weight - 100) > 1e-9:
        errors.append(f"Reviewer weights must sum to 100, found {total_weight:g}")
    average = weighted_score / total_weight if total_weight else 0.0
    if average < 3.5:
        errors.append(f"Reviewer weighted score is {average:.2f}/5, below the internal 3.50 gate")
    return errors, [f"Reviewer weighted score: {average:.2f}/5"]


def audit_submission() -> tuple[list[str], list[str], list[Path]]:
    submission = ROOT / "submission"
    files = sorted(path for path in submission.iterdir() if path.is_file()) if submission.exists() else []
    papers = [path for path in files if path.suffix.lower() in {".pdf", ".doc", ".docx"}]
    archives = [path for path in files if path.suffix.lower() in {".zip", ".rar"}]
    errors: list[str] = []
    if len(papers) != 1:
        errors.append(f"submission/ must contain exactly one paper, found {len(papers)}")
    if len(archives) != 1:
        errors.append(f"submission/ must contain exactly one support archive, found {len(archives)}")
    for path in files:
        if path.stat().st_size > 20 * 1024 * 1024:
            errors.append(f"Submission file exceeds 20 MB: {path.name}")
    warnings = ["RAR archive content cannot be inspected automatically; manually check filenames and identity data"] if any(path.suffix.lower() == ".rar" for path in archives) else []
    return errors, warnings, files


def audit_gates() -> tuple[list[str], list[str]]:
    path = ROOT / "state" / "gates.json"
    if not path.exists():
        return ["Missing gate state"], []
    state = json.loads(path.read_text(encoding="utf-8"))
    incomplete = [
        gate
        for gate, item in state.get("gates", {}).items()
        if gate != "G6" and item.get("status") != "pass"
    ]
    return ([f"Incomplete gates: {', '.join(incomplete)}"] if incomplete else []), []


def scan_forbidden(terms: list[str]) -> list[str]:
    findings: list[str] = []
    if not terms:
        return findings
    suffixes = {".md", ".txt", ".csv", ".json", ".py", ".tex"}
    roots = [ROOT / name for name in ("submission", "code", "outputs")]
    for base in roots:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(ROOT).as_posix()
            for term in terms:
                if term.lower() in relative.lower():
                    findings.append(f"Forbidden identity term in filename: {relative}")
            if path.suffix.lower() in suffixes:
                text = path.read_text(encoding="utf-8", errors="ignore")
                for term in terms:
                    if term and term.lower() in text.lower():
                        findings.append(f"Forbidden identity term in file content: {relative}")
            if path.suffix.lower() == ".zip":
                try:
                    with zipfile.ZipFile(path) as archive:
                        for member in archive.infolist():
                            member_name = member.filename
                            for term in terms:
                                if term and term.lower() in member_name.lower():
                                    findings.append(f"Forbidden identity term in ZIP filename: {relative}::{member_name}")
                            member_suffix = Path(member_name).suffix.lower()
                            if member_suffix in suffixes and member.file_size <= 2 * 1024 * 1024:
                                content = archive.read(member).decode("utf-8", errors="ignore")
                                for term in terms:
                                    if term and term.lower() in content.lower():
                                        findings.append(f"Forbidden identity term in ZIP content: {relative}::{member_name}")
                except zipfile.BadZipFile:
                    findings.append(f"Unreadable ZIP archive: {relative}")
    return sorted(set(findings))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit data, experiments, evidence, gates, and privacy.")
    parser.add_argument("--forbidden", action="append", default=[], help="Identity term that must not appear.")
    parser.add_argument("--skip-gates", action="store_true", help="Use during a mid-contest dry run only.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    errors: list[str] = []
    warnings: list[str] = []

    data_issues = verify_contract(DEFAULT_CONTRACT)
    errors.extend(data_issues)
    errors.extend(verify_freeze(DEFAULT_OUTPUTS, DEFAULT_MANIFEST))
    for audit in (audit_experiments, audit_claims, audit_figures, audit_assumptions, audit_reviewer_scorecard):
        audit_errors, audit_warnings = audit()
        errors.extend(audit_errors)
        warnings.extend(audit_warnings)
    if not args.skip_gates:
        gate_errors, gate_warnings = audit_gates()
        errors.extend(gate_errors)
        warnings.extend(gate_warnings)
    errors.extend(scan_forbidden(args.forbidden))

    submission_errors, submission_warnings, submission_files = audit_submission()
    errors.extend(submission_errors)
    warnings.extend(submission_warnings)

    evidence_paths = [
        DEFAULT_CONTRACT,
        DEFAULT_MANIFEST,
        ROOT / "templates" / "claim_evidence_map.csv",
        ROOT / "templates" / "figure_contract.csv",
        ROOT / "templates" / "assumption_register.csv",
        ROOT / "templates" / "reviewer_scorecard.csv",
        *(sorted((ROOT / "experiments").glob("*/manifest.json")) if (ROOT / "experiments").exists() else []),
        *submission_files,
    ]
    evidence_hashes = {
        path.relative_to(ROOT).as_posix(): sha256(path)
        for path in evidence_paths
        if path.exists() and path.is_file()
    }

    report: dict[str, Any] = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "warnings": warnings,
        "evidence_hashes": evidence_hashes,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Audit status: {report['status'].upper()}")
    for error in errors:
        print(f"ERROR: {error}")
    for warning in warnings:
        print(f"WARNING: {warning}")
    print(f"Saved: {REPORT}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
