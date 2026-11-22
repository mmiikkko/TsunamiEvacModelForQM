"""Privacy-preserving synthetic evacuation group and departure scenarios."""

from __future__ import annotations

import math
import random
from pathlib import Path

import pandas as pd


def generate_synthetic_groups(
    total_people: int,
    small_party_share: float,
    departure_window_min: int,
    seed: int,
) -> pd.DataFrame:
    """Split an aggregate total into anonymous groups with reproducible departures.

    Typical party sizes are scenario draws from 5–10 people; small-party draws
    use 2–3. These are assumptions, not inferred household records. Group
    locations are intentionally not generated here.
    """
    total_people = int(total_people)
    departure_window_min = int(departure_window_min)
    if total_people < 1:
        raise ValueError("total_people must be at least 1")
    if not 0 <= small_party_share <= 1:
        raise ValueError("small_party_share must be between 0 and 1")
    if departure_window_min < 0:
        raise ValueError("departure_window_min cannot be negative")

    rng = random.Random(int(seed))
    typical_sizes = list(range(5, 11))
    small_sizes = [2, 3]
    available_sizes = sorted(set(typical_sizes + small_sizes))

    # Reachability ensures each random size choice leaves a way to partition
    # the remainder exactly, avoiding an artificial leftover person/group.
    reachable = [False] * (total_people + 1)
    reachable[0] = True
    for amount in range(1, total_people + 1):
        reachable[amount] = any(
            size <= amount and reachable[amount - size]
            for size in available_sizes
        )
    if not reachable[total_people]:
        # A one-person total is retained as a one-person synthetic group.
        if total_people != 1:
            raise ValueError("The total cannot be partitioned using the configured party sizes")

    groups: list[dict[str, int | float | str]] = []
    remaining = total_people
    while remaining > 0:
        wants_small = rng.random() < small_party_share
        preferred_sizes = small_sizes if wants_small else typical_sizes
        options = [
            size for size in preferred_sizes
            if size <= remaining and reachable[remaining - size]
        ]
        if not options:
            options = [
                size for size in available_sizes
                if size <= remaining and reachable[remaining - size]
            ]
        if not options:
            # This only occurs for a one-person total or a final one-person
            # remainder, which is avoided by reachability for larger totals.
            size = remaining
            party_type = "balancing remainder"
        else:
            size = rng.choice(options)
            party_type = "small-party assumption (2–3)" if size in small_sizes else "typical-party assumption (5–10)"

        departure = (
            round(rng.uniform(0, departure_window_min), 2)
            if departure_window_min > 0 else 0.0
        )
        groups.append({
            "group_id": f"SG{len(groups) + 1:05d}",
            "zone": "Gubat aggregate (location unassigned)",
            "group_size": size,
            "party_size_assumption": party_type,
            "departure_min": departure,
        })
        remaining -= size

    result = pd.DataFrame(groups)
    return result.sort_values(["departure_min", "group_id"], ignore_index=True)


def _ring_area(ring: list[list[float]]) -> float:
    return abs(sum(
        ring[index][0] * ring[index + 1][1] - ring[index + 1][0] * ring[index][1]
        for index in range(len(ring) - 1)
    ) / 2.0)


def _point_in_ring(lon: float, lat: float, ring: list[list[float]]) -> bool:
    inside = False
    previous = len(ring) - 1
    for current in range(len(ring)):
        x1, y1 = ring[current]
        x2, y2 = ring[previous]
        if (y1 > lat) != (y2 > lat):
            crossing_lon = (x2 - x1) * (lat - y1) / (y2 - y1) + x1
            if lon < crossing_lon:
                inside = not inside
        previous = current
    return inside


