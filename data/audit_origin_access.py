"""Create a reproducible proximity and component audit for Gubat origins.

This is a GIS screening aid only. Straight-line distance to an OSM feature or
graph vertex does not establish a usable entrance, pedestrian connection, or
safe route.
"""

from __future__ import annotations

import csv
import json
import math
import sqlite3
from pathlib import Path

from build_osm_road_graph import _read_wkb


DATA_DIR = Path(__file__).resolve().parent
ORIGINS = DATA_DIR / "origin_access_candidates.csv"
NODES = DATA_DIR / "daet_basud_network_nodes.csv"
EDGES = DATA_DIR / "daet_basud_network_edges.csv"
ROADS = DATA_DIR / "daet_basud_roads.gpkg"
OUTPUT = DATA_DIR / "origin_access_review.csv"
POINTS_GEOJSON_OUTPUT = DATA_DIR / "origin_access_review_points.geojson"
LINES_GEOJSON_OUTPUT = DATA_DIR / "origin_access_review_offsets.geojson"


def _xy_m(point: tuple[float, float], origin: tuple[float, float]) -> tuple[float, float]:
    """Local equirectangular coordinates in metres, suitable for this audit."""
    lon, lat = point
    lon0, lat0 = origin
    return (
        math.radians(lon - lon0) * 6_371_008.8 * math.cos(math.radians(lat0)),
        math.radians(lat - lat0) * 6_371_008.8,
    )


def _nearest_on_segment(
    origin: tuple[float, float],
    a: tuple[float, float],
    b: tuple[float, float],
) -> tuple[float, tuple[float, float]]:
    """Return local projected distance and nearest point on one segment."""
    ax, ay = _xy_m(a, origin)
    bx, by = _xy_m(b, origin)
    dx, dy = bx - ax, by - ay
    length2 = dx * dx + dy * dy
    t = 0.0 if length2 == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / length2))
    x, y = ax + t * dx, ay + t * dy
    distance = math.hypot(x, y)
    lon = origin[0] + math.degrees(x / (6_371_008.8 * math.cos(math.radians(origin[1]))))
    lat = origin[1] + math.degrees(y / 6_371_008.8)
    return distance, (lon, lat)


def _load_roads() -> list[dict[str, object]]:
    connection = sqlite3.connect(ROADS)
    connection.row_factory = sqlite3.Row
    table = connection.execute(
        "SELECT table_name FROM gpkg_contents WHERE data_type='features'"
    ).fetchone()[0]
    rows = connection.execute(f'SELECT * FROM "{table}" ORDER BY fid').fetchall()
    connection.close()
    return [dict(row) for row in rows]


def _component_ids(nodes: dict[str, tuple[float, float]], edges: list[dict[str, str]]) -> dict[str, str]:
    parent = {node_id: node_id for node_id in nodes}

    def find(node_id: str) -> str:
        while parent[node_id] != node_id:
            parent[node_id] = parent[parent[node_id]]
            node_id = parent[node_id]
        return node_id

    for edge in edges:
        a, b = find(edge["from_node"]), find(edge["to_node"])
        if a != b:
            parent[max(a, b)] = min(a, b)

    groups: dict[str, list[str]] = {}
    for node_id in nodes:
        groups.setdefault(find(node_id), []).append(node_id)
    ordered = sorted(groups.values(), key=lambda group: (-len(group), min(group)))
    return {node_id: f"C{rank:03d}" for rank, group in enumerate(ordered, start=1) for node_id in group}


