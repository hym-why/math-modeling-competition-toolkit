from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from green_logistics_trial import (  # noqa: E402
    POLICY_END,
    Route,
    VEHICLE_BY_NAME,
    energy_rate,
    evaluate_route,
    travel_segments,
)


class GreenLogisticsTrialTests(unittest.TestCase):
    def test_travel_segments_crosses_traffic_boundary(self) -> None:
        minutes, segments = travel_segments(20.0, 8 * 60)
        self.assertGreater(minutes, 60.0)
        self.assertEqual(segments[0][1], 9.8)
        self.assertAlmostEqual(sum(distance for distance, _ in segments), 20.0, places=8)

    def test_energy_rate_is_positive(self) -> None:
        for speed in (3.0, 9.8, 35.4, 55.3, 90.0):
            self.assertGreater(energy_rate("fuel", speed), 0.0)
            self.assertGreater(energy_rate("electric", speed), 0.0)

    def test_policy_delays_fuel_service_to_1600(self) -> None:
        distances = np.array([[0.0, 1.0], [1.0, 0.0]])
        route = Route(
            vehicle=VEHICLE_BY_NAME["Fuel-1250"],
            order=[1],
            deliveries={1: (100.0, 1.0)},
        )
        result = evaluate_route(route, distances, {1: (9 * 60, 10 * 60)}, {1}, True)
        self.assertGreaterEqual(result["stops"][0]["service_start_min"], POLICY_END)


if __name__ == "__main__":
    unittest.main()