def load_named_zone_anchors(
    csv_path: str | Path,
    boundary_features: list[dict],
) -> pd.DataFrame:
    """Load named residential-area anchors and keep only Gubat candidates.

    Coordinates are named-place anchors from public map references, not
    household points or polygon centroids. Zone population shares remain
    synthetic until safe local aggregate counts are available.
    """
    zones = pd.read_csv(csv_path)
    required = {"zone_id", "zone_name", "longitude", "latitude", "include_in_gubat_origins"}
    missing = required - set(zones.columns)
    if missing:
        raise ValueError(f"Origin-zone candidate file is missing columns: {sorted(missing)}")
    include = zones["include_in_gubat_origins"].astype(str).str.strip().str.lower().isin({"true", "1", "yes"})
    zones = zones.loc[include].copy()
    zones["longitude"] = pd.to_numeric(zones["longitude"], errors="raise")
    zones["latitude"] = pd.to_numeric(zones["latitude"], errors="raise")

    rings = []
    for feature in boundary_features:
        geometry = feature["geometry"]
        polygons = (
            [geometry["coordinates"]]
            if geometry["type"] == "Polygon"
            else geometry["coordinates"] if geometry["type"] == "MultiPolygon" else []
        )
        rings.extend(polygon[0] for polygon in polygons if polygon)
    if not rings:
        raise ValueError("Gubat boundary has no polygon exterior ring")
    main_ring = max(rings, key=_ring_area)

    inside = zones.apply(
        lambda row: _point_in_ring(float(row["longitude"]), float(row["latitude"]), main_ring),
        axis=1,
    )
    outside_names = zones.loc[~inside, "zone_name"].tolist()
    if outside_names:
        raise ValueError(f"These named origin anchors fall outside the Gubat boundary: {outside_names}")
    return zones.rename(columns={"longitude": "lon", "latitude": "lat"}).reset_index(drop=True)


def allocate_groups_to_zones(
    groups: pd.DataFrame,
    zones: pd.DataFrame,
    seed: int,
    zone_balance: int = 4,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Assign groups to anonymous anchors using random zone shares.

    ``zone_balance`` is a scenario control from 1 (more uneven) to 10 (more
    even). The allocation is synthetic and must not be read as observed
    population density.
    """
    if zones.empty:
        raise ValueError("At least one synthetic zone is required")
    if not 1 <= int(zone_balance) <= 10:
        raise ValueError("zone_balance must be between 1 and 10")

    rng = random.Random(int(seed) + 7_919)
    alpha = float(zone_balance)
    random_weights = [rng.gammavariate(alpha, 1.0) for _ in range(len(zones))]
    zone_indices = list(range(len(zones)))
    assignments = rng.choices(zone_indices, weights=random_weights, k=len(groups))

    result = groups.copy().reset_index(drop=True)
    zone_records = zones.reset_index(drop=True).to_dict("records")
    result["zone_id"] = [zone_records[index]["zone_id"] for index in assignments]
    result["zone"] = [zone_records[index]["zone_name"] for index in assignments]

    summary = (
        result.groupby("zone_id", as_index=False)
        .agg(groups=("group_id", "count"), people=("group_size", "sum"))
    )
    summary = zones.merge(summary, on="zone_id", how="left").fillna({"groups": 0, "people": 0})
    summary["groups"] = summary["groups"].astype(int)
    summary["people"] = summary["people"].astype(int)
    total = max(int(result["group_size"].sum()), 1)
    summary["simulated_share_pct"] = (summary["people"] / total * 100).round(1)
    summary = summary.sort_values("zone_id", ignore_index=True)
    return result, summary


def nearest_candidate_road_nodes(
    zones: pd.DataFrame,
    road_nodes: pd.DataFrame,
) -> pd.DataFrame:
    """Find nearest graph vertices to named-place anchors for manual review.

    Uses a local equirectangular approximation suitable for these short
    distances. This is a geometric candidate only; it does not verify a
    pedestrian entrance or network connectivity.
    """
    if road_nodes.empty:
        raise ValueError("Road graph contains no nodes")
    reference_lat = float(zones["lat"].mean())
    lon_scale = 111_320.0 * math.cos(math.radians(reference_lat))
    lat_scale = 111_320.0
    node_records = road_nodes.to_dict("records")
    output = []
    for zone in zones.to_dict("records"):
        best = None
        for node in node_records:
            dx = (float(node["lon"]) - float(zone["lon"])) * lon_scale
            dy = (float(node["lat"]) - float(zone["lat"])) * lat_scale
            distance = math.hypot(dx, dy)
            if best is None or distance < best["distance_m"]:
                best = {
                    "zone_id": zone["zone_id"],
                    "zone_name": zone["zone_name"],
                    "anchor_lon": float(zone["lon"]),
                    "anchor_lat": float(zone["lat"]),
                    "candidate_node_id": str(node["node_id"]),
                    "candidate_lon": float(node["lon"]),
                    "candidate_lat": float(node["lat"]),
                    "distance_m": distance,
                    "status": "GEOMETRIC_CANDIDATE_NOT_FIELD_VALIDATED",
                }
        output.append(best)
    result = pd.DataFrame(output)
    result["distance_m"] = result["distance_m"].round(1)
    return result
