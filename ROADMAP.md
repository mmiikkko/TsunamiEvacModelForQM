# Project Roadmap

## Project objective

Build an interactive geographic scenario application for Barangay Gubat and the evacuation network across Daet, with routes extending south and potentially to confirmed destinations in Basud. The map is the main interface: users should be able to zoom and pan, inspect hazard and road layers, change scenario settings, and see geographic route assignments and time-based results on the map.

The intended time view must keep two processes distinct: evacuation progress from the discrete-event model, and tsunami inundation over time. The supplied tsunami layer contains static maximum inundation-depth classes, not a time series. A true moving inundation view requires time-dependent hazard data or a separate defensible physical model. A simplified illustrative front is possible only if it is prominently labeled as an assumption and never presented as a local forecast.

## Current baseline

- A QGIS layout and PDF show a static Gubat exposure map; they are useful references but are not the target interactive scenario map.
- The Streamlit app has an interactive GIS map using the Gubat hazard/boundary GeoPackages and the Daet–Basud candidate road graph, with extent and layer controls. The user confirmed the three extents, zoom/pan, and layer toggles work. Map-linked scenario outputs and time playback are not implemented.
- Named-area synthetic groups are now assigned to the QGIS-reviewed candidate OSM graph node for their area; the interactive map displays these node markers with scenario totals and reports raw graph-component relationships. This is a geographic origin-to-network attachment only.
- The route calculations still use a schematic 12-edge network and synthetic receiving-area/road-capacity data. R1-R12 are sample edge IDs, not real road names. The client reports there is no definite official evacuation location; potential receiving areas (for example, schools or SM) may be considered, but their use, access, and capacity are unverified. No evacuation paths are presented as real routes.
- The geographic map now has a first-pass multi-origin/multi-pin route screening workflow: users can select named Gubat origin areas, set scenario evacuee amounts under the provisional Gubat-wide limit, add multiple road-node candidate receiving pins, enter a total headcount limit for each pin, and set a planned percentage from each origin to each pin. Whole synthetic groups are assigned in departure order toward those share targets while respecting entered pin limits. It remains a screening preview on unreviewed OSM geometry; it does not model destination service rates, road queues, moving tsunami water, or verified pedestrian access.
- A Daet boundary, Daet-only OSM roads, and a broader Daet–Basud OSM road clip are saved. The candidate vertex graph has not passed a full road connectivity, pedestrian-access, crossing, or local safety review.
- The current tsunami file contains six static inundation-depth classes. It does not provide wave-arrival times, time slices, bathymetry, or a numerical elevation surface for modeling land flow.

## Roadmap

### 1. Lock the study scope and questions — in progress

- Keep the local exposure map centered on Gubat.
- Expand the evacuation-network extent along connected roads through southern Daet.
- Treat schools, SM, and other client-suggested places as **candidate receiving areas for scenario exploration**, not designated evacuation centers. Record their coordinates, access, possible use, capacity evidence, and source; show unverified attributes as unknown. The client has said there is no definite official evacuation location.
- Decide whether the research evaluates evacuation progress against a static hazard scenario, or also includes a time-varying tsunami model. Do not promise an animation until its data and method are defined.
- Keep the distinction clear between tsunami inundation extent/depth, tsunami arrival time, and evacuation completion time.

**Exit condition:** agreed study area, questions, outputs, and explicit limits recorded in the paper and app.

### 2. Audit and prepare the geographic inputs — in progress

- Inspect the available road GeoPackage for Daet and the southbound corridor toward Basud. Clip a working copy to the agreed study extent while preserving the original source.
- Check road connectivity, directionality, pedestrian access, highway crossings, bridges, sidewalks/roadside walking space, and missing links. OSM attributes and geometry are starting evidence, not field verification.
- Confirm the tsunami layer's coverage, depth-class meanings, source, date, and permitted interpretation. Record that it is static unless time-resolved data are obtained.
- Identify candidate receiving areas with the client/local authorities. A school or SM may be evaluated as a possible receiving area only if the client/local source supports considering it. Record name/location, access, permission/use status, any usable-capacity evidence, and source; leave unknown values unknown. Do not label candidate places as official shelters or safe sites without confirmation.
- Obtain population inputs as privacy-preserving origin zones (for example, barangay, purok, or suitably aggregated grid cells), not as counts attached to identifiable household points. Store only zone-level totals and demographic aggregates needed by the model; avoid names, household IDs, and precise resident-level records.
- Record each dataset's source, date, CRS, extent/resolution, license, confidence, and transformations in `data/data_sources.csv`.

