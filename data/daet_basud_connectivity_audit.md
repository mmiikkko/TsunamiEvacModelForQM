# Preliminary Daet–Basud road connectivity diagnostic

**Audit date:** 2026-11-22  
**Input:** `data/daet_basud_roads.gpkg` (1,551 OSM road/path features, EPSG:4326)  
**Purpose:** identify issues to review before converting the regional screening roads into a routable pedestrian network.

## Vertex-based diagnostic

The clipped line geometries were read as line parts, then each consecutive pair of coordinates was counted as a segment. Coordinates rounded to 8 decimal places were treated as the same vertex. This produced **12,369 segments** and **11,892 unique vertices**, arranged in **136 vertex-connected components**. The five largest components contain 1,691, 1,508, 1,043, 905, and 622 segments. The vertex degrees were: 9,243 degree-2 vertices, 1,443 degree-3 vertices, 239 degree-4 vertices, and 967 degree-1 vertices. Component navigation centers and review fields are in `data/daet_basud_component_review.csv`.

Approximate segment lengths, calculated as great-circle distances from the WGS 84 coordinates, had a median of about **22 m** and a maximum of about **672 m**. Twenty-two segments were shorter than 1 m, and 547 were shorter than 5 m; these may include short connectors or geometry artifacts and should be inspected before graph construction.

## How to interpret this result

This is a **geometry screening diagnostic**, not proof that the streets form 136 real-world disconnected networks. OSM line endpoints and shared vertices reveal some connections, but this check does not split lines at every geometric crossing. Conversely, a map crossing can be a bridge or other grade-separated crossing that should not connect pedestrians. The coordinate tolerance, clipped boundary ends, duplicate or near-duplicate lines, and short segments can also affect the counts.

Therefore:

- Do not treat this diagnostic as a validated routability test or as evidence that any route is safe.
- Review the largest components and the component breaks on a map; check apparent crossings, bridge/tunnel/layer tags, and connections at Daet/Basud boundary edges.
- Snap or split only where a real at-grade connection is supported by geometry and local knowledge. Preserve grade separation and pedestrian access restrictions.
- Exclude or explicitly handle `construction` features and other roads that are not usable by pedestrians.
- Re-run connectivity after cleanup and inspect whether Gubat origins connect to locally confirmed destinations.

The print overview is `output/daet_basud_road_review.png` (also available as PDF). See `data/daet_basud_review_instructions.md` for loading the component index in QGIS and recording a human review. The review-status fields currently remain `NOT REVIEWED`.

No edge capacities, lane assumptions, walking speeds, shelters, or population estimates were inferred from this connectivity count. The app remains on the schematic R1–R12 graph until the road graph and scenario inputs are reviewed and integrated.

## Gubat origin candidate proximity screen

`audit_origin_access.py` creates `origin_access_review.csv` from the current named-area anchors, selected candidate graph nodes, OSM road geometries, and preliminary vertex graph. It keeps nearest-road-line distance separate from selected-node distance and records the OSM way tags and candidate node's raw graph component. The current measurements are:

| Origin anchor | Nearest mapped road geometry | Recorded graph node | Raw component | Other included origins in component |
|---|---:|---:|---|---|
| Roseville Subdivision | 163.0 m | 163.0 m | C046 (21 vertices) | None |
| Cleofe Ecology Village | 13.4 m | 38.3 m | C005 (622 vertices) | Mandulongan (Purok Tsiko) |
| Mandulongan (Purok Tsiko) | 24.6 m | 25.1 m | C005 (622 vertices) | Cleofe Ecology Village |

The measurements are a triage screen only. The Roseville gap is a priority for map inspection; the smaller distances at the other anchors still do not confirm a gate, walkable connector, road crossing, or safe access. All candidate access records remain `REVIEW_REQUIRED`. Do not add connectors or merge graph components from proximity alone. The Streamlit Road coverage panel displays the report and provides its CSV download for QGIS/local review.
