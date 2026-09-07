from __future__ import annotations

import sys
import tempfile
import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import run_experiment  # noqa: E402
from run_experiment import parse_parameters, safe_name  # noqa: E402


class ExperimentHelperTests(unittest.TestCase):
    def test_parameter_parser(self) -> None:
        self.assertEqual(parse_parameters(["alpha=0.2", "method = baseline"]), {"alpha": "0.2", "method": "baseline"})

    def test_parameter_without_equals_fails(self) -> None:
        with self.assertRaises(ValueError):
            parse_parameters(["alpha"])

    def test_safe_name_removes_path_characters(self) -> None:
        self.assertEqual(safe_name("Q1 / baseline"), "Q1-baseline")

    def test_main_records_successful_experiment(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "code").mkdir()
            (root / "data").mkdir()
            (root / "outputs").mkdir()
            entry = root / "code" / "demo.py"
            entry.write_text(
                "from pathlib import Path\n"
                "Path('outputs/result.txt').write_text('42', encoding='utf-8')\n"
                "print('done')\n",
                encoding="utf-8",
            )
            argv = ["run_experiment.py", "--name", "smoke", "--entry", str(entry)]
            with (
                mock.patch.object(run_experiment, "ROOT", root),
                mock.patch.object(run_experiment, "EXPERIMENTS", root / "experiments"),
                mock.patch.object(sys, "argv", argv),
                redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(run_experiment.main(), 0)
            manifests = list((root / "experiments").glob("*/manifest.json"))
            self.assertEqual(len(manifests), 1)
            self.assertIn('"return_code": 0', manifests[0].read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