**Completed in this step so far:** exported the 25 Daet (Capital) barangays, dissolved them to one working outline, and clipped 1,102 OSM road/path features to Daet. Also prepared a broader screening layer with 25 Daet and 29 Basud barangays and clipped 1,551 OSM road/path features to the combined boundaries. A preliminary vertex-based connectivity diagnostic found 136 components; a review map and component navigation CSV are ready. The combined road layer has been loaded in QGIS and visually screened at its full extent: road coverage is densest around the central built-up area and becomes more dispersed toward the southern extent. This is an initial map-level observation only; individual component breaks, pedestrian access, crossings, and continuity toward Basud have not been checked or locally confirmed. All component review statuses remain unreviewed. A candidate graph is now exported by `data/build_osm_road_graph.py` as `data/daet_basud_network_nodes.csv` and `data/daet_basud_network_edges.csv` (11,892 vertices; 12,369 physical vertex-to-vertex segments represented in both walking directions). The app now uses the static Gubat exposure map as the main scenario-page image. A collapsed reference section retains the synthetic R1-R12 graph that still drives the demo calculations; the map and candidate graph are not geographically linked. The regional road overview and PDF remain in a separate screening panel. See `data/daet_roads_audit.md`, `data/daet_basud_connectivity_audit.md`, `data/daet_basud_component_review.csv`, and `data/daet_basud_review_instructions.md`. These are preparation and screening results, not field validation or a confirmed evacuation corridor. Basud destinations remain unconfirmed.

**Exit condition:** documented, reviewable geographic inputs and a list of unresolved data gaps.

### 3. Build the interactive geographic map — target experience

- Replace the map PNG as the operative map with a zoomable, pannable GIS view using the Gubat boundary and inundation polygons plus the Daet road network, with a regional view for southern Daet and any confirmed Basud destinations.
- Add layer controls and a clear legend for hazard-depth classes, roads, barangay boundaries, population origins, destinations, and assigned routes. Do not show incomplete building data as a complete household inventory.
- Let a user click the map to place a **candidate receiving-area pin** instead of requiring a preloaded official shelter. Display the selected coordinate, nearest pedestrian-network node, snap distance, and whether it is connected to the selected origin. Treat the pin as a scenario input, not proof that the location is safe or available.
- Make scenario changes visibly update geographic route closures, assignments, route loads, destination counts, and evacuation progress as appropriate inputs become available.
- Attribute OSM and all other map sources correctly; retain the static QGIS export as a printable/downloadable map, not as the app's only map.

**Exit condition:** reviewed static maps that can be interpreted without confusing hazard classes, buildings, and routes.

### 4. Replace the schematic road graph

- Review the preliminary candidate graph in `data/daet_basud_network_edges.csv` and confirm/split/merge links where GIS geometry and local knowledge support a real at-grade pedestrian connection. The current graph follows shared vertices only and must not be described as a fully connected route network.
- Convert the reviewed road network into simulation graph edges with stable IDs and human-readable road/segment descriptions. The current export has OSM name/ref tags for only some edge records; retain stable segment IDs and show those where no name is recorded.
- Represent permitted pedestrian directions, road/path type, lengths, and capacity assumptions. Distinguish the four-lane national highway from usable pedestrian space; do not assume all lanes or shoulders serve evacuees in the same way.
- Replace the R1-R12 closure control with meaningful segment labels and use it only for documented scenario closures.
- Add geographically referenced origin areas and client/local-reviewed candidate receiving areas in the expanded study area. The model may compare explicitly assumed candidate destinations even when there is no official evacuation location, but must disclose unverified permission, access, and capacity and must not call them official shelters or certified safe areas. No receiving destinations in Basud are currently confirmed.
- Support a user-placed map destination pin: validate it is near an allowed pedestrian link, snap to the graph only within a documented tolerance, report the offset and graph component, and refuse to draw a route when the destination is disconnected or beyond that tolerance. A pin is not a verified entrance; local access and receiving-area status remain explicit fields.
- Current implementation checkpoint: the three included Gubat residential-area scenario origins are linked to recorded candidate graph nodes, and their synthetic group allocations appear at those nodes. The table/map reports raw graph-component relationships; the Roseville candidate falls in a separate geometry component from the other two candidates. This diagnostic ignores missing OSM links, barriers, crossings, and actual access.
- A reproducible origin-access screen now records nearest mapped road-line distance separately from selected candidate-node distance, relevant OSM tags, and raw graph component IDs. It flags Roseville's 163 m proximity gap for review and shows Cleofe and Mandulongan in the same component. All three remain unreviewed for entrances, pedestrian access, crossings, and field continuity; no snap or artificial connector was added.