def main() -> None:
    with NODES.open(encoding="utf-8-sig", newline="") as stream:
        node_rows = list(csv.DictReader(stream))
    nodes = {row["node_id"]: (float(row["lon"]), float(row["lat"])) for row in node_rows}
    with EDGES.open(encoding="utf-8-sig", newline="") as stream:
        edges = list(csv.DictReader(stream))
    with ORIGINS.open(encoding="utf-8-sig", newline="") as stream:
        origins = list(csv.DictReader(stream))

    component_for_node = _component_ids(nodes, edges)
    component_sizes: dict[str, int] = {}
    for component_id in component_for_node.values():
        component_sizes[component_id] = component_sizes.get(component_id, 0) + 1

    road_rows = _load_roads()
    output_rows = []
    for origin_row in origins:
        anchor = (float(origin_row["anchor_lon"]), float(origin_row["anchor_lat"]))
        candidate_id = origin_row["candidate_node_id"]
        candidate_point = nodes[candidate_id]
        nearest_vertex_id = min(nodes, key=lambda node_id: math.dist(_xy_m(nodes[node_id], anchor), (0.0, 0.0)))

        nearest_feature: tuple[float, dict[str, object], tuple[float, float]] | None = None
        for road in road_rows:
            for line in _read_wkb(road["geom"]):
                for a, b in zip(line, line[1:]):
                    distance, nearest_point = _nearest_on_segment(anchor, a, b)
                    if nearest_feature is None or distance < nearest_feature[0]:
                        nearest_feature = (distance, road, nearest_point)
        if nearest_feature is None:
            raise ValueError(f"No road geometries available for {origin_row['zone_id']}")

        road_distance, road, nearest_point = nearest_feature
        component_id = component_for_node[candidate_id]
        output_rows.append({
            "zone_id": origin_row["zone_id"],
            "zone_name": origin_row["zone_name"],
            "anchor_lon": anchor[0],
            "anchor_lat": anchor[1],
            "candidate_node_id": candidate_id,
            "candidate_node_lon": candidate_point[0],
            "candidate_node_lat": candidate_point[1],
            "anchor_to_candidate_node_m": round(math.dist(_xy_m(candidate_point, anchor), (0.0, 0.0)), 1),
            "nearest_graph_node_id": nearest_vertex_id,
            "candidate_is_nearest_graph_node": candidate_id == nearest_vertex_id,
            "candidate_component_id": component_id,
            "candidate_component_vertices": component_sizes[component_id],
            "nearest_road_fid": road["fid"],
            "nearest_road_osm_id": road.get("osm_id", ""),
            "nearest_road_name_or_ref": road.get("name") or road.get("ref") or "",
            "nearest_road_highway": road.get("highway") or "",
            "nearest_road_foot": road.get("foot") or "",
            "nearest_road_access": road.get("access") or "",
            "anchor_to_road_geometry_m": round(road_distance, 1),
            "nearest_road_point_lon": round(nearest_point[0], 8),
            "nearest_road_point_lat": round(nearest_point[1], 8),
            "review_status": "REVIEW_REQUIRED",
            "interpretation": "Proximity/component screen only; no entrance, pedestrian link, crossing, or route is validated.",
        })

    for row in output_rows:
        peers = [
            other["zone_name"] for other in output_rows
            if other["zone_id"] != row["zone_id"]
            and other["candidate_component_id"] == row["candidate_component_id"]
        ]
        row["other_candidate_origins_same_component"] = "; ".join(peers)

    fields = list(output_rows[0])
    with OUTPUT.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output_rows)

    point_features = []
    line_features = []
    for row in output_rows:
        common = {
            "zone_id": row["zone_id"],
            "zone_name": row["zone_name"],
            "candidate_node_id": row["candidate_node_id"],
            "candidate_component_id": row["candidate_component_id"],
            "anchor_to_road_geometry_m": row["anchor_to_road_geometry_m"],
            "anchor_to_candidate_node_m": row["anchor_to_candidate_node_m"],
            "nearest_road_osm_id": row["nearest_road_osm_id"],
            "nearest_road_name_or_ref": row["nearest_road_name_or_ref"],
            "nearest_road_highway": row["nearest_road_highway"],
            "review_status": row["review_status"],
            "not_a_route": True,
        }
        points = {
            "origin_anchor": [row["anchor_lon"], row["anchor_lat"]],
            "candidate_graph_node": [row["candidate_node_lon"], row["candidate_node_lat"]],
            "nearest_road_geometry_point": [row["nearest_road_point_lon"], row["nearest_road_point_lat"]],
        }
        for role, coordinates in points.items():
            point_features.append({
                "type": "Feature",
                "properties": {**common, "feature_role": role},
                "geometry": {"type": "Point", "coordinates": coordinates},
            })
        for role, endpoint in (
            ("anchor_to_road_proximity_only", points["nearest_road_geometry_point"]),
            ("anchor_to_candidate_node_offset_only", points["candidate_graph_node"]),
        ):
            line_features.append({
                "type": "Feature",
                "properties": {**common, "feature_role": role},
                "geometry": {"type": "LineString", "coordinates": [points["origin_anchor"], endpoint]},
            })

    for path, layer_name, features in (
        (POINTS_GEOJSON_OUTPUT, "Gubat origin access review points", point_features),
        (LINES_GEOJSON_OUTPUT, "Gubat origin access offsets only - not routes", line_features),
    ):
        with path.open("w", encoding="utf-8") as stream:
            json.dump({"type": "FeatureCollection", "name": layer_name, "features": features}, stream, ensure_ascii=False, indent=2)

    print(f"Wrote {OUTPUT}")
    print(f"Wrote {POINTS_GEOJSON_OUTPUT}")
    print(f"Wrote {LINES_GEOJSON_OUTPUT}")
    for row in output_rows:
        print(
            f"{row['zone_name']}: road geometry {row['anchor_to_road_geometry_m']} m; "
            f"candidate node {row['anchor_to_candidate_node_m']} m; "
            f"{row['candidate_component_id']} ({row['candidate_component_vertices']} vertices); "
            f"nearest graph node match={row['candidate_is_nearest_graph_node']}"
        )


if __name__ == "__main__":
    main()
