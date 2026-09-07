from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from result_freeze import freeze, verify  # noqa: E402


class ResultFreezeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.outputs = self.root / "outputs"
        self.outputs.mkdir()
        self.manifest = self.root / "state" / "frozen_results.json"
        (self.outputs / "result.csv").write_text("id,score\n1,0.8\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_unchanged_outputs_pass(self) -> None:
        freeze(self.outputs, self.manifest)
        self.assertEqual(verify(self.outputs, self.manifest), [])

    def test_changed_file_is_detected(self) -> None:
        freeze(self.outputs, self.manifest)
        (self.outputs / "result.csv").write_text("id,score\n1,0.9\n", encoding="utf-8")
        self.assertIn("Changed after freeze: result.csv", verify(self.outputs, self.manifest))

    def test_added_and_deleted_files_are_detected(self) -> None:
        freeze(self.outputs, self.manifest)
        (self.outputs / "result.csv").unlink()
        (self.outputs / "figure.png").write_bytes(b"not-a-real-image")
        issues = verify(self.outputs, self.manifest)
        self.assertIn("Deleted after freeze: result.csv", issues)
        self.assertIn("Added after freeze: figure.png", issues)


if __name__ == "__main__":
    unittest.main()
