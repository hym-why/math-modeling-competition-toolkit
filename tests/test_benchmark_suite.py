from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from benchmark_suite import question_headings, run_case  # noqa: E402


class BenchmarkSuiteTests(unittest.TestCase):
    def test_question_headings_supports_chinese_and_numeric_labels(self) -> None:
        text = "题面\n问题一 分析数据\n问题 2 建立模型\n3．验证方案\n第三列是编号\n普通段落"
        self.assertEqual(question_headings(text), ["问题一 分析数据", "问题 2 建立模型", "3．验证方案"])

    def test_missing_case_file_fails_closed(self) -> None:
        case = {
            "id": "2099C",
            "year": 2099,
            "problem_pdf": "missing.pdf",
            "data_files": [],
            "output_templates": [],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("benchmark_suite.ROOT", Path(temp_dir)):
                with self.assertRaisesRegex(ValueError, "missing files"):
                    run_case(case, Path(temp_dir) / "out")


if __name__ == "__main__":
    unittest.main()
