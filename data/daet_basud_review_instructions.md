# Reviewing the Daet–Basud road screening layer in QGIS

This packet is prepared for a human map review. **No road in it has been marked as locally verified.** The component IDs are geometry-screening groups, not official route IDs.

## Open the road map

1. Open the QGIS project you are using for the evacuation study.
2. Add `data/daet_basud_roads_context_100m.gpkg` and `data/daet_basud_boundary.gpkg` as vector layers. The road layer extends up to 100 m beyond the unchanged administrative boundary; keep the boundary below the roads and set its fill to transparent.
3. Use `output/daet_basud_road_review.png` as a quick overview, or open `output/daet_basud_road_review.pdf` for a larger print view. The source roads remain the GeoPackage; the PNG/PDF are review references.
4. Start at Gubat, then trace south through Daet and into Basud. Zoom in around apparent gaps and line crossings. Check bridge/tunnel/layer tags and local knowledge before deciding whether two lines connect for pedestrians.

## Review the named Gubat origin access candidates

Regenerate the screening records when source anchors or the graph changes:

```powershell
.\.venv\Scripts\python.exe data\audit_origin_access.py
```

1. Add `data/origin_access_review_points.geojson`, `data/origin_access_review_offsets.geojson`, and `data/daet_basud_roads_context_100m.gpkg` to QGIS.
2. Keep the roads at the bottom, the offset lines above them, and the review points at the top. Use categorized symbology on the points' `feature_role` field: distinguish `origin_anchor`, `candidate_graph_node`, and `nearest_road_geometry_point`. Style the two line roles differently and label them as proximity/offset only.
3. Inspect each anchor at neighborhood scale. Compare the closest mapped road point and recorded graph node to actual mapped streets, gates, crossings, and access restrictions. Roseville is about 66 m from the nearest mapped line and 163 m from its recorded graph node. Cleofe Ecology Village is about 13 m from a mapped line and Mandulongan about 25 m; every candidate still needs the same access review.
4. The straight connectors are not paths and must not be used to merge network components or to calculate evacuation times. Use the CSV `data/origin_access_review.csv` to see the measurements, OSM tags, and raw graph component IDs. All statuses start as `REVIEW_REQUIRED`.
5. Record only the visual map finding in a separate review copy. Mark local access `LOCAL CONFIRMATION NEEDED` unless a responsible source confirms the entrance and pedestrian connection; record the source and date if confirmation is obtained.

## Navigate component groups

1. Add `data/daet_basud_component_review.csv` as a **Delimited Text** layer.
2. Set X field to `center_lon`, Y field to `center_lat`, and geometry CRS to **EPSG:4326**. The center coordinate is only an approximate zoom aid for a component; it is not a real road junction or a route endpoint.
3. Label the points with `component_id`. Open the table and use `component_id` to find each group's feature count, OSM road classes, and bounding box.
4. Zoom to component groups along the potential southbound corridor. Review the largest groups first, then inspect nearby smaller groups that might connect them.

## Review nearest gaps between components

1. Add `data/daet_basud_component_gap_review.geojson` above the road layer. Style it as a thin dashed magenta line and label with `review_rank` and `gap_distance_m`. These are straight lines between nearest graph nodes, not road links.
2. Open `data/daet_basud_component_gap_review.csv` and review the smallest `review_rank` values first. It lists 666 nearest-node pairs (one for each pair among 37 components) with component sizes, coordinates, nearby road names, OSM way IDs, and a `NOT REVIEWED` status. The GeoJSON contains the closest 100 pairs for map navigation.
3. Zoom to each pair and inspect the underlying road geometry, OSM way IDs, bridge/tunnel/layer tags, nearby intersections, and any visible barriers. Seven of the eight pairs under 5 m share an OSM way ID at both ends; treat these as precision-review candidates, not automatic connections.
4. Record findings in a copy of the CSV. Do not add these red/magenta indicators as roads, snap the graph from distance alone, or infer that a crossing is at grade or pedestrian-accessible.

## Record findings

For each component or road segment reviewed, fill `review_status` and `review_notes` in a copy of the CSV. Suggested status values:

- `VISUALLY CHECKED` — map geometry reviewed only; local access not confirmed.
- `LOCAL CONFIRMATION NEEDED` — a gap, crossing, sidewalk, bridge, or access issue needs client/local review.
- `CONFIRMED WITH SOURCE` — a named source or responsible local contact confirmed the condition; put the source and date in the notes.

Do not use `CONFIRMED WITH SOURCE` based only on the OSM line or this map. Do not mark a destination as safe or available without evidence of location, access, and usable capacity. Preserve an untouched copy of the original CSV when recording review results.