**Exit condition:** routes can be traced on the regional map, and edge attributes and limitations are reviewable.

### 5. Replace synthetic population and mobility assumptions

- Model evacuees from anonymous geographic zones. Use barangay/purok/grid aggregates where permitted; if only a barangay total is available, use one clearly labeled representative origin for that area rather than fabricating household counts. Any allocation of an aggregate total among smaller cells must use documented, approved weights and remain explicitly estimated.
- The project-provided `2024 CBMS Total Population.xlsx` gives a preliminary Gubat barangay-level aggregate of 6,502 household members and 1,680 responding households. It is recorded in `data/origin_zones.csv`, but is not yet connected to calculations. Confirm the table's reference period, definitions, and permitted use. Do not use protected household/building-point counts. A representative area/access point is the privacy-preserving starting method; finer zones require approved, sufficiently aggregated and disclosure-safe totals.
- Represent elderly residents, children, and PWDs with aggregate counts or explicit scenario shares and suitable assistance/speed assumptions; never infer individual needs from identifiable records.
- Treat one vehicle per household and local vehicle mix (including tricycles and motorcycles) as scenario assumptions until aggregate ownership, driver availability, passenger capacity, and boarding/pickup arrangements are confirmed.
- Model congestion and vehicle interactions only if data and project scope support them. Otherwise, state their limits and compare clearly labeled scenarios.
- A separate synthetic group generator creates anonymous 5–10 person parties and configurable 2–3 person small-party draws with reproducible randomized departure times. The app now lets users set scenario evacuee amounts for selected Gubat candidate origins and assign each origin's planned share among selected candidate receiving pins, subject to per-pin headcount limits. These amounts/shares are scenario choices; approved locality-level population aggregates are not available. The coordinates are candidate place anchors, not household points, official zone polygons, or validated access points. Del Rosario is a separate barangay in Mercedes and remains outside Gubat's scenario unless a distinct approved aggregate is added for a broader model. Borabod and roadside-home aggregate origins are not yet represented.

**Exit condition:** every population, mobility, and vehicle input has a source or is clearly marked as a provisional scenario.

### 6. Implement and explain the evacuation simulation

- Build on the discrete-event simulation approach for time-ordered departures, travel, queues/capacity constraints, and arrivals at destinations.
- Define “most efficient” as a specific objective (initially shortest estimated walking time on the reviewed graph). Later compare capacity-aware assignments when several groups share links or a destination; do not call a geometric shortest path optimal under crowding.
- Overlay the static maximum-inundation classes only as hazard screening. A route “during tsunami” can be evaluated against moving water only after time-dependent, locally suitable inundation/arrival data and a defensible route-closure rule are available. Until then, label output as a static-hazard scenario and make no claim that the route beats the wave or is safe.
- Report evacuation progress over time on the map, including route assignments, bottlenecks, unserved people, and destination-capacity exceedance.
- Use sensitivity/scenario comparisons for departure delay, walking speed, group assistance, road capacity, closures, and any vehicle/tricycle assumptions.
- Keep evacuation completion time separate from tsunami arrival time. Without validated time-resolved hazard data, do not claim that the simulation predicts whether evacuees beat the wave.

**Exit condition:** results are reproducible from documented inputs and limitations are visible beside outputs.

### 7. Implement a time view for tsunami inundation with an explicit evidence level

- The supplied polygons are depth classes only; inspect their provenance and seek time-stamped extents, arrival-time rasters, or model outputs if available.
- If those inputs remain unavailable, implement a tsunami-front animation only as a separate illustrative scenario with an exposed user-adjustable rate/direction and a persistent warning that it is not a forecast or evacuation-safety clock. Do not infer an inland travel time from the static depth classes or apply offshore wave speed directly over land.
- A physically meaningful local wave animation requires a suitable hydrodynamic model, earthquake/source scenario, bathymetry/topography, boundary conditions, friction/land-cover treatment, and validation.

**Exit condition:** either a sourced and validated time-dependent hazard feature, or an explicit decision to keep the hazard static for this project.

### 8. Align the paper with the implemented project

