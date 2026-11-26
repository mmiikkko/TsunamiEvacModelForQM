"""Small GeoPackage reader for the app's interactive Plotly map.

The project layers are EPSG:4326 GeoPackages. This deliberately narrow reader
supports the OGC WKB line and polygon geometry types used by those layers.
"""

from __future__ import annotations

import sqlite3
import struct
from pathlib import Path
from typing import Any


def _parse_wkb(blob: bytes, offset: int) -> tuple[dict[str, Any], int]:
    byte_order = blob[offset]
    endian = "<" if byte_order == 1 else ">"
    raw_type = struct.unpack_from(endian + "I", blob, offset + 1)[0]
    offset += 5
    if raw_type >= 3000:
        geom_type, dimensions = raw_type - 3000, 4
    elif raw_type >= 2000:
        geom_type, dimensions = raw_type - 2000, 3
    elif raw_type >= 1000:
        geom_type, dimensions = raw_type - 1000, 3
    else:
        geom_type, dimensions = raw_type, 2

    def point_list(count: int, offset: int) -> tuple[list[list[float]], int]:
        coords = []
        for _ in range(count):
            values = struct.unpack_from(endian + "d" * dimensions, blob, offset)
            coords.append([values[0], values[1]])
            offset += 8 * dimensions
        return coords, offset

    if geom_type == 2:  # LineString
        count = struct.unpack_from(endian + "I", blob, offset)[0]
        coords, offset = point_list(count, offset + 4)
        return {"type": "LineString", "coordinates": coords}, offset
    if geom_type == 3:  # Polygon
        ring_count = struct.unpack_from(endian + "I", blob, offset)[0]
        offset += 4
        rings = []
        for _ in range(ring_count):
            count = struct.unpack_from(endian + "I", blob, offset)[0]
            ring, offset = point_list(count, offset + 4)
            rings.append(ring)
        return {"type": "Polygon", "coordinates": rings}, offset
    if geom_type in (5, 6, 7):  # MultiLineString, MultiPolygon, GeometryCollection
        count = struct.unpack_from(endian + "I", blob, offset)[0]
        offset += 4
        children = []
        for _ in range(count):
            child, offset = _parse_wkb(blob, offset)
            children.append(child)
        if geom_type == 5:
            return {"type": "MultiLineString", "coordinates": [child["coordinates"] for child in children]}, offset
        if geom_type == 6:
            return {"type": "MultiPolygon", "coordinates": [child["coordinates"] for child in children]}, offset
        return {"type": "GeometryCollection", "geometries": children}, offset
    raise ValueError(f"Unsupported GeoPackage WKB geometry type: {raw_type}")


def read_gpkg_features(path: str | Path, table: str | None = None) -> list[dict[str, Any]]:
    """Return feature properties and GeoJSON-compatible geometries from a GPKG."""
    path = Path(path)
    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row
        if table is None:
            row = connection.execute(
                "SELECT table_name FROM gpkg_contents WHERE data_type='features' LIMIT 1"
            ).fetchone()
            if row is None:
                raise ValueError(f"No feature table found in {path}")
            table = row[0]
        # Table name comes from the GeoPackage catalog, not user input.
        quoted = '"' + table.replace('"', '""') + '"'
        rows = connection.execute(f"SELECT * FROM {quoted}").fetchall()
        geometry_column = connection.execute(
            "SELECT column_name FROM gpkg_geometry_columns WHERE table_name=?", (table,)
        ).fetchone()[0]

    features = []
    for row in rows:
        blob = row[geometry_column]
        flags = blob[3]
        envelope_code = (flags >> 1) & 0b111
        envelope_sizes = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}
        geom, _ = _parse_wkb(blob, 8 + envelope_sizes.get(envelope_code, 0))
        features.append({
            "type": "Feature",
            "geometry": geom,
            "properties": {key: row[key] for key in row.keys() if key != geometry_column},
        })
    return features

