"""Record the local modeling environment before the contest starts."""

from __future__ import annotations

import importlib.metadata
import importlib.util
import json
import platform
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "state" / "environment_report.json"
PACKAGES = {
    "numpy": "required",
    "pandas": "required",
    "matplotlib": "required",
    "scipy": "required",
    "sklearn": "required",
    "openpyxl": "required",
    "statsmodels": "recommended",
    "pulp": "recommended",
    "skcriteria": "recommended",
}


def package_record(module_name: str, level: str) -> dict[str, str | bool | None]:
    installed = importlib.util.find_spec(module_name) is not None
    package_name = {"sklearn": "scikit-learn", "skcriteria": "scikit-criteria"}.get(module_name, module_name)
    try:
        version = importlib.metadata.version(package_name) if installed else None
    except importlib.metadata.PackageNotFoundError:
        version = None
    return {"name": package_name, "module": module_name, "level": level, "installed": installed, "version": version}


def main() -> int:
    packages = [package_record(name, level) for name, level in PACKAGES.items()]
    tools = {name: shutil.which(name) for name in ("git", "xelatex", "latexmk")}
    report = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "python": {"version": platform.python_version(), "implementation": platform.python_implementation()},
        "platform": platform.platform(),
        "packages": packages,
        "tools": tools,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    missing_required = [item["name"] for item in packages if item["level"] == "required" and not item["installed"]]
    missing_recommended = [item["name"] for item in packages if item["level"] == "recommended" and not item["installed"]]
    print(f"Python: {report['python']['version']}")
    print(f"Required packages missing: {', '.join(missing_required) if missing_required else 'none'}")
    print(f"Recommended packages missing: {', '.join(missing_recommended) if missing_recommended else 'none'}")
    print(f"Saved: {OUTPUT}")
    return 1 if missing_required else 0


if __name__ == "__main__":
    sys.exit(main())
