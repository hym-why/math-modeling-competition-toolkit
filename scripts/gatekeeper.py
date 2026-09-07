"""Small G1-G6 checkpoint tracker for a three-person CUMCM team."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from result_freeze import DEFAULT_MANIFEST, DEFAULT_OUTPUTS, verify


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


ROOT = Path(__file__).resolve().parents[1]
STATE_FILE = ROOT / "state" / "gates.json"
GATES = {
    "G1": "题目已拆解",
    "G2": "方法已用基准/PoC 验证",
    "G3": "代码已复现并交叉检查",
    "G4": "结果已冻结",
    "G5": "论文证据链已闭合",
    "G6": "终稿与提交材料已审计",
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def initial_state() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "updated_at": now(),
        "gates": {
            gate: {"name": name, "status": "pending", "note": "", "artifacts": []}
            for gate, name in GATES.items()
        },
        "history": [],
    }


def load_state() -> dict[str, Any]:
    if not STATE_FILE.exists():
        return initial_state()
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))


def save_state(state: dict[str, Any]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = now()
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_artifacts(values: list[str]) -> tuple[list[str], list[str]]:
    paths: list[str] = []
    missing: list[str] = []
    for value in values:
        path = (ROOT / value).resolve() if not Path(value).is_absolute() else Path(value).resolve()
        if not path.exists():
            missing.append(value)
            continue
        paths.append(path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path))
    return paths, missing


def pass_gate(args: argparse.Namespace) -> int:
    state = load_state()
    order = list(GATES)
    gate_index = order.index(args.gate)
    prior = [gate for gate in order[:gate_index] if state["gates"][gate]["status"] != "pass"]
    if prior:
        print(f"FAIL: pass earlier gates first: {', '.join(prior)}")
        return 1

    artifacts, missing = normalize_artifacts(args.artifact)
    if missing:
        print(f"FAIL: missing artifacts: {', '.join(missing)}")
        return 1
    if not artifacts:
        print("FAIL: provide at least one --artifact as evidence")
        return 1
    if args.gate == "G4":
        freeze_issues = verify(DEFAULT_OUTPUTS, DEFAULT_MANIFEST)
        if freeze_issues:
            print("FAIL: G4 requires a current result freeze")
            for issue in freeze_issues:
                print(f"- {issue}")
            return 1
    if args.gate == "G6":
        audit_path = ROOT / "state" / "audit_report.json"
        if not audit_path.exists():
            print("FAIL: G6 requires state/audit_report.json")
            return 1
        try:
            audit = json.loads(audit_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            print(f"FAIL: cannot read audit report: {exc}")
            return 1
        if audit.get("status") != "pass":
            print("FAIL: G6 requires a passing project audit")
            return 1
        for relative_path, expected_hash in audit.get("evidence_hashes", {}).items():
            evidence_path = ROOT / relative_path
            if not evidence_path.exists() or sha256(evidence_path) != expected_hash:
                print(f"FAIL: audit report is stale because evidence changed: {relative_path}")
                return 1

    state["gates"][args.gate].update(status="pass", note=args.note, artifacts=artifacts)
    state["history"].append(
        {"at": now(), "action": "pass", "gate": args.gate, "note": args.note, "artifacts": artifacts}
    )
    save_state(state)
    print(f"PASS: {args.gate} {GATES[args.gate]}")
    return 0


def reopen_gate(args: argparse.Namespace) -> int:
    state = load_state()
    order = list(GATES)
    gate_index = order.index(args.gate)
    for gate in order[gate_index:]:
        state["gates"][gate].update(status="pending", note="", artifacts=[])
    state["history"].append(
        {"at": now(), "action": "reopen", "gate": args.gate, "reason": args.reason}
    )
    save_state(state)
    print(f"PASS: reopened {args.gate} and reset downstream gates")
    return 0


def print_status() -> int:
    state = load_state()
    stale = bool(verify(DEFAULT_OUTPUTS, DEFAULT_MANIFEST))
    for gate, name in GATES.items():
        status = state["gates"][gate]["status"]
        suffix = " (STALE)" if gate == "G4" and status == "pass" and stale else ""
        print(f"{gate} [{status.upper()}]{suffix} {name}")
    return 1 if stale and state["gates"]["G4"]["status"] == "pass" else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Track the lightweight G1-G6 contest gates.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status")

    pass_parser = subparsers.add_parser("pass")
    pass_parser.add_argument("gate", choices=GATES)
    pass_parser.add_argument("--note", required=True)
    pass_parser.add_argument("--artifact", action="append", default=[])

    reopen_parser = subparsers.add_parser("reopen")
    reopen_parser.add_argument("gate", choices=GATES)
    reopen_parser.add_argument("--reason", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "status":
        return print_status()
    if args.command == "pass":
        return pass_gate(args)
    return reopen_gate(args)


if __name__ == "__main__":
    sys.exit(main())
