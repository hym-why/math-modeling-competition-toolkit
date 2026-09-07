from __future__ import annotations

import json
import io
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
from contextlib import redirect_stdout


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import gatekeeper  # noqa: E402


class GatekeeperTests(unittest.TestCase):
    def make_ready_state(self) -> dict:
        state = gatekeeper.initial_state()
        for gate in ("G1", "G2", "G3", "G4", "G5"):
            state["gates"][gate]["status"] = "pass"
        return state

    def test_g6_accepts_current_audit_and_rejects_stale_audit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            state_dir = root / "state"
            state_dir.mkdir()
            evidence = root / "paper.txt"
            evidence.write_text("version 1", encoding="utf-8")
            gates_path = state_dir / "gates.json"
            gates_path.write_text(json.dumps(self.make_ready_state(), ensure_ascii=False), encoding="utf-8")
            audit_path = state_dir / "audit_report.json"
            audit_path.write_text(
                json.dumps(
                    {
                        "status": "pass",
                        "evidence_hashes": {"paper.txt": gatekeeper.sha256(evidence)},
                    }
                ),
                encoding="utf-8",
            )
            args = SimpleNamespace(
                gate="G6",
                note="reviewed",
                artifact=["state/audit_report.json"],
            )
            with (
                mock.patch.object(gatekeeper, "ROOT", root),
                mock.patch.object(gatekeeper, "STATE_FILE", gates_path),
                redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(gatekeeper.pass_gate(args), 0)
                evidence.write_text("version 2", encoding="utf-8")
                self.assertEqual(gatekeeper.pass_gate(args), 1)


if __name__ == "__main__":
    unittest.main()
