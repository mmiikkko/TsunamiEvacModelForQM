"""Create a proximity-only review queue for separate road-graph components.

The output lines visualize straight-line gaps between mapped graph nodes. They
are not road links and must never be inserted into the network automatically.
"""

from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np


DATA = Path(__file__).resolve().parent
NODES = DATA / "daet_basud_network_nodes.csv"
EDGES = DATA / "daet_basud_network_edges.csv"
COMPONENT_REVIEW = DATA / "daet_basud_component_review.csv"
OUTPUT_CSV = DATA / "daet_basud_component_gap_review.csv"
OUTPUT_GEOJSON = DATA / "daet_basud_component_gap_review.geojson"
MAX_LINES_IN_GEOJSON = 100


def main() -> None:
    with NODES.open(encoding="utf-8-sig", newline="") as stream:
        node_rows = {row["node_id"]: row for row in csv.DictReader(stream)}
    with COMPONENT_REVIEW.open(encoding="utf-8-sig", newline="") as stream:
        component_rows = list(csv.DictReader(stream))
    with EDGES.open(encoding="utf-8-sig", newline="") as stream:
        edges = [row for row in csv.DictReader(stream) if row["edge_id"].endswith("_F")]

    node_names: dict[str, set[str]] = defaultdict(set)
    node_osm_ids: dict[str, set[str]] = defaultdict(set)
    node_classes: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        label = (edge.get("name") or "").strip()
        osm_id = (edge.get("osm_id") or "").strip()
        highway = (edge.get("highway") or "").strip()
        if label and label.lower() != "nan":
            node_names[edge["from_node"]].add(label)
            node_names[edge["to_node"]].add(label)
        if osm_id:
            node_osm_ids[edge["from_node"]].add(osm_id)
            node_osm_ids[edge["to_node"]].add(osm_id)
        if highway:
            node_classes[edge["from_node"]].add(highway)
            node_classes[edge["to_node"]].add(highway)

    adjacency: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        a, b = edge["from_node"], edge["to_node"]
        adjacency[a].add(b)
        adjacency[b].add(a)
    member_lists = []
    seen: set[str] = set()
    for node_id in adjacency:
        if node_id in seen:
            continue
        stack = [node_id]
        seen.add(node_id)
        members = []
        while stack:
            current = stack.pop()
            members.append(current)
            for neighbor in adjacency[current]:
                if neighbor not in seen:
                    seen.add(neighbor)
                    stack.append(neighbor)
        member_lists.append(members)
    member_lists.sort(key=lambda members: (-len(members), min(members)))
    if len(member_lists) != len(component_rows):
        raise RuntimeError("Component index is stale; rebuild it before the gap review")

    flat_rows = []
    for index, source_nodes in enumerate(member_lists):
        for target_index in range(index + 1, len(member_lists)):
            target_nodes = member_lists[target_index]
            source_xy = np.array([
                [float(node_rows[n]["lon"]), float(node_rows[n]["lat"])] for n in source_nodes
            ])
            target_xy = np.array([
                [float(node_rows[n]["lon"]), float(node_rows[n]["lat"])] for n in target_nodes
            ])
            latitude_reference = float(np.mean(np.concatenate((source_xy[:, 1], target_xy[:, 1]))))
            lon_scale = 111_320.0 * math.cos(math.radians(latitude_reference))
            lat_scale = 111_320.0
            target_metric = target_xy * np.array([lon_scale, lat_scale])
            best_distance = math.inf
            best_pair: tuple[str, str] | None = None
            for offset in range(0, len(source_nodes), 128):
                source_metric = source_xy[offset:offset + 128] * np.array([lon_scale, lat_scale])
                delta = source_metric[:, None, :] - target_metric[None, :, :]
                squared = np.sum(delta * delta, axis=2)
                row_index, col_index = np.unravel_index(int(np.argmin(squared)), squared.shape)
                distance = math.sqrt(float(squared[row_index, col_index]))
                if distance < best_distance:
                    best_distance = distance
                    best_pair = (source_nodes[offset + int(row_index)], target_nodes[int(col_index)])
            if best_pair is None:
                continue
            a, b = best_pair
            pa = (float(node_rows[a]["lon"]), float(node_rows[a]["lat"]))
            pb = (float(node_rows[b]["lon"]), float(node_rows[b]["lat"]))
            flat_rows.append({
                "component_a": f"C{index + 1:03d}",
                "component_a_vertices": len(source_nodes),
                "component_b": f"C{target_index + 1:03d}",
                "component_b_vertices": len(target_nodes),
                "gap_distance_m": round(best_distance, 1),
                "node_a_id": a,
                "node_a_lon": pa[0],
                "node_a_lat": pa[1],
                "node_a_mapped_roads": "; ".join(sorted(node_names.get(a, set()))) or "Unnamed mapped road/path",
                "node_a_osm_way_ids": "; ".join(sorted(node_osm_ids.get(a, set()))),
                "node_a_highway_classes": "; ".join(sorted(node_classes.get(a, set()))),
                "node_b_id": b,
                "node_b_lon": pb[0],
                "node_b_lat": pb[1],
                "node_b_mapped_roads": "; ".join(sorted(node_names.get(b, set()))) or "Unnamed mapped road/path",
                "node_b_osm_way_ids": "; ".join(sorted(node_osm_ids.get(b, set()))),
                "node_b_highway_classes": "; ".join(sorted(node_classes.get(b, set()))),
                "review_status": "NOT REVIEWED",
                "interpretation": "Straight-line nearest-node pair only; not a road, connector, or route.",
            })

    flat_rows.sort(key=lambda row: (row["gap_distance_m"], -row["component_a_vertices"], row["component_a"], row["component_b"]))
    for rank, row in enumerate(flat_rows, start=1):
        row["review_rank"] = rank
    if flat_rows:
        with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(flat_rows[0]))
            writer.writeheader()
            writer.writerows(flat_rows)

    features = []
    for row in flat_rows[:MAX_LINES_IN_GEOJSON]:
        features.append({
            "type": "Feature",
            "properties": {key: value for key, value in row.items()
                           if key not in {"node_a_lon", "node_a_lat", "node_b_lon", "node_b_lat"}},
            "geometry": {"type": "LineString", "coordinates": [
                [row["node_a_lon"], row["node_a_lat"]], [row["node_b_lon"], row["node_b_lat"]]
            ]},
        })
    OUTPUT_GEOJSON.write_text(json.dumps({"type": "FeatureCollection", "features": features}, indent=2), encoding="utf-8")
    print(f"Wrote {len(flat_rows)} nearest-component-pair rows to {OUTPUT_CSV.name}")
    print(f"Wrote the closest {len(features)} review indicators to {OUTPUT_GEOJSON.name}")


if __name__ == "__main__":
    main()
