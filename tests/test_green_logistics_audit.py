from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from audit_green_logistics_comparison import (  # noqa: E402
    physical_vehicle_schedule,
    segment_inside_circle_interval,
)


class GreenLogisticsAuditTests(unittest.TestCase):
    def test_multitrip_schedule_reuses_compatible_vehicle(self) -> None:
        routes = pd.DataFrame(
            [
                {"route_id": 1, "vehicle_type": "Fuel-1250", "departure": "08:00", "return": "09:00"},
                {"route_id": 2, "vehicle_type": "Fuel-1250", "departure": "09:20", "return": "10:00"},
                {"route_id": 3, "vehicle_type": "Fuel-1250", "departure": "08:30", "return": "09:30"},
            ]
        )
        result = physical_vehicle_schedule(routes)
        self.assertEqual(result["trips"], 3)
        self.assertEqual(result["minimum_physical_vehicles_for_saved_timing"], 2)
        self.assertEqual(result["avoidable_start_charges_if_one_charge_per_physical_vehicle"], 400.0)

    def test_circle_intersection_detects_crossing(self) -> None:
        interval = segment_inside_circle_interval((-20.0, 0.0), (20.0, 0.0))
        self.assertIsNotNone(interval)
        assert interval is not None
        self.assertAlmostEqual(interval[0], 0.25)
        self.assertAlmostEqual(interval[1], 0.75)

    def test_circle_intersection_rejects_external_segment(self) -> None:
        self.assertIsNone(segment_inside_circle_interval((20.0, 20.0), (30.0, 20.0)))


if __name__ == "__main__":
    unittest.main()
