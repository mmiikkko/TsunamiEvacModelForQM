"""Convert the Daet–Basud OSM GeoPackage into a vertex-based graph CSV.

This is a geometry preparation step, not a route-safety validator. It preserves
all mapped ways and does not infer connections at crossings or grade separation.
"""

from __future__ import annotations

import csv
import math
import sqlite3
import struct
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parent
SOURCE = DATA_DIR / "daet_basud_roads.gpkg"
NODES_OUT = DATA_DIR / "daet_basud_network_nodes.csv"
EDGES_OUT = DATA_DIR / "daet_basud_network_edges.csv"


def _read_wkb(blob: bytes) -> list[list[tuple[float, float]]]:
    """Read LineString/MultiLineString coordinates from a GeoPackage blob."""
    if blob[:2] != b"GP":
        raise ValueError("Feature geometry is not a GeoPackage geometry blob")
    flags = blob[3]
    envelope_code = (flags >> 1) & 0b111
    envelope_sizes = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}
    offset = 8 + envelope_sizes.get(envelope_code, 0)

    def parse(offset: int) -> tuple[list[list[tuple[float, float]]], int]:
        byte_order = blob[offset]
        endian = "<" if byte_order == 1 else ">"
        geom_type = struct.unpack_from(endian + "I", blob, offset + 1)[0]
        offset += 5
        has_z = geom_type >= 1000 and geom_type < 3000
        has_m = geom_type >= 2000
        base_type = geom_type % 1000 if geom_type >= 1000 else geom_type
        dimensions = 2 + int(has_z) + int(has_m)
        if base_type == 2:  # LineString
            count = struct.unpack_from(endian + "I", blob, offset)[0]
            offset += 4
            coords = []
            for _ in range(count):
                values = struct.unpack_from(endian + "d" * dimensions, blob, offset)
                coords.append((values[0], values[1]))
                offset += 8 * dimensions
            return [coords], offset
        if base_type == 5:  # MultiLineString
            count = struct.unpack_from(endian + "I", blob, offset)[0]
            offset += 4
            lines = []
            for _ in range(count):
                part, offset = parse(offset)
                lines.extend(part)
            return lines, offset
        if base_type == 7:  # GeometryCollection (defensive support)
            count = struct.unpack_from(endian + "I", blob, offset)[0]
            offset += 4
            lines = []
            for _ in range(count):
                part, offset = parse(offset)
                lines.extend(part)
            return lines, offset
        raise ValueError(f"Unsupported WKB geometry type {geom_type}")

    lines, _ = parse(offset)
    return lines


def _node_id(lon: float, lat: float) -> str:
    # Keep the source coordinates in WGS 84 and use a deterministic spatial key.
    return f"N{lon:.8f}_{lat:.8f}"


def _distance_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    lon1, lat1 = map(math.radians, a)
    lon2, lat2 = map(math.radians, b)
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * 6_371_008.8 * math.asin(math.sqrt(h))


def main() -> None:
    if not SOURCE.exists():
        raise FileNotFoundError(SOURCE)
    connection = sqlite3.connect(SOURCE)
    connection.row_factory = sqlite3.Row
    table = connection.execute("SELECT table_name FROM gpkg_contents WHERE data_type='features'").fetchone()[0]
    rows = connection.execute(f'SELECT * FROM "{table}" ORDER BY fid').fetchall()

    nodes: dict[str, dict[str, object]] = {}
    edges: list[dict[str, object]] = []
    skipped_short = 0
    for feature in rows:
        fid = feature["fid"]
        for part_index, coordinates in enumerate(_read_wkb(feature["geom"])):
            for segment_index, (a, b) in enumerate(zip(coordinates, coordinates[1:])):
                distance = _distance_m(a, b)
                if distance <= 0:
                    skipped_short += 1
                    continue
                a_id, b_id = _node_id(*a), _node_id(*b)
                for node_id, point in ((a_id, a), (b_id, b)):
                    nodes.setdefault(node_id, {"node_id": node_id, "lon": point[0], "lat": point[1]})
                common = {
                    "osm_fid": fid,
                    "osm_id": feature["osm_id"],
                    "osm_type": feature["osm_type"],
                    "name": feature["name"] or feature["ref"] or "",
                    "highway": feature["highway"] or "",
                    "foot": feature["foot"] or "",
                    "access": feature["access"] or "",
                    "vehicle_oneway": feature["oneway"] or "",
                    "segment_index": segment_index,
                    "length_m": round(distance, 2),
                }
                # Foot routing remains bidirectional by default; OSM oneway is
                # retained as vehicle metadata and is not applied to pedestrians.
                for direction, start, end in (("F", a_id, b_id), ("R", b_id, a_id)):
                    edges.append({
                        "edge_id": f"OSM{fid}_{part_index}_{segment_index}_{direction}",
                        "from_node": start,
                        "to_node": end,
                        **common,
                    })
    connection.close()

    node_fields = ("node_id", "lon", "lat")
    edge_fields = (
        "edge_id", "from_node", "to_node", "osm_fid", "osm_id", "osm_type",
        "name", "highway", "foot", "access", "vehicle_oneway", "segment_index", "length_m",
    )
    for path, fields, records in ((NODES_OUT, node_fields, nodes.values()), (EDGES_OUT, edge_fields, edges)):
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(records)
    named = sum(bool(edge["name"]) for edge in edges)
    print(f"Source features: {len(rows)}")
    print(f"Graph vertices: {len(nodes)}")
    print(f"Directed walking segments: {len(edges)}")
    print(f"Segments with OSM name/ref: {named} ({named / max(len(edges), 1):.1%})")
    print(f"Zero-length consecutive segments skipped: {skipped_short}")
    print(f"Wrote {NODES_OUT.name} and {EDGES_OUT.name}")


if __name__ == "__main__":
    main()
