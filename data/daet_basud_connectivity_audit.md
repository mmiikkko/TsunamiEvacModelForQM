# Preliminary Daet–Basud road connectivity diagnostic

**Audit date:** 2026-11-23  
**Current input:** `data/daet_basud_roads_context_100m.gpkg` (2,018 OSM road/path geometries, EPSG:4326), preserving `data/daet_basud_roads.gpkg` and adding regional-road geometry within 100 m of the unchanged Daet–Basud administrative outline.  
**Purpose:** identify candidate graph connections that need review before any route interpretation. The context buffer is not a boundary edit or a validated evacuation corridor.

## Vertex-based diagnostic

The candidate graph is built from consecutive line vertices with shared coordinates connected; each physical segment is written as two directed walking edges. The context graph has **14,061 physical segments**, **13,319 unique vertices**, and **37 vertex-connected components**. The five largest components contain 12,714, 370, 36, 25, and 25 vertices. All three current named Gubat origin candidate nodes and both Daet Bridge 1 ways are in component C001 (12,714 vertices). The component navigation centers are regenerated from this graph in `data/daet_basud_component_review.csv`; all rows remain `NOT REVIEWED`.

For comparison, the earlier graph from the boundary-only `data/daet_basud_roads.gpkg` had 12,369 physical segments, 11,892 vertices, and 136 shared-vertex components. The 100 m road-context extension therefore adds mapped outside-boundary approaches and joins several graph fragments, but it does not establish that each connection is usable by pedestrians.

The 37 components produce **666 nearest-component-pair candidates** in `data/daet_basud_component_gap_review.csv`; the top 100 are drawn as proximity-only indicators in `data/daet_basud_component_gap_review.geojson`. Eight pairs are within 5 m, and seven of those share at least one OSM way ID across both endpoints. This pattern makes endpoint precision or split geometry worth inspecting, but it does not prove a real at-grade pedestrian connection. No gap was snapped or added to the graph. See `data/daet_basud_review_instructions.md` for the QGIS review steps.

The base clip's earlier diagnostic measured a median segment length of about **22 m** and a maximum of about **672 m**. Those length statistics have not been recomputed for the buffered context graph.

## Provisional QGIS review of the highest-ranked gaps

Ranks 1–6 in the proximity queue were reviewed against the close-up map figure `output/daet_component_gap_top6_review.png`. Their paired endpoints render on or immediately beside the same mapped road geometry; the listed OSM way IDs are shared at both endpoints for each pair. The locations include Diego Naing, Governor Panotes Avenue/Lakan Street, Amoguis, and J. Lukban Extension. This is a **map-only observation** that prioritizes endpoint precision or split-geometry investigation. It does not establish an at-grade connection, pedestrian access, or a safe route. No graph edits or connectors were made. The original queue remains untouched; statuses and notes are copied to `data/daet_basud_component_gap_review_map_notes.csv`. Ranks 7–10 have not received this close-up review.

## How to interpret this result

This is a **geometry screening diagnostic**, not proof that streets form 37 real-world disconnected networks or that roads in C001 form a usable route. OSM line endpoints and shared vertices reveal some connections, but this check does not split lines at every geometric crossing. Conversely, a map crossing can be a bridge or other grade-separated crossing that should not connect pedestrians. Clipped boundary ends, duplicate or near-duplicate lines, and short segments can also affect the counts.

Therefore:

- Do not treat this diagnostic as a validated routability test or as evidence that any route is safe.
- Review the largest components and the component breaks on a map; check apparent crossings, bridge/tunnel/layer tags, and connections at Daet/Basud boundary edges.
- Snap or split only where a real at-grade connection is supported by geometry and local knowledge. Preserve grade separation and pedestrian access restrictions.
- Exclude or explicitly handle `construction` features and other roads that are not usable by pedestrians.
- Re-run connectivity after cleanup and inspect whether Gubat origins connect to locally confirmed destinations.

The print overview is `output/daet_basud_road_review.png` (also available as PDF). See `data/daet_basud_review_instructions.md` for loading the component index in QGIS and recording a human review. The review-status fields currently remain `NOT REVIEWED`.

No edge capacities, lane assumptions, walking speeds, shelter status, or population estimates were inferred from this connectivity count. The geographic graph supports candidate map-pin route screening; the separate R1–R12 tables still use a schematic demo network. Neither output is an approved evacuation route.

## Gubat origin candidate proximity screen

`audit_origin_access.py` creates `origin_access_review.csv` from the current named-area anchors, selected candidate graph nodes, OSM road geometries, and preliminary vertex graph. It keeps nearest-road-line distance separate from selected-node distance and records the OSM way tags and candidate node's raw graph component. The current measurements are:

| Origin anchor | Nearest mapped road geometry | Recorded graph node | Raw component | Other included origins in component |
|---|---:|---:|---|---|
| Roseville Subdivision | 65.8 m | 163.0 m | C001 (12,714 vertices) | Cleofe Ecology Village; Mandulongan (Purok Tsiko) |
| Cleofe Ecology Village | 13.4 m | 38.3 m | C001 (12,714 vertices) | Roseville Subdivision; Mandulongan (Purok Tsiko) |
| Mandulongan (Purok Tsiko) | 24.6 m | 25.1 m | C001 (12,714 vertices) | Roseville Subdivision; Cleofe Ecology Village |

The measurements are a triage screen only. The Roseville gap is a priority for map inspection; the smaller distances at the other anchors still do not confirm a gate, walkable connector, road crossing, or safe access. All candidate access records remain `REVIEW_REQUIRED`. Do not add connectors or merge graph components from proximity alone. The Streamlit Road coverage panel displays the report and provides its CSV download for QGIS/local review.
