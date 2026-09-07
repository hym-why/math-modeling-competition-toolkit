"""Freeze and verify contest result files with SHA-256 hashes.

Use this after the model outputs are accepted and before paper numbers are copied.
The script is deliberately dependency-free so it still works under deadline pressure.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUTS = ROOT / "outputs"
DEFAULT_MANIFEST = ROOT / "state" / "frozen_results.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def collect_files(outputs: Path) -> list[Path]:
    if not outputs.exists():
        return []
    return sorted(
        path
        for path in outputs.rglob("*")
        if path.is_file() and path.name != ".gitkeep" and "__pycache__" not in path.parts
    )


def freeze(outputs: Path, manifest: Path) -> dict[str, Any]:
    files = collect_files(outputs)
    if not files:
        raise ValueError(f"No result files found in {outputs}")

    payload: dict[str, Any] = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "outputs_dir": outputs.relative_to(ROOT).as_posix() if outputs.is_relative_to(ROOT) else str(outputs),
        "files": [],
    }
    for path in files:
        payload["files"].append(
            {
                "path": path.relative_to(outputs).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )

    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def verify(outputs: Path, manifest: Path) -> list[str]:
    if not manifest.exists():
        return [f"Missing freeze manifest: {manifest}"]

    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return [f"Cannot read freeze manifest: {exc}"]

    frozen = {item["path"]: item for item in payload.get("files", [])}
    current_paths = collect_files(outputs)
    current = {path.relative_to(outputs).as_posix(): path for path in current_paths}
    issues: list[str] = []

    for relative_path in sorted(frozen.keys() - current.keys()):
        issues.append(f"Deleted after freeze: {relative_path}")
    for relative_path in sorted(current.keys() - frozen.keys()):
        issues.append(f"Added after freeze: {relative_path}")
    for relative_path in sorted(frozen.keys() & current.keys()):
        item = frozen[relative_path]
        path = current[relative_path]
        if path.stat().st_size != item.get("bytes") or sha256(path) != item.get("sha256"):
            issues.append(f"Changed after freeze: {relative_path}")
    return issues


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Freeze or verify contest output files.")
    parser.add_argument("action", choices=("freeze", "check"))
    parser.add_argument("--outputs", type=Path, default=DEFAULT_OUTPUTS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    outputs = args.outputs.resolve()
    manifest = args.manifest.resolve()

    if args.action == "freeze":
        try:
            payload = freeze(outputs, manifest)
        except ValueError as exc:
            print(f"FAIL: {exc}")
            return 1
        print(f"PASS: froze {len(payload['files'])} files into {manifest}")
        return 0

    issues = verify(outputs, manifest)
    if issues:
        print("FAIL: frozen results are stale or incomplete")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print("PASS: current outputs match the frozen manifest")
    return 0


if __name__ == "__main__":
    sys.exit(main())
