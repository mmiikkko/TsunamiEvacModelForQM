# Candidate walking-route model: current assumptions

**Reviewed:** 2026-11-25  
**Network source:** `data/daet_basud_roads_context_100m.gpkg`, an OpenStreetMap-derived road/path extract recorded as received on 2026-10-16.  
**Purpose:** explain what the app currently computes and which parts still need map or local review.

## What “shortest route” means in the app

The app runs a weighted shortest-path search on the candidate road graph. Every included segment is assigned the same assumed walking speed: **1.15 m/s × the walking-speed multiplier**. Since the same speed is applied to every segment, minimizing modeled walking time is mathematically the same as minimizing mapped segment length. The speed multiplier changes displayed travel-time estimates but does not change the selected route.

For origin groups, the app finds paths to reachable pins, then assigns whole groups subject to the user's origin-to-pin share settings and each pin's entered capacity. A shortest path to a pin does not mean that the pin itself is the nearest or best destination; shares and remaining capacity affect assignment.

The pin-to-pin line is the shortest-distance path in the current filtered graph. It demonstrates graph connectivity only. It is not a reviewed, safe, officially designated, or guaranteed usable route.

## Current pedestrian-link filtering

- `highway=construction` is excluded.
- Explicitly restrictive `foot` values (`no`, `private`, `restricted`, `customers`, `delivery`, `permit`, `use_sidepath`) are excluded.
- Explicitly permissive `foot` values (`yes`, `designated`, `permissive`, `official`) take precedence over a general `access` restriction.
- When `foot` does not explicitly allow access, general `access` values `no`, `private`, `restricted`, `customers`, `delivery`, and `permit` are excluded.
- Missing/other access tags remain candidate links. They are not confirmed as publicly walkable.
- Vehicle `oneway` tags are retained as metadata but are not applied to pedestrians. The derived pedestrian graph is bidirectional; no pedestrian-specific direction rule is currently represented in the source fields.

The access filter is a screening rule, not a complete interpretation of all OSM access tagging or local regulations.

## Attribute coverage in the current graph

The graph contains **14,061 physical vertex-to-vertex segments** (represented by directed forward/reverse records in the CSV). Among the physical segments:

| Attribute | Tagged | Blank |
|---|---:|---:|
| `foot` | 999 | 13,062 |
| `access` | 146 | 13,915 |
| vehicle `oneway` | 141 | 13,920 |
| `surface` | 2,261 | 11,800 |
| `maxspeed` | 40 | 14,021 |
| `sidewalk` | 140 | 13,921 |
| `width` | 0 | 14,061 |
| `smoothness` | 0 | 14,061 |

The graph export now preserves `surface`, `smoothness`, `width`, `maxspeed`, `footway`, and `sidewalk:left` fields when they exist in the source. These attributes are retained for review; they are **not** yet used to assign different walking speeds or capacities. `maxspeed` is a vehicle road tag and should not be interpreted as pedestrian speed.

## What the current travel-time estimate omits

Travel time does not model congestion, crowd density, road width/capacity, surface-specific speeds, slope, crossings/intersections, bridge approach or crossing delay, mobility differences, closures, or time-varying tsunami inundation. The graph is built by connecting shared line vertices and does not establish that every crossing is at grade or accessible to pedestrians. A visible geometric connection may still be blocked, private, unsafe, or absent in the field.

## Review needed before describing a route as efficient or usable

1. Inspect route-relevant graph gaps and apparent crossings in QGIS; preserve bridge/tunnel/grade separation.
2. Confirm pedestrian entrances, access restrictions, bridges, sidewalks, and current closures with local knowledge or an authoritative source.
3. Ask the client/advisers for defensible walking-speed assumptions, including any accessibility scenarios. Keep values labeled as assumptions until then.
4. Only after the road network and assumptions are reviewed should the app compare routes as candidate alternatives. Do not present the current route as an emergency recommendation.

The next GIS review can use `data/daet_basud_review_instructions.md`, `data/daet_basud_component_gap_review.csv`, and the QGIS review-status fields. Current component and gap screens remain preliminary.