- Build the review of related literature from accessible, verifiable scholarly and official sources; replace inaccessible references and revise claims that depended on them.
- Update the introduction and methodology to match the expanded Gubat–southern Daet–potential Basud study area, actual data sources, DES design, population groups, mobility assumptions, and the static/time-dependent hazard decision.
- Keep unpublished instructor modules out of the reference list; retain relevant concepts only when supported by published sources.
- Follow the provided IEEE conference template. Add results and conclusions only after the model is implemented and reviewed.

**Exit condition:** the paper describes what the app actually does, cites accessible sources, and distinguishes verified data from assumptions.

### 9. Improve the app, validate, and share

- Redesign the Streamlit interface around the interactive geographic map, with layer controls, scenario controls, time playback, map-linked results, sources, and limitations.
- Use clear names, accessible colors, and concise explanations. Make it visually distinct from a generic default dashboard without hiding assumptions.
- Review outputs with the client/adviser and compare them against known routes and feasible travel/capacity assumptions.
- Before deployment, commit and push the required app assets and code; check repository visibility and remove/private any household-identifying or sensitive location data.
- For the current Streamlit app, use Streamlit Community Cloud for the simplest GitHub-based shareable link. Consider Vercel only if the interface is rebuilt or adapted for that hosting model.

**Exit condition:** a stable demo link, documented limitations, and no unapproved sensitive data exposed.

## Immediate next action

The app now supports a user-defined aggregate origin anchor: choose **Map point type → Origin area**, click an existing teal graph node, and give the origin a name in the sidebar. For each selected origin, configure its scenario evacuee amount and planned percentage to each receiving pin; set a total headcount cap at each receiving pin in **Explore details → Pin route**. Example: assign 80% of one origin to Pin 2 and 20% to Pin 3. The app allocates whole synthetic groups toward those shares subject to connectivity and entered caps. Custom origins are session-only, point-anchored scenario inputs; they are not polygons, official purok boundaries, population observations, or verified access points. To represent parts of an existing origin, users must enter the assumed subarea amounts themselves and avoid selecting overlapping parent and subarea origins together. No source population splitting or parent/subarea relationship is inferred. This completes the planned 90% implementation checkpoint; live map verification remains pending. Review at least two origins and two pins, the entered shares and capacities, whole-group rounding, unassigned reasons, and map-rendered paths in the running app. Then inspect closest disconnected-node pairs in QGIS as review leads only; never connect a gap without checking geometry, pedestrian access, crossings, barriers, and continuity. The picker selects existing graph nodes (zero snap offset); arbitrary off-road point snapping remains future work. Pins are scenario candidates, not official shelters or verified safe sites. Confirm CBMS definitions and usage permission before treating its 6,502 total as a local model input. The depth-class overlap is a static map comparison, not a time-progressing tsunami front or a safety finding. Use time-resolved hazard data if available, or label any approximate front as illustrative and separate from evacuation results.

## Progress estimate

The project is at a **90% implementation checkpoint; the live walkthrough is still pending**. The interactive geographic map, named Gubat origins, user-defined session-only aggregate origin anchors, per-origin scenario evacuee amounts, per-origin-to-pin percentage shares, per-pin headcount limits, whole-group allocation, and disconnected-road diagnostics are implemented in code. User-defined origins are representative graph-node points and their amounts/shares are assumptions; the app does not know official purok boundaries or automatically partition CBMS totals. Avoid selecting an overlapping parent origin and its manually defined subareas in the same run. Only the provisional Gubat aggregate is currently available as a population reference. Pin limits are not verified capacities, and pins are not designated shelters. Groups that cannot be assigned because of shares, network gaps, capacity, or whole-group rounding remain unassigned with a reason. Disconnected groups report graph-component information and closest separate graph-node pairs as GIS review leads; no artificial connector is created. OSM route geometry and candidate access remain unreviewed; map selection is restricted to existing graph nodes. Static inundation-depth classes are used only for geometric route overlap, not tsunami timing or safety. The separate R1–R12 schematic demo still drives its own route calculations. The client reports no definite official evacuation location. Time-stepped evacuation playback, a defensible tsunami inundation timeline, local field/access validation, approved broader-area population aggregates, and deployment are not complete. Next: walk through multi-origin/multi-pin behavior in the running app; inspect suggested gaps in QGIS without auto-connecting; obtain client/local approval for aggregate amounts, boundaries, receiving-area use and capacity; validate behavior, security and sharing configuration; then prepare a hosted link.
