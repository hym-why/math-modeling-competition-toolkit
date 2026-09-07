"""Reproducible audit of the closed-book green-logistics trial outputs.

This script does not optimize routes. It reloads the saved candidate solutions and
checks modeling choices that became visible when comparing them with the official
excellent-paper set.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

import pandas as pd

import green_logistics_trial as trial


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "outputs" / "green_logistics_trial"
DEFAULT_AUDIT = ROOT / "outputs" / "green_logistics_official_audit.json"
TURNAROUND_MINUTES = 20.0


def parse_path(value: str) -> list[int]:
    nodes = [int(part) for part in value.split("-")]
    if len(nodes) < 2 or nodes[0] != 0 or nodes[-1] != 0:
        raise ValueError(f"Invalid depot route: {value}")
    return nodes[1:-1]


def load_saved_routes(name: str, output_dir: Path) -> list[trial.Route]:
    route_frame = pd.read_csv(output_dir / f"{name}_routes.csv")
    stop_frame = pd.read_csv(output_dir / f"{name}_stops.csv")
    deliveries: dict[int, dict[int, tuple[float, float]]] = defaultdict(dict)
    for row in stop_frame.itertuples(index=False):
        deliveries[int(row.route_id)][int(row.customer)] = (
            float(row.delivered_weight_kg),
            float(row.delivered_volume_m3),
        )

    routes: list[trial.Route] = []
    for row in route_frame.itertuples(index=False):
        routes.append(
            trial.Route(
                vehicle=trial.VEHICLE_BY_NAME[str(row.vehicle_type)],
                order=parse_path(str(row.path)),
                deliveries=deliveries[int(row.route_id)],
                departure=trial.parse_clock(row.departure),
            )
        )
    return routes


def physical_vehicle_schedule(route_frame: pd.DataFrame) -> dict[str, object]:
    """Greedily interval-partition trips; this is optimal for identical vehicles."""
    by_type: dict[str, dict[str, object]] = {}
    total_physical = 0
    for vehicle_type, group in route_frame.groupby("vehicle_type"):
        intervals = sorted(
            (
                trial.parse_clock(row.departure),
                trial.parse_clock(row.return_) + TURNAROUND_MINUTES,
            )
            for row in group.rename(columns={"return": "return_"}).itertuples(index=False)
        )
        available: list[float] = []
        for start, end_with_turnaround in intervals:
            compatible = [index for index, end in enumerate(available) if end <= start + 1e-9]
            if compatible:
                index = max(compatible, key=lambda item: available[item])
                available[index] = end_with_turnaround
            else:
                available.append(end_with_turnaround)
        count = len(available)
        total_physical += count
        by_type[str(vehicle_type)] = {
            "trips": int(len(intervals)),
            "minimum_physical_vehicles_for_saved_timing": count,
        }
    return {
        "turnaround_minutes": TURNAROUND_MINUTES,
        "trips": int(len(route_frame)),
        "minimum_physical_vehicles_for_saved_timing": total_physical,
        "avoidable_start_charges_if_one_charge_per_physical_vehicle": float(
            (len(route_frame) - total_physical) * trial.START_COST
        ),
        "by_type": by_type,
    }


def segment_inside_circle_interval(
    start: tuple[float, float], end: tuple[float, float], radius: float = 10.0
) -> tuple[float, float] | None:
    dx, dy = end[0] - start[0], end[1] - start[1]
    a = dx * dx + dy * dy
    if a <= 1e-12:
        return (0.0, 1.0) if math.hypot(*start) <= radius else None
    b = 2.0 * (start[0] * dx + start[1] * dy)
    c = start[0] ** 2 + start[1] ** 2 - radius**2
    discriminant = b * b - 4.0 * a * c
    start_inside = c <= 0.0
    end_inside = end[0] ** 2 + end[1] ** 2 <= radius**2
    if discriminant < 0.0:
        return (0.0, 1.0) if start_inside and end_inside else None
    root = math.sqrt(max(0.0, discriminant))
    roots = sorted(((-b - root) / (2.0 * a), (-b + root) / (2.0 * a)))
    lo = 0.0 if start_inside else roots[0]
    hi = 1.0 if end_inside else roots[1]
    lo, hi = max(0.0, lo), min(1.0, hi)
    return (lo, hi) if lo <= hi and hi >= 0.0 and lo <= 1.0 else None


def green_arc_audit(
    route_frame: pd.DataFrame,
    stop_frame: pd.DataFrame,
    coords: dict[int, tuple[float, float]],
) -> dict[str, object]:
    route_info = route_frame.set_index("route_id")
    violations: list[dict[str, object]] = []
    checked = 0
    for route_id, stops in stop_frame.groupby("route_id"):
        info = route_info.loc[route_id]
        if info["power"] != "fuel":
            continue
        previous_departure = trial.parse_clock(info["departure"])
        previous_customer = 0
        ordered = stops.sort_values("sequence")
        for stop in ordered.itertuples(index=False):
            arrival = float(stop.arrival_raw_min)
            interval = segment_inside_circle_interval(
                coords[previous_customer], coords[int(stop.customer)]
            )
            checked += 1
            if interval is not None:
                inside_start = previous_departure + interval[0] * (arrival - previous_departure)
                inside_end = previous_departure + interval[1] * (arrival - previous_departure)
                if inside_start < trial.POLICY_END and inside_end > trial.DEPOT_OPEN:
                    violations.append(
                        {
                            "route_id": int(route_id),
                            "from": previous_customer,
                            "to": int(stop.customer),
                            "estimated_inside_start": trial.fmt_clock(inside_start),
                            "estimated_inside_end": trial.fmt_clock(inside_end),
                        }
                    )
            previous_departure = float(stop.departure_min)
            previous_customer = int(stop.customer)

        return_start = previous_departure
        return_arrival = trial.parse_clock(info["return"])
        interval = segment_inside_circle_interval(coords[previous_customer], coords[0])
        checked += 1
        if interval is not None:
            inside_start = return_start + interval[0] * (return_arrival - return_start)
            inside_end = return_start + interval[1] * (return_arrival - return_start)
            if inside_start < trial.POLICY_END and inside_end > trial.DEPOT_OPEN:
                violations.append(
                    {
                        "route_id": int(route_id),
                        "from": previous_customer,
                        "to": 0,
                        "estimated_inside_start": trial.fmt_clock(inside_start),
                        "estimated_inside_end": trial.fmt_clock(inside_end),
                    }
                )
    return {
        "method": "straight-line chord proxy because road geometries are unavailable",
        "fuel_arcs_checked": checked,
        "estimated_restricted_period_crossings": len(violations),
        "affected_routes": len({item["route_id"] for item in violations}),
        "examples": violations[:20],
    }


def corrected_electric_energy_audit(
    routes: list[trial.Route], data: dict[str, object], green: set[int], policy: bool
) -> dict[str, float]:
    old_summary, _ = trial.summarize_routes(routes, data, green, policy)
    original = trial.energy_rate

    def corrected(power: str, speed: float) -> float:
        if power == "fuel":
            return 0.0025 * speed**2 - 0.2554 * speed + 31.75
        return 0.0014 * speed**2 - 0.12 * speed + 36.19

    trial.energy_rate = corrected
    try:
        corrected_summary, _ = trial.summarize_routes(routes, data, green, policy)
    finally:
        trial.energy_rate = original
    return {
        "reported_total_cost": float(old_summary["total_cost"]),
        "corrected_total_cost_on_same_routes": float(corrected_summary["total_cost"]),
        "total_cost_difference": float(corrected_summary["total_cost"] - old_summary["total_cost"]),
        "reported_emissions_kg": float(old_summary["emissions_kg"]),
        "corrected_emissions_kg": float(corrected_summary["emissions_kg"]),
        "emissions_difference_kg": float(
            corrected_summary["emissions_kg"] - old_summary["emissions_kg"]
        ),
    }


def late_speed_gap_audit(
    routes: list[trial.Route], data: dict[str, object], green: set[int], policy: bool
) -> dict[str, float | str]:
    """Compare the current 17:00+ extrapolation with one official-paper scenario."""
    current_summary, _ = trial.summarize_routes(routes, data, green, policy)
    original = trial.traffic_state

    def alternate(minute: float) -> tuple[str, float, float]:
        if minute < 17.0 * 60.0:
            return original(minute)
        if minute < 18.0 * 60.0:
            return "congested", 9.8, 18.0 * 60.0
        if minute < 20.0 * 60.0:
            return "normal", 35.4, 20.0 * 60.0
        return "smooth", 55.3, float("inf")

    trial.traffic_state = alternate
    try:
        alternate_summary, _ = trial.summarize_routes(routes, data, green, policy)
    finally:
        trial.traffic_state = original
    return {
        "comparison_scenario": "17:00-18:00 congested, 18:00-20:00 normal, then smooth",
        "reported_total_cost": float(current_summary["total_cost"]),
        "scenario_total_cost_on_same_routes": float(alternate_summary["total_cost"]),
        "total_cost_difference": float(
            alternate_summary["total_cost"] - current_summary["total_cost"]
        ),
        "reported_late_hours": float(current_summary["late_hours"]),
        "scenario_late_hours": float(alternate_summary["late_hours"]),
        "late_hours_difference": float(
            alternate_summary["late_hours"] - current_summary["late_hours"]
        ),
    }


def dynamic_state_audit(output_dir: Path) -> dict[str, object]:
    event = json.loads((output_dir / "q3_event.json").read_text(encoding="utf-8"))
    event_minute = trial.parse_clock(event["event_time"])
    before_routes = pd.read_csv(output_dir / "q2_candidate_routes.csv").set_index("route_id")
    before_stops = pd.read_csv(output_dir / "q2_candidate_stops.csv")
    after_routes = pd.read_csv(output_dir / "q3_dynamic_routes.csv")
    after_stops = pd.read_csv(output_dir / "q3_dynamic_stops.csv")

    new_customer = int(event["new_customer"])
    new_stop_rows = after_stops[after_stops["customer"] == new_customer]
    new_order_insertions: list[dict[str, object]] = []
    for stop in new_stop_rows.itertuples(index=False):
        route_id = int(stop.route_id)
        route = after_routes[after_routes["route_id"] == route_id].iloc[0]
        departure = trial.parse_clock(route["departure"])
        new_order_insertions.append(
            {
                "route_id": route_id,
                "route_departure": route["departure"],
                "departed_before_event": departure < event_minute,
                "path_after_replan": route["path"],
            }
        )

    cancel_customer = int(event["cancelled_customer"])
    cancelled_stops = before_stops[before_stops["customer"] == cancel_customer]
    cancellation_on_departed_trips: list[dict[str, object]] = []
    for stop in cancelled_stops.itertuples(index=False):
        route = before_routes.loc[int(stop.route_id)]
        departure = trial.parse_clock(route["departure"])
        if departure < event_minute:
            cancellation_on_departed_trips.append(
                {
                    "route_id": int(stop.route_id),
                    "route_departure": route["departure"],
                    "cancelled_delivery_weight_kg": float(stop.delivered_weight_kg),
                    "cancelled_delivery_volume_m3": float(stop.delivered_volume_m3),
                }
            )
    return {
        "event_time": event["event_time"],
        "new_order_insertions": new_order_insertions,
        "new_order_loaded_onto_already_departed_route": any(
            item["departed_before_event"] for item in new_order_insertions
        ),
        "cancelled_deliveries_on_already_departed_routes": cancellation_on_departed_trips,
        "audit_note": (
            "The current full-day recomputation removes cancelled cargo from route load even "
            "when that cargo was already aboard at departure."
        ),
    }


def imputation_audit(data_dir: Path) -> dict[str, object]:
    orders = pd.read_excel(data_dir / "订单信息.xlsx")
    complete = orders.dropna(subset=["重量", "体积"]).copy()
    positive_volume = complete[complete["体积"] > 0]
    density = float((positive_volume["重量"] / positive_volume["体积"]).median())

    alternative = orders.copy()
    weight_missing = alternative["重量"].isna() & alternative["体积"].notna()
    volume_missing = alternative["体积"].isna() & alternative["重量"].notna()
    alternative.loc[weight_missing, "重量"] = alternative.loc[weight_missing, "体积"] * density
    alternative.loc[volume_missing, "体积"] = alternative.loc[volume_missing, "重量"] / density
    alternative["重量"] = alternative["重量"].fillna(complete["重量"].median())
    alternative["体积"] = alternative["体积"].fillna(complete["体积"].median())

    current = trial.load_inputs(data_dir)["orders"]
    return {
        "complete_row_median_density_kg_per_m3": density,
        "current_independent_median_totals": {
            "weight_kg": float(current["重量"].sum()),
            "volume_m3": float(current["体积"].sum()),
        },
        "density_linked_totals": {
            "weight_kg": float(alternative["重量"].sum()),
            "volume_m3": float(alternative["体积"].sum()),
        },
        "difference_density_minus_current": {
            "weight_kg": float(alternative["重量"].sum() - current["重量"].sum()),
            "volume_m3": float(alternative["体积"].sum() - current["体积"].sum()),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit saved green-logistics trial results")
    parser.add_argument("--data-dir", type=Path, default=trial.DEFAULT_DATA)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit-file", type=Path, default=DEFAULT_AUDIT)
    args = parser.parse_args()

    data = trial.load_inputs(args.data_dir)
    results: dict[str, object] = {
        "imputation": imputation_audit(args.data_dir),
        "dynamic_state": dynamic_state_audit(args.output_dir),
        "solutions": {},
    }
    for name, policy in (("q1_candidate", False), ("q2_candidate", True)):
        route_frame = pd.read_csv(args.output_dir / f"{name}_routes.csv")
        stop_frame = pd.read_csv(args.output_dir / f"{name}_stops.csv")
        routes = load_saved_routes(name, args.output_dir)
        green = data["green_geometry"]
        assert isinstance(green, set)
        entry: dict[str, object] = {
            "corrected_electric_formula": corrected_electric_energy_audit(
                routes, data, green, policy
            ),
            "late_speed_gap": late_speed_gap_audit(routes, data, green, policy),
            "multi_trip": physical_vehicle_schedule(route_frame),
        }
        if policy:
            coords = data["coords"]
            assert isinstance(coords, dict)
            entry["green_arc_policy"] = green_arc_audit(route_frame, stop_frame, coords)
        results["solutions"][name] = entry

    args.audit_file.parent.mkdir(parents=True, exist_ok=True)
    args.audit_file.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
