# Project Roadmap

## Project objective

Build an interactive geographic scenario application for Barangay Gubat and the evacuation network across Daet, with routes extending south and potentially to confirmed destinations in Basud. The map is the main interface: users should be able to zoom and pan, inspect hazard and road layers, change scenario settings, and see geographic route assignments and time-based results on the map.

The intended time view must keep two processes distinct: evacuation progress from the discrete-event model, and tsunami inundation over time. The supplied tsunami layer contains static maximum inundation-depth classes, not a time series. A true moving inundation view requires time-dependent hazard data or a separate defensible physical model. A simplified illustrative front is possible only if it is prominently labeled as an assumption and never presented as a local forecast.

## Current baseline

- A QGIS layout and PDF show a static Gubat exposure map; they are useful references but are not the target interactive scenario map.
- The Streamlit app has an interactive GIS map using the Gubat hazard/boundary GeoPackages and the Daet–Basud candidate road graph, with extent and layer controls. The user confirmed the three extents, zoom/pan, and layer toggles work. Map-linked scenario outputs and time playback are not implemented.
- Named-area synthetic groups are now assigned to the QGIS-reviewed candidate OSM graph node for their area; the interactive map displays these node markers with scenario totals and reports raw graph-component relationships. This is a geographic origin-to-network attachment only.
- The route calculations still use a schematic 12-edge network and synthetic receiving-area/road-capacity data. R1-R12 are sample edge IDs, not real road names. The client reports there is no definite official evacuation location; potential receiving areas (for example, schools or SM) may be considered, but their use, access, and capacity are unverified. No evacuation paths are presented as real routes.
- The geographic map now has a first-pass candidate-route interaction: users can enable a road-node picker, click a mapped graph node, choose a named Gubat origin, and view a shortest estimated free-flow path if the graph connects them. It is a screening preview on unreviewed OSM geometry and does not account for moving tsunami water, capacity queues, or verified pedestrian access.
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
- A separate synthetic group generator now partitions the provisional 6,502-person Gubat total into anonymous 5–10 person parties and configurable 2–3 person small-party draws, assigns reproducible randomized departure times, and allocates groups among named candidate residential-area anchors (Roseville Subdivision, Cleofe Ecology Village, and Mandulongan/Purok Tsiko). The map shows the named-place anchors and simulated zone totals. Population shares are randomized, not measured. The coordinates are candidate place anchors, not household points, official zone polygons, or validated access points; the generated groups do not drive route outputs yet. Del Rosario is a separate barangay in Mercedes and is excluded from Gubat's population allocation unless a distinct approved total is added for a broader model.

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

Continue **Step 4**: live-review the new map-node picker and shortest-time route preview, then use `data/origin_access_review.csv` to inspect the Roseville 163 m gap and the two closer candidate accesses in QGIS. The first implementation selects an existing graph node (so its snap offset is zero); arbitrary off-road point snapping remains future work. Record what the map supports and what needs local confirmation. Do not connect the Roseville component based on distance alone. Keep user-selected pins labeled as scenario candidates, not official shelters or verified safe sites. Review network connectivity and pedestrian access before using the candidate path as a route. Confirm CBMS definitions and usage permission before treating its 6,502 total as a local model input. The static depth polygons can be shown as hazard classes but cannot provide a real time-progressing tsunami front. Use time-resolved hazard data if available, or label any approximate front as illustrative and separate from evacuation results.

## Progress estimate

The expanded target remains **80%** until the map interaction is confirmed in a live app session. The interactive geographic map, extent/layer controls, named Gubat scenario origins, reproducible synthetic group generation, and randomized area allocation are in place. Each included origin’s scenario groups now appear at its candidate OSM graph node. A reproducible origin-access screen distinguishes anchor-to-road-line proximity from anchor-to-node distance and reports component IDs: Roseville is 163 m from its nearest mapped road geometry and sits in a separate 21-vertex component; Cleofe Ecology Village and Mandulongan are in a 622-vertex component, with nearest-road distances of 13 m and 25 m. A first-pass map-node picker and shortest estimated free-flow route preview have been added, but remain unverified in the running app. These improve reviewability; they do **not** complete real evacuation routing: all origin accesses and the 136-component regional graph remain unreviewed. The client reports there is no definite official evacuation location; user-selected map points and possible places such as schools or SM are scenario candidates, while permission/use, access, and capacity are not established. R1–R12 still drive separate route calculations. Population totals and area shares remain provisional; Del Rosario is excluded from the Gubat total. Time-stepped evacuation playback on reviewed real routes and a defensible tsunami inundation timeline are not implemented. Next, verify map-node selection and path rendering in the live app, review origin access in QGIS, and review candidate paths on an appropriately checked pedestrian graph. Confirm aggregate definitions and permitted use before relying on the 6,502 total; then scope time-dependent hazard evidence, validate, and deploy.
