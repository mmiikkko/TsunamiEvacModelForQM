# Reviewing the Daet–Basud road screening layer in QGIS

This packet is prepared for a human map review. **No road in it has been marked as locally verified.** The component IDs are geometry-screening groups, not official route IDs.

## Open the road map

1. Open the QGIS project you are using for the evacuation study.
2. Add `data/daet_basud_roads.gpkg` and `data/daet_basud_boundary.gpkg` as vector layers. Keep the boundary below the roads and set its fill to transparent so it does not cover the road lines.
3. Use `output/daet_basud_road_review.png` as a quick overview, or open `output/daet_basud_road_review.pdf` for a larger print view. The source roads remain the GeoPackage; the PNG/PDF are review references.
4. Start at Gubat, then trace south through Daet and into Basud. Zoom in around apparent gaps and line crossings. Check bridge/tunnel/layer tags and local knowledge before deciding whether two lines connect for pedestrians.

## Navigate component groups

1. Add `data/daet_basud_component_review.csv` as a **Delimited Text** layer.
2. Set X field to `center_lon`, Y field to `center_lat`, and geometry CRS to **EPSG:4326**. The center coordinate is only an approximate zoom aid for a component; it is not a real road junction or a route endpoint.
3. Label the points with `component_id`. Open the table and use `component_id` to find each group's feature count, OSM road classes, and bounding box.
4. Zoom to component groups along the potential southbound corridor. Review the largest groups first, then inspect nearby smaller groups that might connect them.

## Record findings

For each component or road segment reviewed, fill `review_status` and `review_notes` in a copy of the CSV. Suggested status values:

- `VISUALLY CHECKED` — map geometry reviewed only; local access not confirmed.
- `LOCAL CONFIRMATION NEEDED` — a gap, crossing, sidewalk, bridge, or access issue needs client/local review.
- `CONFIRMED WITH SOURCE` — a named source or responsible local contact confirmed the condition; put the source and date in the notes.

Do not use `CONFIRMED WITH SOURCE` based only on the OSM line or this map. Do not mark a destination as safe or available without evidence of location, access, and usable capacity. Preserve an untouched copy of the original CSV when recording review results.
