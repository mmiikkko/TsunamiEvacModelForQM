"""Simple network evacuation estimator for prototype planning only."""

from __future__ import annotations

import math
from typing import Any

import networkx as nx
import pandas as pd


def load_inputs(data_dir: str = "data") -> dict[str, pd.DataFrame]:
    """Load and validate the replaceable CSV inputs."""
    names = ("nodes", "roads", "origins", "shelters", "scenario", "data_sources")
    result = {name: pd.read_csv(f"{data_dir}/{name}.csv") for name in names}
    nodes = result["nodes"]
    roads = result["roads"]
    origins = result["origins"]
    shelters = result["shelters"]
    node_ids = set(nodes["node_id"].astype(str))
    referenced = set(roads["from_node"].astype(str)) | set(roads["to_node"].astype(str))
    referenced |= set(origins["node_id"].astype(str)) | set(shelters["node_id"].astype(str))
    missing = sorted(referenced - node_ids)
    if missing:
        raise ValueError(f"Node IDs referenced by other files are missing from nodes.csv: {missing}")
    for table, cols in (
        (roads, ("length_m", "width_m", "capacity_per_min")),
        (origins, ("population", "walk_speed_mps")),
        (shelters, ("capacity",)),
    ):
        for col in cols:
            table[col] = pd.to_numeric(table[col], errors="raise")
            if (table[col] < 0).any() or ((col != "population") and (table[col] == 0).any()):
                raise ValueError(f"{col} contains invalid nonpositive values")
    return result


def run_simulation(
    inputs: dict[str, pd.DataFrame],
    population_scale: float = 1.0,
    speed_scale: float = 1.0,
    capacity_scale: float = 1.0,
    departure_delay_min: float = 0.0,
    planning_window_min: float = 20.0,
    closed_edges: set[str] | None = None,
) -> dict[str, Any]:
    """Assign origins to nearest reachable shelter and estimate link queues.

    This is a deterministic, aggregate screening model, not a validated
    pedestrian dynamics or tsunami inundation model.
    """
    closed_edges = closed_edges or set()
    nodes, roads, origins, shelters = (inputs[k] for k in ("nodes", "roads", "origins", "shelters"))
    graph = nx.DiGraph()
    for row in roads.to_dict("records"):
        if row["edge_id"] in closed_edges:
            continue
        length = float(row["length_m"])
        capacity = float(row["capacity_per_min"]) * capacity_scale
        graph.add_edge(
            str(row["from_node"]), str(row["to_node"]),
            edge_id=str(row["edge_id"]), length_m=length,
            width_m=float(row["width_m"]), capacity_per_min=capacity,
            free_flow_min=length / 1.15 / 60.0,
        )

    shelter_rows = shelters.to_dict("records")
    node_positions = {
        str(row["node_id"]): (float(row["x"]), float(row["y"]))
        for row in nodes.to_dict("records")
    }
    edge_people: dict[str, float] = {}
    edge_data: dict[str, dict[str, Any]] = {}
    assignments = []
    no_route = 0

    for origin in origins.to_dict("records"):
        origin_node = str(origin["node_id"])
        population = int(round(float(origin["population"]) * population_scale))
        speed = float(origin["walk_speed_mps"]) * speed_scale
        candidates = []
        if origin_node in graph:
            for shelter in shelter_rows:
                destination = str(shelter["node_id"])
                try:
                    path = nx.shortest_path(graph, origin_node, destination, weight="free_flow_min")
                    path_edges = [graph[a][b] for a, b in zip(path, path[1:])]
                    minutes = sum(edge["length_m"] / speed / 60.0 for edge in path_edges)
                    candidates.append((minutes, shelter, path, path_edges))
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    continue
        if not candidates:
            no_route += population
            assignments.append({"origin": origin["group"], "people": population, "destination": "No reachable destination", "walk_min": None})
            continue
        walk_min, shelter, path, path_edges = min(candidates, key=lambda item: item[0])
        for edge in path_edges:
            edge_id = edge["edge_id"]
            edge_people[edge_id] = edge_people.get(edge_id, 0) + population
            edge_data[edge_id] = edge
        assignments.append({
            "origin": origin["group"], "people": population,
            "destination": shelter["name"], "walk_min": walk_min,
            "path": " → ".join(path),
        })

    edge_rows = []
    for row in roads.to_dict("records"):
        edge_id = str(row["edge_id"])
        if edge_id in closed_edges:
            edge_rows.append({**row, "people": 0, "capacity": float(row["capacity_per_min"]) * capacity_scale, "queue_min": 0.0, "load_ratio": 0.0, "closed": True})
            continue
        edge = edge_data.get(edge_id)
        count = edge_people.get(edge_id, 0)
        capacity = edge["capacity_per_min"] if edge else float(row["capacity_per_min"]) * capacity_scale
        queue_min = count / capacity if capacity > 0 else math.inf
        edge_rows.append({**row, "people": count, "capacity": capacity, "queue_min": queue_min, "load_ratio": count / max(capacity * 10, 1), "closed": False})

    routed = [a for a in assignments if a["walk_min"] is not None]
    # A conservative aggregate estimate: free-flow route time plus the total
    # capacity-service queue on route edges, with departure delay added.
    finishes = []
    completed_within_window = 0
    for assignment in routed:
        route = assignment["path"].split(" → ")
        path_edges = [graph[a][b] for a, b in zip(route, route[1:])]
        bottleneck_service = sum(
            assignment["people"] / edge["capacity_per_min"]
            for edge in path_edges if edge["capacity_per_min"] > 0
        )
        finish = float(assignment["walk_min"]) + min(bottleneck_service, float(assignment["walk_min"]) * 2.0) + departure_delay_min
        finishes.append(finish)
        assignment["estimated_finish_min"] = finish
        if finish <= planning_window_min:
            completed_within_window += assignment["people"]
    completion_min = max(finishes, default=0.0)
    total_population = int(sum(a["people"] for a in assignments))

    shelter_rows_out = []
    for shelter in shelter_rows:
        assigned = sum(a["people"] for a in routed if a["destination"] == shelter["name"])
        shelter_rows_out.append({**shelter, "assigned": assigned, "overflow": max(0, assigned - int(shelter["capacity"]))})

    return {
        "assignments": pd.DataFrame(assignments),
        "edges": pd.DataFrame(edge_rows),
        "shelters": pd.DataFrame(shelter_rows_out),
        "total_population": total_population,
        "no_route": no_route,
        "completion_min": completion_min,
        "within_window": completed_within_window,
    }


def node_coordinate_lookup(nodes: pd.DataFrame) -> dict[str, tuple[float, float]]:
    return {
        str(row.node_id): (float(row.x), float(row.y))
        for row in nodes.itertuples(index=False)
    }
