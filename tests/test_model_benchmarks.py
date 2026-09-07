from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from model_benchmarks import artifact_id, midpoint_price, wape  # noqa: E402


class ModelBenchmarkTests(unittest.TestCase):
    def test_artifact_id_uses_leading_number(self) -> None:
        self.assertEqual(artifact_id("03部位2"), 3)
        self.assertIsNone(artifact_id("A1"))

    def test_midpoint_price(self) -> None:
        self.assertEqual(midpoint_price("2.50-4.00"), 3.25)

    def test_wape(self) -> None:
        self.assertAlmostEqual(wape(np.array([10.0, 20.0]), np.array([8.0, 24.0])), 0.2)


if __name__ == "__main__":
    unittest.main()
