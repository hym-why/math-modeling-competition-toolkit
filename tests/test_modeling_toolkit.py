from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


CODE = Path(__file__).resolve().parents[1] / "code"
sys.path.insert(0, str(CODE))

from modeling_toolkit import (  # noqa: E402
    clr_transform,
    empirical_cvar,
    gestational_week,
    valid_composition_mask,
)


class ModelingToolkitTests(unittest.TestCase):
    def test_composition_validation_and_clr(self) -> None:
        frame = pd.DataFrame({"a": [50.0, 40.0], "b": [50.0, 0.0]})
        self.assertEqual(valid_composition_mask(frame).tolist(), [True, False])
        transformed = clr_transform(frame)
        np.testing.assert_allclose(transformed.sum(axis=1), 0.0, atol=1e-10)
        self.assertTrue(np.isfinite(transformed.to_numpy()).all())

    def test_empirical_cvar_uses_worst_tail(self) -> None:
        self.assertEqual(empirical_cvar([1, 2, 3, 100], alpha=0.75), 100.0)

    def test_gestational_week(self) -> None:
        self.assertAlmostEqual(gestational_week("12w+3"), 12 + 3 / 7)
        self.assertAlmostEqual(gestational_week("20周"), 20.0)
        self.assertTrue(np.isnan(gestational_week("unknown")))


if __name__ == "__main__":
    unittest.main()
