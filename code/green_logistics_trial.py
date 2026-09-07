"""Closed-book trial for the urban green logistics scheduling problem.

The solver intentionally uses only the supplied statement and four input files.
It implements a transparent split-delivery, heterogeneous-fleet VRP heuristic with
time-dependent travel, soft time windows, energy/carbon costs, policy constraints,
multi-start insertion, local search, and a rolling-horizon event demonstration.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import os
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

os.environ.setdefault(
    "MPLCONFIGDIR",
    str(Path(__file__).resolve().parents[1] / "state" / "matplotlib"),
)

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "data" / "green_logistics_A"
DEFAULT_OUTPUT = ROOT / "outputs" / "green_logistics_trial"
SERVICE_MINUTES = 20.0
DEPOT_OPEN = 8.0 * 60.0
POLICY_END = 16.0 * 60.0
WAIT_COST_PER_HOUR = 20.0
LATE_COST_PER_HOUR = 50.0
START_COST = 400.0
CARBON_PRICE = 0.65


@dataclass(frozen=True)
class VehicleType:
    name: str
    power: str
    capacity_weight: float
    capacity_volume: float
    count: int
    load_increase: float
    energy_price: float
    carbon_factor: float


VEHICLES = (
    VehicleType("EV-3000", "electric", 3000.0, 15.0, 10, 0.35, 1.64, 0.501),
    VehicleType("Fuel-3000", "fuel", 3000.0, 13.5, 60, 0.40, 7.61, 2.547),
    VehicleType("Fuel-1500", "fuel", 1500.0, 10.8, 50, 0.40, 7.61, 2.547),
    VehicleType("EV-1250", "electric", 1250.0, 8.5, 15, 0.35, 1.64, 0.501),
    VehicleType("Fuel-1250", "fuel", 1250.0, 6.5, 50, 0.40, 7.61, 2.547),
)
VEHICLE_BY_NAME = {vehicle.name: vehicle for vehicle in VEHICLES}


@dataclass
class Route:
    vehicle: VehicleType
    order: list[int] = field(default_factory=list)
    deliveries: dict[int, tuple[float, float]] = field(default_factory=dict)
    min_departure: float = DEPOT_OPEN
    departure: float | None = None
    locked_prefix: int = 0

    def clone(self) -> "Route":
        return Route(
            vehicle=self.vehicle,
            order=list(self.order),
            deliveries=dict(self.deliveries),
            min_departure=self.min_departure,
            departure=self.departure,
            locked_prefix=self.locked_prefix,
        )

    @property
    def load_weight(self) -> float:
        return sum(value[0] for value in self.deliveries.values())

    @property
    def load_volume(self) -> float:
        return sum(value[1] for value in self.deliveries.values())


def parse_clock(value: object) -> float:
    text = str(value).strip()
    hour, minute = text.split(":")[:2]
    return float(int(hour) * 60 + int(minute))


def fmt_clock(minutes: float) -> str:
    total = int(round(minutes))
    return f"{total // 60:02d}:{total % 60:02d}"


def load_inputs(data_dir: Path) -> dict[str, object]:
    orders = pd.read_excel(data_dir / "订单信息.xlsx")
    distance_frame = pd.read_excel(data_dir / "距离矩阵.xlsx")
    coordinates = pd.read_excel(data_dir / "客户坐标信息.xlsx")
    windows_frame = pd.read_excel(data_dir / "时间窗.xlsx")

    missing_before = {column: int(orders[column].isna().sum()) for column in ("重量", "体积")}
    for column in ("重量", "体积"):
        grouped_median = orders.groupby("目标客户编号")[column].transform("median")
        orders[column] = orders[column].fillna(grouped_median).fillna(orders[column].median())

    demands_frame = (
        orders.groupby("目标客户编号")[["重量", "体积"]]
        .sum()
        .reindex(range(1, 99), fill_value=0.0)
    )
    demands = {
        int(customer): (float(row["重量"]), float(row["体积"]))
        for customer, row in demands_frame.iterrows()
    }

    distance_frame = distance_frame.set_index("客户")
    distance_frame.columns = [int(column) for column in distance_frame.columns]
    ids = list(range(99))
    distances = distance_frame.loc[ids, ids].to_numpy(dtype=float)

    coordinates = coordinates.set_index("ID")
    coords = {
        int(customer): (float(row["X (km)"]), float(row["Y (km)"]))
        for customer, row in coordinates.iterrows()
    }
    radii = {customer: math.hypot(*coords[customer]) for customer in range(1, 99)}
    green_geometry = {customer for customer, radius in radii.items() if radius <= 10.0 + 1e-12}
    green_30_nearest = set(sorted(radii, key=radii.get)[:30])

    windows = {
        int(row["客户编号"]): (parse_clock(row["开始时间"]), parse_clock(row["结束时间"]))
        for _, row in windows_frame.iterrows()
    }
    active = {customer for customer, demand in demands.items() if demand[0] > 0 or demand[1] > 0}

    audit = {
        "orders": int(len(orders)),
        "customers": 98,
        "active_customers": int(len(active)),
        "zero_demand_customers": sorted(set(range(1, 99)) - active),
        "missing_before_imputation": missing_before,
        "missing_after_imputation": {
            column: int(orders[column].isna().sum()) for column in ("重量", "体积")
        },
        "total_weight_kg": float(demands_frame["重量"].sum()),
        "total_volume_m3": float(demands_frame["体积"].sum()),
        "customers_exceeding_largest_vehicle": int(
            ((demands_frame["重量"] > 3000.0) | (demands_frame["体积"] > 15.0)).sum()
        ),
        "green_by_radius_10km": len(green_geometry),
        "statement_green_count": 30,
        "distance_symmetric_max_error": float(np.abs(distances - distances.T).max()),
        "distance_diagonal_max_abs": float(np.abs(np.diag(distances)).max()),
    }
    return {
        "orders": orders,
        "demands": demands,
        "distances": distances,
        "coords": coords,
        "windows": windows,
        "green_geometry": green_geometry,
        "green_30_nearest": green_30_nearest,
        "audit": audit,
    }


def traffic_state(minute: float) -> tuple[str, float, float]:
    if minute < 480:
        return "smooth", 55.3, 480.0
    if minute < 540:
        return "congested", 9.8, 540.0
    if minute < 600:
        return "smooth", 55.3, 600.0
    if minute < 690:
        return "normal", 35.4, 690.0
    if minute < 780:
        return "congested", 9.8, 780.0
    if minute < 900:
        return "smooth", 55.3, 900.0
    if minute < 1020:
        return "normal", 35.4, 1020.0
    return "smooth", 55.3, float("inf")


def travel_segments(
    distance_km: float,
    departure_minute: float,
    sampled_speeds: dict[str, float] | None = None,
) -> tuple[float, list[tuple[float, float]]]:
    remaining = float(distance_km)
    minute = float(departure_minute)
    segments: list[tuple[float, float]] = []
    while remaining > 1e-10:
        state, mean_speed, boundary = traffic_state(minute)
        speed = float(sampled_speeds.get(state, mean_speed)) if sampled_speeds else mean_speed
        speed = max(speed, 3.0)
        possible = remaining if math.isinf(boundary) else speed * max(boundary - minute, 0.0) / 60.0
        covered = min(remaining, possible)
        if covered <= 1e-12:
            minute = boundary + 1e-9
            continue
        segments.append((covered, speed))
        minute += covered / speed * 60.0
        remaining -= covered
    return minute - departure_minute, segments


def energy_rate(power: str, speed: float) -> float:
    if power == "fuel":
        return 0.0025 * speed**2 - 0.2554 * speed + 31.75
    return 0.001 * speed**2 - 0.1 * speed + 36.194


def route_metrics_at_departure(
    route: Route,
    distances: np.ndarray,
    windows: dict[int, tuple[float, float]],
    green: set[int],
    policy: bool,
    departure: float,
    sampled_speeds: dict[str, float] | None = None,
) -> dict[str, object]:
    vehicle = route.vehicle
    remaining_weight = route.load_weight
    remaining_volume = route.load_volume
    minute = departure
    previous = 0
    total_distance = 0.0
    energy = 0.0
    emissions = 0.0
    wait_minutes = 0.0
    late_minutes = 0.0
    stops: list[dict[str, object]] = []

    for sequence, customer in enumerate(route.order, start=1):
        leg = float(distances[previous, customer])
        travel_min, segments = travel_segments(leg, minute, sampled_speeds)
        utilization = max(
            remaining_weight / vehicle.capacity_weight,
            remaining_volume / vehicle.capacity_volume,
        )
        utilization = min(max(utilization, 0.0), 1.0)
        multiplier = 1.0 + vehicle.load_increase * utilization
        leg_energy = sum(distance / 100.0 * energy_rate(vehicle.power, speed) * multiplier for distance, speed in segments)
        energy += leg_energy
        emissions += leg_energy * vehicle.carbon_factor
        total_distance += leg
        raw_arrival = minute + travel_min
        earliest, latest = windows[customer]
        policy_floor = POLICY_END if policy and vehicle.power == "fuel" and customer in green else -float("inf")
        service_start = max(raw_arrival, earliest, policy_floor)
        wait = max(0.0, service_start - raw_arrival)
        late = max(0.0, service_start - latest)
        wait_minutes += wait
        late_minutes += late
        delivered_weight, delivered_volume = route.deliveries[customer]
        departure_customer = service_start + SERVICE_MINUTES
        stops.append(
            {
                "sequence": sequence,
                "customer": customer,
                "from_customer": previous,
                "leg_distance_km": leg,
                "arrival_raw_min": raw_arrival,
                "service_start_min": service_start,
                "departure_min": departure_customer,
                "wait_min": wait,
                "late_min": late,
                "delivered_weight_kg": delivered_weight,
                "delivered_volume_m3": delivered_volume,
                "remaining_weight_before_kg": remaining_weight,
                "remaining_volume_before_m3": remaining_volume,
                "leg_energy": leg_energy,
            }
        )
        remaining_weight -= delivered_weight
        remaining_volume -= delivered_volume
        minute = departure_customer
        previous = customer

    return_leg = float(distances[previous, 0]) if route.order else 0.0
    return_min, segments = travel_segments(return_leg, minute, sampled_speeds)
    return_energy = sum(distance / 100.0 * energy_rate(vehicle.power, speed) for distance, speed in segments)
    energy += return_energy
    emissions += return_energy * vehicle.carbon_factor
    total_distance += return_leg
    return_time = minute + return_min
    energy_cost = energy * vehicle.energy_price
    carbon_cost = emissions * CARBON_PRICE
    waiting_cost = wait_minutes / 60.0 * WAIT_COST_PER_HOUR
    lateness_cost = late_minutes / 60.0 * LATE_COST_PER_HOUR
    objective = START_COST + energy_cost + carbon_cost + waiting_cost + lateness_cost
    return {
        "objective": objective,
        "start_cost": START_COST,
        "energy_cost": energy_cost,
        "carbon_cost": carbon_cost,
        "waiting_cost": waiting_cost,
        "lateness_cost": lateness_cost,
        "distance_km": total_distance,
        "energy": energy,
        "emissions_kg": emissions,
        "wait_minutes": wait_minutes,
        "late_minutes": late_minutes,
        "departure_min": departure,
        "return_min": return_time,
        "stops": stops,
    }


def evaluate_route(
    route: Route,
    distances: np.ndarray,
    windows: dict[int, tuple[float, float]],
    green: set[int],
    policy: bool,
    optimize_departure: bool = False,
    sampled_speeds: dict[str, float] | None = None,
) -> dict[str, object]:
    if not route.order:
        return {
            "objective": 0.0,
            "start_cost": 0.0,
            "energy_cost": 0.0,
            "carbon_cost": 0.0,
            "waiting_cost": 0.0,
            "lateness_cost": 0.0,
            "distance_km": 0.0,
            "energy": 0.0,
            "emissions_kg": 0.0,
            "wait_minutes": 0.0,
            "late_minutes": 0.0,
            "departure_min": route.min_departure,
            "return_min": route.min_departure,
            "stops": [],
        }
    if route.departure is not None or not optimize_departure:
        departure = route.departure if route.departure is not None else route.min_departure
        return route_metrics_at_departure(
            route, distances, windows, green, policy, departure, sampled_speeds
        )

    latest_candidate = min(max(windows[customer][1] for customer in route.order), 20.0 * 60.0)
    candidates = np.arange(route.min_departure, max(route.min_departure, latest_candidate) + 0.1, 15.0)
    best = None
    for departure in candidates:
        result = route_metrics_at_departure(
            route, distances, windows, green, policy, float(departure), sampled_speeds
        )
        if best is None or float(result["objective"]) < float(best["objective"]):
            best = result
    assert best is not None
    return best


def fits(route: Route, add_weight: float = 0.0, add_volume: float = 0.0) -> bool:
    return (
        route.load_weight + add_weight <= route.vehicle.capacity_weight + 1e-7
        and route.load_volume + add_volume <= route.vehicle.capacity_volume + 1e-9
    )


def split_demands(demands: dict[int, tuple[float, float]]) -> dict[int, list[tuple[float, float]]]:
    pieces: dict[int, list[tuple[float, float]]] = {}
    for customer, (weight, volume) in demands.items():
        if weight <= 0 and volume <= 0:
            continue
        count = max(1, math.ceil(max(weight / 1250.0, volume / 6.5) - 1e-12))
        pieces[customer] = [(weight / count, volume / count) for _ in range(count)]
    return pieces


def used_vehicle_counts(routes: Iterable[Route]) -> Counter[str]:
    return Counter(route.vehicle.name for route in routes if route.order)


def insertion_candidates(route: Route, customer: int, all_positions: bool) -> list[int]:
    if customer in route.deliveries:
        return [-1]
    if not all_positions:
        return [len(route.order)]
    return list(range(route.locked_prefix, len(route.order) + 1))


def with_piece(route: Route, customer: int, piece: tuple[float, float], position: int) -> Route:
    candidate = route.clone()
    old_weight, old_volume = candidate.deliveries.get(customer, (0.0, 0.0))
    candidate.deliveries[customer] = (old_weight + piece[0], old_volume + piece[1])
    if customer not in candidate.order:
        candidate.order.insert(position, customer)
    candidate.departure = None if candidate.locked_prefix == 0 else candidate.departure
    return candidate


def customer_orders(
    pieces: dict[int, list[tuple[float, float]]],
    windows: dict[int, tuple[float, float]],
    coords: dict[int, tuple[float, float]],
    green: set[int],
    policy: bool,
    variant: int,
    rng: np.random.Generator,
) -> list[int]:
    customers = list(pieces)
    if variant == 0:
        return sorted(customers, key=lambda c: (0 if policy and c in green else 1, windows[c][1], c))
    if variant == 1:
        return sorted(
            customers,
            key=lambda c: (
                0 if policy and c in green else 1,
                math.atan2(coords[c][1], coords[c][0]),
                windows[c][1],
            ),
        )
    noise = {customer: float(rng.normal(0, 120.0)) for customer in customers}
    return sorted(
        customers,
        key=lambda c: (
            0 if policy and c in green else 1,
            windows[c][1] + noise[c],
            -sum(pieces[c][0]),
        ),
    )


def construct_routes(
    demands: dict[int, tuple[float, float]],
    distances: np.ndarray,
    windows: dict[int, tuple[float, float]],
    coords: dict[int, tuple[float, float]],
    green: set[int],
    policy: bool,
    all_positions: bool,
    variant: int,
    seed: int,
) -> list[Route]:
    rng = np.random.default_rng(seed)
    pieces = split_demands(demands)
    routes: list[Route] = []
    customer_order = customer_orders(pieces, windows, coords, green, policy, variant, rng)

    for customer in customer_order:
        customer_pieces = list(pieces[customer])
        if variant >= 2:
            rng.shuffle(customer_pieces)
        for piece in customer_pieces:
            best: tuple[float, str, int, Route] | None = None
            for route_index, route in enumerate(routes):
                if not fits(route, *piece):
                    continue
                old = evaluate_route(route, distances, windows, green, policy)["objective"]
                for position in insertion_candidates(route, customer, all_positions):
                    candidate = with_piece(route, customer, piece, position)
                    new = evaluate_route(candidate, distances, windows, green, policy)["objective"]
                    choice = (float(new) - float(old), "existing", route_index, candidate)
                    if best is None or choice[0] < best[0]:
                        best = choice

            used = used_vehicle_counts(routes)
            capacity_shadow = (0.0, 0.04, 0.08, 0.12)[variant % 4] if all_positions else 0.0
            best_new: tuple[float, float, Route] | None = None
            for vehicle in VEHICLES:
                if used[vehicle.name] >= vehicle.count:
                    continue
                candidate = Route(vehicle=vehicle, order=[customer], deliveries={customer: piece})
                if not fits(candidate):
                    continue
                delta = float(evaluate_route(candidate, distances, windows, green, policy)["objective"])
                type_score = delta - capacity_shadow * (vehicle.capacity_weight - piece[0])
                new_choice = (type_score, delta, candidate)
                if best_new is None or new_choice[0] < best_new[0]:
                    best_new = new_choice
            if best_new is not None:
                choice = (best_new[1], "new", len(routes), best_new[2])
                if best is None or choice[0] < best[0]:
                    best = choice

            if best is None:
                raise RuntimeError(f"No fleet capacity remains for customer {customer}")
            if best[1] == "existing":
                routes[best[2]] = best[3]
            else:
                routes.append(best[3])
    return routes


def improve_route_order(
    route: Route,
    distances: np.ndarray,
    windows: dict[int, tuple[float, float]],
    green: set[int],
    policy: bool,
) -> Route:
    if len(route.order) < 2 or route.locked_prefix:
        return route
    best = route.clone()
    best_cost = float(evaluate_route(best, distances, windows, green, policy)["objective"])
    improved = True
    while improved:
        improved = False
        for left in range(len(best.order) - 1):
            for right in range(left + 1, len(best.order)):
                candidate = best.clone()
                candidate.order[left : right + 1] = reversed(candidate.order[left : right + 1])
                cost = float(evaluate_route(candidate, distances, windows, green, policy)["objective"])
                if cost + 1e-8 < best_cost:
                    best, best_cost, improved = candidate, cost, True
    return best


def relocate_improvement(
    routes: list[Route],
    distances: np.ndarray,
    windows: dict[int, tuple[float, float]],
    green: set[int],
    policy: bool,
    passes: int = 2,
) -> list[Route]:
    routes = [route.clone() for route in routes]
    for _ in range(passes):
        changed = False
        for source_index in sorted(range(len(routes)), key=lambda i: routes[i].load_weight):
            if source_index >= len(routes):
                continue
            source = routes[source_index]
            for customer in list(source.order):
                delivery = source.deliveries[customer]
                source_candidate = source.clone()
                source_candidate.order.remove(customer)
                del source_candidate.deliveries[customer]
                old_source_cost = float(evaluate_route(source, distances, windows, green, policy)["objective"])
                new_source_cost = float(evaluate_route(source_candidate, distances, windows, green, policy)["objective"])
                best_move: tuple[float, int, Route] | None = None
                for target_index, target in enumerate(routes):
                    if target_index == source_index or not fits(target, *delivery):
                        continue
                    old_target_cost = float(evaluate_route(target, distances, windows, green, policy)["objective"])
                    for position in insertion_candidates(target, customer, True):
                        target_candidate = with_piece(target, customer, delivery, position)
                        new_target_cost = float(
                            evaluate_route(target_candidate, distances, windows, green, policy)["objective"]
                        )
                        delta = new_source_cost + new_target_cost - old_source_cost - old_target_cost
                        if best_move is None or delta < best_move[0]:
                            best_move = (delta, target_index, target_candidate)
                if best_move is not None and best_move[0] < -1e-7:
                    routes[source_index] = source_candidate
                    routes[best_move[1]] = best_move[2]
                    source = source_candidate
                    changed = True
            routes = [route for route in routes if route.order]
        if not changed:
            break
    return routes


def improve_vehicle_types(
    routes: list[Route],
    distances: np.ndarray,
    windows: dict[int, tuple[float, float]],
    green: set[int],
    policy: bool,
) -> list[Route]:
    routes = [route.clone() for route in routes]
    counts = used_vehicle_counts(routes)
    for index, route in enumerate(routes):
        current = evaluate_route(route, distances, windows, green, policy, optimize_departure=True)
        best_route = route
        best_cost = float(current["objective"])
        for vehicle in VEHICLES:
            if vehicle.name != route.vehicle.name and counts[vehicle.name] >= vehicle.count:
                continue
            candidate = route.clone()
            candidate.vehicle = vehicle
            candidate.departure = None
            if not fits(candidate):
                continue
            result = evaluate_route(candidate, distances, windows, green, policy, optimize_departure=True)
            if float(result["objective"]) + 1e-7 < best_cost:
                best_route, best_cost = candidate, float(result["objective"])
        if best_route.vehicle.name != route.vehicle.name:
            counts[route.vehicle.name] -= 1
            counts[best_route.vehicle.name] += 1
            routes[index] = best_route
    return routes


def finalize_routes(
    routes: list[Route],
    distances: np.ndarray,
    windows: dict[int, tuple[float, float]],
    green: set[int],
    policy: bool,
) -> list[Route]:
    finalized = []
    for route in routes:
        candidate = improve_route_order(route, distances, windows, green, policy)
        result = evaluate_route(candidate, distances, windows, green, policy, optimize_departure=True)
        candidate.departure = float(result["departure_min"])
        finalized.append(candidate)
    return finalized


def solve(
    data: dict[str, object],
    green: set[int],
    policy: bool,
    method: str,
    starts: int,
    seed: int,
) -> list[Route]:
    demands = data["demands"]
    distances = data["distances"]
    windows = data["windows"]
    coords = data["coords"]
    assert isinstance(demands, dict) and isinstance(distances, np.ndarray)
    assert isinstance(windows, dict) and isinstance(coords, dict)

    if method == "baseline":
        routes = construct_routes(
            demands, distances, windows, coords, green, policy, False, 0, seed
        )
        return finalize_routes(routes, distances, windows, green, policy)

    best_routes = None
    best_cost = float("inf")
    for variant in range(starts):
        routes = construct_routes(
            demands,
            distances,
            windows,
            coords,
            green,
            policy,
            True,
            variant,
            seed + variant * 1009,
        )
        routes = relocate_improvement(routes, distances, windows, green, policy)
        routes = improve_vehicle_types(routes, distances, windows, green, policy)
        routes = finalize_routes(routes, distances, windows, green, policy)
        summary, _ = summarize_routes(routes, data, green, policy)
        if summary["total_cost"] < best_cost:
            best_cost = summary["total_cost"]
            best_routes = routes
    assert best_routes is not None
    return best_routes


def summarize_routes(
    routes: list[Route],
    data: dict[str, object],
    green: set[int],
    policy: bool,
    sampled_speeds: dict[str, float] | None = None,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    distances = data["distances"]
    windows = data["windows"]
    assert isinstance(distances, np.ndarray) and isinstance(windows, dict)
    totals = defaultdict(float)
    stop_rows: list[dict[str, object]] = []
    route_rows: list[dict[str, object]] = []
    delivered_weight = defaultdict(float)
    delivered_volume = defaultdict(float)
    policy_violations = 0
    capacity_violations = 0

    for route_id, route in enumerate(routes, start=1):
        result = evaluate_route(
            route,
            distances,
            windows,
            green,
            policy,
            optimize_departure=route.departure is None,
            sampled_speeds=sampled_speeds,
        )
        for key in (
            "objective",
            "start_cost",
            "energy_cost",
            "carbon_cost",
            "waiting_cost",
            "lateness_cost",
            "distance_km",
            "emissions_kg",
            "wait_minutes",
            "late_minutes",
        ):
            totals[key] += float(result[key])
        if route.load_weight > route.vehicle.capacity_weight + 1e-6 or route.load_volume > route.vehicle.capacity_volume + 1e-8:
            capacity_violations += 1
        for stop in result["stops"]:
            customer = int(stop["customer"])
            delivered_weight[customer] += float(stop["delivered_weight_kg"])
            delivered_volume[customer] += float(stop["delivered_volume_m3"])
            if policy and route.vehicle.power == "fuel" and customer in green and float(stop["service_start_min"]) < POLICY_END - 1e-7:
                policy_violations += 1
            stop_rows.append(
                {
                    "route_id": route_id,
                    "vehicle_type": route.vehicle.name,
                    "power": route.vehicle.power,
                    **stop,
                    "arrival_raw": fmt_clock(float(stop["arrival_raw_min"])),
                    "service_start": fmt_clock(float(stop["service_start_min"])),
                    "departure": fmt_clock(float(stop["departure_min"])),
                    "in_green_zone": customer in green,
                }
            )
        route_rows.append(
            {
                "route_id": route_id,
                "vehicle_type": route.vehicle.name,
                "power": route.vehicle.power,
                "path": "0-" + "-".join(map(str, route.order)) + "-0",
                "departure": fmt_clock(float(result["departure_min"])),
                "return": fmt_clock(float(result["return_min"])),
                "customers": len(route.order),
                "load_weight_kg": route.load_weight,
                "load_volume_m3": route.load_volume,
                "capacity_weight_kg": route.vehicle.capacity_weight,
                "capacity_volume_m3": route.vehicle.capacity_volume,
                "distance_km": result["distance_km"],
                "cost": result["objective"],
                "emissions_kg": result["emissions_kg"],
                "late_minutes": result["late_minutes"],
            }
        )

    demands = data["demands"]
    assert isinstance(demands, dict)
    demand_weight_error = max(abs(delivered_weight[c] - demands[c][0]) for c in demands)
    demand_volume_error = max(abs(delivered_volume[c] - demands[c][1]) for c in demands)
    fleet = used_vehicle_counts(routes)
    fleet_limit_violations = sum(max(0, fleet[v.name] - v.count) for v in VEHICLES)
    summary = {
        "total_cost": totals["objective"],
        "start_cost": totals["start_cost"],
        "energy_cost": totals["energy_cost"],
        "carbon_cost": totals["carbon_cost"],
        "waiting_cost": totals["waiting_cost"],
        "lateness_cost": totals["lateness_cost"],
        "distance_km": totals["distance_km"],
        "emissions_kg": totals["emissions_kg"],
        "wait_hours": totals["wait_minutes"] / 60.0,
        "late_hours": totals["late_minutes"] / 60.0,
        "routes": len(routes),
        "fleet": dict(sorted(fleet.items())),
        "capacity_violations": capacity_violations,
        "fleet_limit_violations": fleet_limit_violations,
        "policy_violations": policy_violations,
        "max_customer_weight_error_kg": demand_weight_error,
        "max_customer_volume_error_m3": demand_volume_error,
        "feasible": bool(
            capacity_violations == 0
            and fleet_limit_violations == 0
            and policy_violations == 0
            and demand_weight_error < 1e-5
            and demand_volume_error < 1e-7
        ),
        "route_rows": route_rows,
    }
    return summary, stop_rows


def monte_carlo_routes(
    routes: list[Route],
    data: dict[str, object],
    green: set[int],
    policy: bool,
    trials: int,
    seed: int,
) -> dict[str, float]:
    rng = np.random.default_rng(seed)
    costs, late_hours, emissions = [], [], []
    for _ in range(trials):
        sampled = {
            "smooth": float(np.clip(rng.normal(55.3, 0.1), 3.0, 90.0)),
            "normal": float(np.clip(rng.normal(35.4, 5.2), 3.0, 90.0)),
            "congested": float(np.clip(rng.normal(9.8, 4.7), 3.0, 90.0)),
        }
        summary, _ = summarize_routes(routes, data, green, policy, sampled)
        costs.append(float(summary["total_cost"]))
        late_hours.append(float(summary["late_hours"]))
        emissions.append(float(summary["emissions_kg"]))
    return {
        "trials": trials,
        "cost_mean": float(np.mean(costs)),
        "cost_p05": float(np.quantile(costs, 0.05)),
        "cost_p95": float(np.quantile(costs, 0.95)),
        "late_hours_mean": float(np.mean(late_hours)),
        "late_hours_p95": float(np.quantile(late_hours, 0.95)),
        "emissions_mean_kg": float(np.mean(emissions)),
        "emissions_p95_kg": float(np.quantile(emissions, 0.95)),
    }


def dynamic_event(
    base_routes: list[Route],
    data: dict[str, object],
    green: set[int],
    policy: bool,
) -> tuple[list[Route], dict[str, object]]:
    event_minute = 14.0 * 60.0
    routes = [route.clone() for route in base_routes]
    distances = data["distances"]
    windows = dict(data["windows"])
    assert isinstance(distances, np.ndarray)
    before, _ = summarize_routes(routes, data, green, policy)

    mutable_candidates: defaultdict[int, list[tuple[int, float, float]]] = defaultdict(list)
    locked: dict[int, int] = {}
    for index, route in enumerate(routes):
        result = evaluate_route(route, distances, windows, green, policy)
        starts = [float(stop["service_start_min"]) for stop in result["stops"]]
        first_future = next((i for i, start in enumerate(starts) if start >= event_minute), len(starts))
        locked_prefix = min(len(starts), first_future + 1) if first_future < len(starts) else len(starts)
        locked[index] = locked_prefix
        for position in range(locked_prefix, len(route.order)):
            customer = route.order[position]
            weight, volume = route.deliveries[customer]
            mutable_candidates[customer].append((index, weight, volume))

    if not mutable_candidates:
        raise RuntimeError("No uncommitted stops remain at the selected event time")
    cancel_customer = max(
        mutable_candidates,
        key=lambda customer: sum(item[1] for item in mutable_candidates[customer]),
    )
    cancelled_weight = 0.0
    cancelled_volume = 0.0
    changed_route_indices: set[int] = set()
    for route_index, weight, volume in mutable_candidates[cancel_customer]:
        route = routes[route_index]
        if cancel_customer in route.order[locked[route_index] :]:
            route.order.remove(cancel_customer)
            del route.deliveries[cancel_customer]
            cancelled_weight += weight
            cancelled_volume += volume
            changed_route_indices.add(route_index)

    new_customer = 96
    new_delivery = (600.0, 2.2)
    windows[new_customer] = (16.5 * 60.0, 19.0 * 60.0)
    dynamic_data = dict(data)
    dynamic_demands = dict(data["demands"])
    dynamic_demands[cancel_customer] = (
        max(0.0, dynamic_demands[cancel_customer][0] - cancelled_weight),
        max(0.0, dynamic_demands[cancel_customer][1] - cancelled_volume),
    )
    dynamic_demands[new_customer] = new_delivery
    dynamic_data["demands"] = dynamic_demands
    dynamic_data["windows"] = windows
    after_cancellation, _ = summarize_routes(routes, dynamic_data, green, policy)

    used = used_vehicle_counts(routes)
    best: tuple[float, str, int, Route] | None = None
    for index, route in enumerate(routes):
        if not route.order or not fits(route, *new_delivery):
            continue
        route.locked_prefix = min(locked[index], len(route.order))
        old_cost = float(evaluate_route(route, distances, windows, green, policy)["objective"])
        for position in range(route.locked_prefix, len(route.order) + 1):
            candidate = with_piece(route, new_customer, new_delivery, position)
            candidate.departure = route.departure
            candidate.locked_prefix = route.locked_prefix
            new_cost = float(evaluate_route(candidate, distances, windows, green, policy)["objective"])
            choice = (new_cost - old_cost, "existing", index, candidate)
            if best is None or choice[0] < best[0]:
                best = choice

    for vehicle in VEHICLES:
        if used[vehicle.name] >= vehicle.count:
            continue
        candidate = Route(
            vehicle=vehicle,
            order=[new_customer],
            deliveries={new_customer: new_delivery},
            min_departure=event_minute,
        )
        if not fits(candidate):
            continue
        result = evaluate_route(candidate, distances, windows, green, policy, optimize_departure=True)
        candidate.departure = float(result["departure_min"])
        choice = (float(result["objective"]), "new", len(routes), candidate)
        if best is None or choice[0] < best[0]:
            best = choice
    if best is None:
        raise RuntimeError("Dynamic order cannot be inserted with the remaining fleet")
    if best[1] == "existing":
        routes[best[2]] = best[3]
        changed_route_indices.add(best[2])
    else:
        routes.append(best[3])
        changed_route_indices.add(len(routes) - 1)

    routes = [route for route in routes if route.order]
    after, _ = summarize_routes(routes, dynamic_data, green, policy)
    event = {
        "event_time": "14:00",
        "strategy": "freeze completed stops and the next committed stop; cancel mutable deliveries; cheapest feasible insertion for the new order",
        "cancelled_customer": cancel_customer,
        "cancelled_weight_kg": cancelled_weight,
        "cancelled_volume_m3": cancelled_volume,
        "new_customer": new_customer,
        "new_weight_kg": new_delivery[0],
        "new_volume_m3": new_delivery[1],
        "new_time_window": ["16:30", "19:00"],
        "changed_routes": len(changed_route_indices),
        "cost_before_event_plan": before["total_cost"],
        "cost_after_cancellation": after_cancellation["total_cost"],
        "cost_after_replan": after["total_cost"],
        "cost_change": after["total_cost"] - before["total_cost"],
        "new_order_incremental_cost": after["total_cost"] - after_cancellation["total_cost"],
        "feasible": after["feasible"],
        "summary": after,
    }
    return routes, event


def save_solution(
    name: str,
    routes: list[Route],
    data: dict[str, object],
    green: set[int],
    policy: bool,
    output_dir: Path,
) -> dict[str, object]:
    summary, stops = summarize_routes(routes, data, green, policy)
    route_rows = summary.pop("route_rows")
    pd.DataFrame(route_rows).to_csv(output_dir / f"{name}_routes.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(stops).to_csv(output_dir / f"{name}_stops.csv", index=False, encoding="utf-8-sig")
    (output_dir / f"{name}_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def plot_routes(
    name: str,
    routes: list[Route],
    data: dict[str, object],
    green: set[int],
    output_dir: Path,
) -> None:
    coords = data["coords"]
    assert isinstance(coords, dict)
    figure, axis = plt.subplots(figsize=(9, 8), constrained_layout=True)
    axis.add_patch(plt.Circle((0, 0), 10, fill=False, color="#D97706", linewidth=2, label="10 km green zone"))
    for route in routes:
        nodes = [0, *route.order, 0]
        color = "#0F766E" if route.vehicle.power == "electric" else "#64748B"
        axis.plot(
            [coords[node][0] for node in nodes],
            [coords[node][1] for node in nodes],
            color=color,
            alpha=0.22,
            linewidth=0.8,
        )
    customers = [customer for customer in range(1, 99)]
    axis.scatter(
        [coords[c][0] for c in customers],
        [coords[c][1] for c in customers],
        c=["#D97706" if c in green else "#2563EB" for c in customers],
        s=20,
        zorder=3,
    )
    axis.scatter([coords[0][0]], [coords[0][1]], marker="s", s=90, c="#DC2626", label="Depot", zorder=4)
    axis.plot([], [], color="#0F766E", linewidth=2, label="Electric route")
    axis.plot([], [], color="#64748B", linewidth=2, label="Fuel route")
    axis.set_title(name.replace("_", " ").title())
    axis.set_xlabel("X (km)")
    axis.set_ylabel("Y (km)")
    axis.set_aspect("equal", adjustable="box")
    axis.grid(alpha=0.2)
    axis.legend(loc="upper left")
    figure.savefig(output_dir / f"{name}_map.png", dpi=180)
    plt.close(figure)


def comparison_table(results: dict[str, dict[str, object]]) -> pd.DataFrame:
    rows = []
    for name, summary in results.items():
        rows.append(
            {
                "scenario": name,
                "total_cost": summary["total_cost"],
                "routes": summary["routes"],
                "distance_km": summary["distance_km"],
                "emissions_kg": summary["emissions_kg"],
                "late_hours": summary["late_hours"],
                "wait_hours": summary["wait_hours"],
                "feasible": summary["feasible"],
            }
        )
    return pd.DataFrame(rows)


def write_report(
    output_dir: Path,
    audit: dict[str, object],
    results: dict[str, dict[str, object]],
    mc: dict[str, dict[str, float]],
    event: dict[str, object],
    runtimes: dict[str, float],
) -> None:
    q1b, q1 = results["q1_baseline"], results["q1_candidate"]
    q2b, q2 = results["q2_baseline"], results["q2_candidate"]
    q230 = results["q2_30_nearest_sensitivity"]

    def pct(new: float, old: float) -> float:
        return (new / old - 1.0) * 100.0

    lines = [
        "# 城市绿色物流配送调度封闭试运行报告",
        "",
        "## 试运行边界",
        "",
        "本次分析只使用用户提供的题目 PDF 与四个原始 Excel。没有联网，没有检索题解，也没有读取题目目录中的既有代码、结果表或图片。结果是启发式可行解，不宣称全局最优。",
        "",
        "## 数据核验与关键口径",
        "",
        f"- 订单 {audit['orders']} 条，98 个客户中 {audit['active_customers']} 个有正需求；总重量 {audit['total_weight_kg']:.3f} kg，总体积 {audit['total_volume_m3']:.3f} m3。",
        f"- 重量缺失 {audit['missing_before_imputation']['重量']} 条、体积缺失 {audit['missing_before_imputation']['体积']} 条，按同客户中位数插补；客户内仍缺失时退回全体中位数。",
        f"- {audit['customers_exceeding_largest_vehicle']} 个客户需求超过最大车辆容量，因此采用可拆分配送；同一客户可由多辆车服务。",
        f"- 按坐标到市中心 (0,0) 的欧氏距离不超过 10 km，只得到 {audit['green_by_radius_10km']} 个绿色区客户，与题面所述 30 个冲突。主结果服从几何定义，另以距离市中心最近的 30 个客户作敏感性。",
        "- 车辆统一 08:00 后出发，服务 20 分钟。题面未给出 17:00 后速度，延用顺畅时段均值 55.3 km/h。",
        "- 早到等待与政策等待均按 20 元/小时计，晚到按 50 元/小时计。燃油车只要在绿色区客户的服务开始时刻不早于 16:00，即判定满足限行；道路轨迹未知，无法约束穿越绿色区。",
        "- 每段能耗按当前最大重量/体积利用率线性插值：燃油满载增幅 40%，新能源满载增幅 35%。",
        "",
        "## 模型",
        "",
        "基准模型采用按最晚时刻排序的顺序插入，只允许把新客户接到现有路径末尾。主模型采用多起点客户排序、全位置最小增量插入、客户访问次序 2-opt、跨路线搬移和车型再分配。每条路线的出发时刻按 15 分钟网格优化。目标函数为车辆启动成本、能耗成本、碳成本、等待成本与迟到成本之和。",
        "",
        "## 问题 1：无政策限制",
        "",
        "| 指标 | 基准 | 主模型 | 变化 |",
        "|---|---:|---:|---:|",
        f"| 总成本（元） | {q1b['total_cost']:.2f} | {q1['total_cost']:.2f} | {pct(q1['total_cost'], q1b['total_cost']):+.2f}% |",
        f"| 车辆数 | {q1b['routes']} | {q1['routes']} | {q1['routes']-q1b['routes']:+d} |",
        f"| 里程（km） | {q1b['distance_km']:.2f} | {q1['distance_km']:.2f} | {pct(q1['distance_km'], q1b['distance_km']):+.2f}% |",
        f"| 碳排放（kg） | {q1b['emissions_kg']:.2f} | {q1['emissions_kg']:.2f} | {pct(q1['emissions_kg'], q1b['emissions_kg']):+.2f}% |",
        f"| 迟到（小时） | {q1b['late_hours']:.2f} | {q1['late_hours']:.2f} | {q1['late_hours']-q1b['late_hours']:+.2f} |",
        "",
        f"主模型车队结构：`{json.dumps(q1['fleet'], ensure_ascii=False)}`。约束复核：`feasible={q1['feasible']}`。完整路径、到达时间和逐项成本见 `q1_candidate_routes.csv` 与 `q1_candidate_stops.csv`。",
        "",
        "## 问题 2：绿色区限行",
        "",
        "| 指标 | 无政策主模型 | 限行基准 | 限行主模型 | 政策相对无政策 |",
        "|---|---:|---:|---:|---:|",
        f"| 总成本（元） | {q1['total_cost']:.2f} | {q2b['total_cost']:.2f} | {q2['total_cost']:.2f} | {pct(q2['total_cost'], q1['total_cost']):+.2f}% |",
        f"| 车辆数 | {q1['routes']} | {q2b['routes']} | {q2['routes']} | {q2['routes']-q1['routes']:+d} |",
        f"| 里程（km） | {q1['distance_km']:.2f} | {q2b['distance_km']:.2f} | {q2['distance_km']:.2f} | {pct(q2['distance_km'], q1['distance_km']):+.2f}% |",
        f"| 碳排放（kg） | {q1['emissions_kg']:.2f} | {q2b['emissions_kg']:.2f} | {q2['emissions_kg']:.2f} | {pct(q2['emissions_kg'], q1['emissions_kg']):+.2f}% |",
        f"| 迟到（小时） | {q1['late_hours']:.2f} | {q2b['late_hours']:.2f} | {q2['late_hours']:.2f} | {q2['late_hours']-q1['late_hours']:+.2f} |",
        "",
        f"限行主模型车队结构：`{json.dumps(q2['fleet'], ensure_ascii=False)}`；燃油车绿色区违规次数 {q2['policy_violations']}。若强制采用 30 个最近市中心客户，成本为 {q230['total_cost']:.2f} 元、排放为 {q230['emissions_kg']:.2f} kg、迟到 {q230['late_hours']:.2f} 小时。这个差异说明绿色区口径必须在论文中先澄清。",
        "",
        "## 问题 3：动态事件",
        "",
        f"14:00 触发组合事件：取消客户 {event['cancelled_customer']} 尚未承诺的配送量 {event['cancelled_weight_kg']:.2f} kg / {event['cancelled_volume_m3']:.2f} m3，并在原零需求客户 96 新增 600 kg / 2.2 m3、时间窗 16:30-19:00 的订单。滚动策略冻结已完成访问和下一承诺访问，只在未执行后缀中做最小增量插入。共改变 {event['changed_routes']} 条路线；取消后成本 {event['cost_after_cancellation']:.2f} 元，新订单边际成本 {event['new_order_incremental_cost']:+.2f} 元，最终相对原计划变化 {event['cost_change']:+.2f} 元，约束复核 `feasible={event['feasible']}`。",
        "",
        "## 随机速度稳健性",
        "",
        f"问题 1 主模型在 {mc['q1']['trials']} 次速度抽样下，总成本均值 {mc['q1']['cost_mean']:.2f} 元，5%-95% 区间 [{mc['q1']['cost_p05']:.2f}, {mc['q1']['cost_p95']:.2f}]，95% 分位迟到 {mc['q1']['late_hours_p95']:.2f} 小时。",
        f"问题 2 主模型在 {mc['q2']['trials']} 次速度抽样下，总成本均值 {mc['q2']['cost_mean']:.2f} 元，5%-95% 区间 [{mc['q2']['cost_p05']:.2f}, {mc['q2']['cost_p95']:.2f}]，95% 分位迟到 {mc['q2']['late_hours_p95']:.2f} 小时。",
        "",
        "## 结论边界",
        "",
        "这版结果适合验证项目流水线和形成论文骨架，但不能直接当最终竞赛答案。最主要的风险是题面绿色区数量矛盾、拆分配送未明确、17:00 后速度缺口，以及启发式算法没有全局最优证明。提交前应向赛方确认数据口径，或在论文中并列两种口径并做敏感性说明。",
        "",
        "## 运行信息",
        "",
        f"随机种子：`{os.getenv('MATH_MODEL_SEED', '2026')}`。各场景运行时间（秒）：`{json.dumps(runtimes, ensure_ascii=False)}`。",
    ]
    (output_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Closed-book green logistics trial")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--seed", type=int, default=int(os.getenv("MATH_MODEL_SEED", "2026")))
    parser.add_argument("--starts", type=int, default=6)
    parser.add_argument("--mc-trials", type=int, default=100)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    data = load_inputs(args.data_dir)
    audit = data["audit"]
    assert isinstance(audit, dict)
    (args.output_dir / "data_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    green_geometry = data["green_geometry"]
    green_30 = data["green_30_nearest"]
    assert isinstance(green_geometry, set) and isinstance(green_30, set)

    runs = [
        ("q1_baseline", green_geometry, False, "baseline", 1),
        ("q1_candidate", green_geometry, False, "candidate", args.starts),
        ("q2_baseline", green_geometry, True, "baseline", 1),
        ("q2_candidate", green_geometry, True, "candidate", args.starts),
        ("q2_30_nearest_sensitivity", green_30, True, "candidate", max(3, args.starts // 2)),
    ]
    routes_by_name: dict[str, list[Route]] = {}
    summaries: dict[str, dict[str, object]] = {}
    runtimes: dict[str, float] = {}
    for offset, (name, green, policy, method, starts) in enumerate(runs):
        began = time.perf_counter()
        routes = solve(data, green, policy, method, starts, args.seed + offset * 10000)
        runtimes[name] = round(time.perf_counter() - began, 3)
        routes_by_name[name] = routes
        summaries[name] = save_solution(name, routes, data, green, policy, args.output_dir)
        if not summaries[name]["feasible"]:
            raise RuntimeError(f"Constraint audit failed for {name}: {summaries[name]}")
        print(
            f"{name}: cost={summaries[name]['total_cost']:.2f}, "
            f"routes={summaries[name]['routes']}, emissions={summaries[name]['emissions_kg']:.2f}"
        )

    dynamic_started = time.perf_counter()
    dynamic_routes, event = dynamic_event(
        routes_by_name["q2_candidate"], data, green_geometry, True
    )
    runtimes["q3_dynamic"] = round(time.perf_counter() - dynamic_started, 3)
    dynamic_data = dict(data)
    dynamic_demands = dict(data["demands"])
    dynamic_demands[event["cancelled_customer"]] = (
        max(0.0, dynamic_demands[event["cancelled_customer"]][0] - event["cancelled_weight_kg"]),
        max(0.0, dynamic_demands[event["cancelled_customer"]][1] - event["cancelled_volume_m3"]),
    )
    dynamic_demands[event["new_customer"]] = (event["new_weight_kg"], event["new_volume_m3"])
    dynamic_windows = dict(data["windows"])
    dynamic_windows[event["new_customer"]] = (16.5 * 60.0, 19.0 * 60.0)
    dynamic_data["demands"] = dynamic_demands
    dynamic_data["windows"] = dynamic_windows
    dynamic_summary = save_solution(
        "q3_dynamic", dynamic_routes, dynamic_data, green_geometry, True, args.output_dir
    )
    event["summary"] = dynamic_summary
    (args.output_dir / "q3_event.json").write_text(
        json.dumps(event, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    mc = {
        "q1": monte_carlo_routes(
            routes_by_name["q1_candidate"], data, green_geometry, False, args.mc_trials, args.seed + 90001
        ),
        "q2": monte_carlo_routes(
            routes_by_name["q2_candidate"], data, green_geometry, True, args.mc_trials, args.seed + 90002
        ),
    }
    (args.output_dir / "monte_carlo.json").write_text(
        json.dumps(mc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    comparison_table(summaries).to_csv(
        args.output_dir / "model_comparison.csv", index=False, encoding="utf-8-sig"
    )
    plot_routes("q1_candidate", routes_by_name["q1_candidate"], data, green_geometry, args.output_dir)
    plot_routes("q2_candidate", routes_by_name["q2_candidate"], data, green_geometry, args.output_dir)
    write_report(args.output_dir, audit, summaries, mc, event, runtimes)
    print(f"Saved trial outputs to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
