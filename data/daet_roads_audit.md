# Preliminary Daet roads and boundary audit

**Audit date:** 2026-11-22  
**Purpose:** record what the current GIS extracts contain before using them to build an evacuation network.

## Files and counts

| File | Contents | Features | CRS |
|---|---|---:|---|
| `data/daet_barangays.gpkg` | Daet (Capital) barangay polygons | 25 | EPSG:4326 |
| `data/daet_boundary.gpkg` | Dissolved outline of those barangays | 1 | EPSG:4326 |
| `data/daet_roads.gpkg` | OSM road/path features clipped to the dissolved Daet outline | 1,102 | EPSG:4326 |
| `data/daet_basud_barangays.gpkg` | Daet and Basud barangay polygons | 54 | EPSG:4326 |
| `data/daet_basud_boundary.gpkg` | Dissolved Daet–Basud screening outline | 1 | EPSG:4326 |
| `data/daet_basud_roads.gpkg` | OSM road/path features clipped to the Daet–Basud screening outline | 1,551 | EPSG:4326 |
| `data/daet_basud_roads_context_100m.gpkg` | Original Daet–Basud road features plus regional OSM road extensions within a 100 m boundary buffer; admin boundary unchanged | 2,018 | EPSG:4326 |

The barangay extract has `ADM3_EN = Daet (Capital)` and `ADM2_EN = Camarines Norte` for all 25 features. It includes Gubat and the other Daet barangays. The source GeoJSON metadata records PSGC version 2023-10-24 and NAMRIA version 2023-11-06; the original download URL, license, and boundary positional accuracy still need confirmation before redistribution or official use.

The roads were clipped from `data/raw/osm_camarines_norte_roads.gpkg`, a 5,276-feature Camarines Norte OSM extract recorded in the project inventory as received 2026-10-16. The Daet-only clip covers Daet. The separately described Daet–Basud screening clip adds Basud road coverage but is still not a validated corridor or route to a confirmed receiving area.

## Daet–Basud screening extent

To support the client's suggestion to consider travel south from Gubat and Daet, a broader screening extent was also created from the same bundled barangay boundary source. The QGIS selection used `ADM3_EN IN ('Daet (Capital)','Basud') AND ADM2_EN = 'Camarines Norte'`. It contains **25 Daet barangays and 29 Basud barangays**. These 54 polygons were dissolved to one outline, then used to clip the unmodified Camarines Norte OSM roads source, producing **1,551 road/path features** in `data/daet_basud_roads.gpkg`.

This is a geographic screening layer, not a recommended evacuation corridor. It includes all roads within Daet and Basud boundaries, rather than only a validated route from Gubat to a known receiving site. No Basud evacuation center has been identified or confirmed by this operation. Use it to inspect the network and discuss candidate destinations with the client; do not route evacuees to an assumed safe location.

The broader clip's OSM `highway` counts are: residential 1,004; service 230; unclassified 90; tertiary 71; trunk 41; track 35; path 27; secondary 26; footway 14; primary 9; and construction 4 (1,551 total). These are feature counts, not road length, capacity, traffic volume, safety, or route connectivity.

## Road classes in the Daet clip

| OSM `highway` value | Features |
|---|---:|
| residential | 756 |
| service | 192 |
| tertiary | 52 |
| unclassified | 36 |
| path | 19 |
| secondary | 14 |
| footway | 11 |
| primary | 9 |
| trunk | 7 |
| track | 6 |
| **Total** | **1,102** |

## Attribute coverage

| Field/tag | Features with a value |
|---|---:|
| `name` | 190 |
| `lanes` | 68 |
| `foot` | 87 |
| `sidewalk` | 18 |
| `width` | 0 |
| `oneway` | 39 |
| `surface` | 125 |
| `bridge` | 13 |

These counts show that the extract is useful for locating candidate streets, but it does not provide enough complete width, sidewalk, lane, direction, or surface data to calculate validated pedestrian capacity or traffic congestion. OSM tags can also be absent even where a feature exists in the field. The client's observation that the national highway has four lanes and is sometimes used as sidewalk space should be recorded as local knowledge for review, not generalized to every road segment.

## Daet Bridge 1 review note

The full regional road source contains two OSM ways tagged `bridge:name=Daet Bridge 1` (including way `241268375` on **F. Pimentel Avenue**), with tags `lanes=4`, `foot=yes`, and `sidewalk=both` on way `241268375`. The project inventory dates receipt of this source extract to 2026-10-16. The user reports that the fourth lane has since opened following renovation; the source lane tag is useful evidence, but it does not record when the lane opened or independently confirm the current configuration.

**Original clip gap:** neither Daet Bridge 1 way is present in `data/daet_roads.gpkg` or `data/daet_basud_roads.gpkg`; OGR geometry checks place the source ways approximately 14 m and 24 m outside the working Daet boundary. The administrative boundary remains unchanged. To preserve the bridge and approaches without changing that boundary, `data/build_daet_context_roads.py` now creates `data/daet_basud_roads_context_100m.gpkg`: it keeps the original 1,551 Daet–Basud road geometries and adds regional OSM road geometry within a 100 m buffer around the Daet–Basud outline. The resulting graph contains the two bridge ways and they share a raw geometry component with the mapped approaches and Gubat candidate origins. This is still only a topological screen, not confirmation of pedestrian access or safety. The app's Road coverage panel identifies the added context and its limitations.

Do not model the four vehicle lanes as four pedestrian routes or infer pedestrian carrying capacity from the lane count. Confirm current pedestrian access, crossing arrangement, usable walking space, bridge condition, and closure/evacuation procedures with the client or DPWH before using the bridge in a route scenario. Keep the user-reported opening separate from verified source metadata.

## Current interpretation and next GIS checks

- Treat the clips as preliminary geometry and classification layers, not an approved evacuation-route inventory.
- Review the road lines against aerial imagery and local knowledge for gaps, overpasses/bridges, intersections, pedestrian access, and disconnected geometry. A line crossing on the map does not automatically mean the network is connected.
- Review the Daet–Basud screening extent and, with the client, narrow it to a plausible southbound corridor; identify candidate destinations only after the client or local authorities confirm them.
- Before building the simulation graph, normalize the selected network, create stable segment IDs, inspect routing connectivity and direction rules, and document which pedestrian speed/capacity values are measured versus scenario assumptions.
- Add field/adviser review for sidewalks, highway crossing behavior, tricycle/motorcycle traffic, congestion, and accessibility needs (elderly residents, children, and PWDs).

## Attribution and use

The roads originate from OpenStreetMap. Attribute © OpenStreetMap contributors and follow ODbL terms when using or sharing the data. Do not describe the OSM extract as authoritative or field-verified. The boundary source's redistribution terms have not yet been confirmed.
