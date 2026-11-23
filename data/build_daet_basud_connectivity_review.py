"""Regenerate the QGIS navigation index from the current candidate graph."""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path


DATA = Path(__file__).resolve().parent
NODES = DATA / "daet_basud_network_nodes.csv"
EDGES = DATA / "daet_basud_network_edges.csv"
OUTPUT = DATA / "daet_basud_component_review.csv"


def main() -> None:
    with NODES.open(encoding="utf-8-sig", newline="") as stream:
        node_rows = {row["node_id"]: row for row in csv.DictReader(stream)}
    with EDGES.open(encoding="utf-8-sig", newline="") as stream:
        edges = [row for row in csv.DictReader(stream) if row["edge_id"].endswith("_F")]

    adjacency: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        a, b = edge["from_node"], edge["to_node"]
        adjacency[a].add(b)
        adjacency[b].add(a)

    components: list[set[str]] = []
    seen: set[str] = set()
    for node_id in adjacency:
        if node_id in seen:
            continue
        stack = [node_id]
        seen.add(node_id)
        members: set[str] = set()
        while stack:
            current = stack.pop()
            members.add(current)
            for neighbor in adjacency[current]:
                if neighbor not in seen:
                    seen.add(neighbor)
                    stack.append(neighbor)
        components.append(members)
    components.sort(key=lambda members: (-len(members), min(members)))
    component_for_node = {
        node_id: f"C{index:03d}"
        for index, members in enumerate(components, start=1)
        for node_id in members
    }

    rows = []
    for index, members in enumerate(components, start=1):
        component_id = f"C{index:03d}"
        points = [(float(node_rows[node]["lon"]), float(node_rows[node]["lat"])) for node in members]
        component_edges = [edge for edge in edges if component_for_node[edge["from_node"]] == component_id]
        classes = Counter(edge.get("highway", "") or "unknown" for edge in component_edges)
        center_lon = sum(point[0] for point in points) / len(points)
        center_lat = sum(point[1] for point in points) / len(points)
        rows.append({
            "component_id": component_id,
            "segment_count": len(component_edges),
            "vertex_count": len(members),
            "feature_count": len({edge["osm_fid"] for edge in component_edges}),
            "highway_classes": "; ".join(f"{name}:{count}" for name, count in classes.most_common()),
            "min_lon": min(point[0] for point in points),
            "min_lat": min(point[1] for point in points),
            "max_lon": max(point[0] for point in points),
            "max_lat": max(point[1] for point in points),
            "center_lon": center_lon,
            "center_lat": center_lat,
            "review_status": "NOT REVIEWED",
            "review_notes": "",
        })
    fields = list(rows[0]) if rows else []
    with OUTPUT.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} component review centers to {OUTPUT.name}")


if __name__ == "__main__":
    main()
