from __future__ import annotations

import tempfile
import sys
import unittest
from pathlib import Path

import pandas as pd


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from data_contract import create_contract, verify_contract  # noqa: E402


class DataContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.data_file = self.root / "sample.csv"
        self.contract_file = self.root / "data_contract.json"
        pd.DataFrame({"id": [1, 2, 3], "value": [2.0, None, 4.0]}).to_csv(self.data_file, index=False)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_contract_profiles_and_verifies_csv(self) -> None:
        contract = create_contract([self.data_file], self.contract_file)
        self.assertEqual(contract["files"][0]["tables"][0]["rows"], 3)
        self.assertEqual(verify_contract(self.contract_file), [])

    def test_changed_input_is_detected(self) -> None:
        create_contract([self.data_file], self.contract_file)
        self.data_file.write_text("id,value\n1,99\n", encoding="utf-8")
        self.assertIn(f"Input changed: {self.data_file}", verify_contract(self.contract_file))


if __name__ == "__main__":
    unittest.main()
