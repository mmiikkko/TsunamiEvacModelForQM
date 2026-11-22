# Tsunami evacuation planning prototype

An early, local web prototype for comparing evacuation scenarios. It is designed so the model and interface can be started with synthetic example data, then updated as verified Barangay Gubat data becomes available.

See [ROADMAP.md](ROADMAP.md) for the agreed study extent, pending data decisions, implementation stages, and next actions.

## Current geographic-data milestone

The project includes a preliminary Daet boundary and OSM road/path clip: `data/daet_barangays.gpkg` (25 barangays), `data/daet_boundary.gpkg` (one dissolved outline), and `data/daet_roads.gpkg` (1,102 features). A broader screening extent is also available in `data/daet_basud_barangays.gpkg` (25 Daet + 29 Basud barangays), `data/daet_basud_boundary.gpkg` (one dissolved outline), and `data/daet_basud_roads.gpkg` (1,551 features). The broader clip includes every mapped road/path within those municipal boundaries; it is not a selected or validated evacuation corridor and does not imply that a Basud shelter has been confirmed. Attribute coverage and source limitations are documented in [`data/daet_roads_audit.md`](data/daet_roads_audit.md); a preliminary vertex connectivity screen is in [`data/daet_basud_connectivity_audit.md`](data/daet_basud_connectivity_audit.md). Its 136 preliminary components have a QGIS navigation index at `data/daet_basud_component_review.csv`; its review fields remain unfilled. The overview map is `output/daet_basud_road_review.png` and [QGIS review steps](data/daet_basud_review_instructions.md) explain how to inspect it without treating the components as approved routes.

These GeoPackages are not yet connected to the app's evacuation calculations. The app continues to use its schematic R1-R12 network and synthetic scenario inputs until routing, population, destination, and local validation work is completed.

The app also displays `gubat_tsunami_exposure_map_preview.png` and offers `gubat_tsunami_exposure_map.pdf` for download. These are static exports from the QGIS layout, for visual reference only; they are not an animated tsunami model and are not connected to the synthetic evacuation calculations.

## Important scope note

The included network and population are **synthetic demonstration data**, not measurements or official recommendations for Barangay Gubat. The prototype models movement over a road graph; it does not simulate tsunami generation, wave propagation, inundation, warning issuance, or real-time navigation. Do not use its sample outputs for emergency decisions. Replace the example data and review assumptions with the Barangay and Daet MDRRMO before interpreting results.

## Client-provided GIS and planning inputs

- `tsunamishp/tsunami.*` is a polygon shapefile bundle with six inundation-depth classes and a WGS 84 / EPSG:4326 coordinate reference system. The client defines inundation depth as the vertical distance from ground surface to the top of accumulated water. Treat this as a static hazard extent/depth layer, not a time series or wave-motion simulation. Overlay it with verified roads, house points, and candidate destinations; exclude mapped inundated segments/sites only according to the scenario and an authorized hazard interpretation.
- The client clarified that “length of the tsunami” means its **inundation distance/extent**. That layer supports hazard-zone and route screening. It does not provide wave-arrival time or hazard duration; do not use it to claim a timed “beat the wave” result.
- Request from the MPDO: geotagged house/building points and the total population of Barangay Gubat. If permitted, also request aggregated occupants by purok or building to distribute population across the points. A barangay total alone cannot determine how many people begin at each house. Do not include names or household-identifying attributes in the model dataset.
- OpenStreetMap can provide a starting pedestrian and road network. Verify connectivity, pedestrian access, road width, sidewalks, gates, and closures with field observation and local officials; OSM coverage is community mapped and should not be presented as exact without validation. Attribute “© OpenStreetMap contributors” and follow the ODbL terms when using its data.

## Evacuation-network study extent

The client recommends evaluating evacuation movement beyond Barangay Gubat, toward southern Daet and potentially Basud. The exposure map may remain focused on Gubat, while the evacuation-network analysis should cover the connected road corridors and any confirmed receiving areas. A Camarines Norte OpenStreetMap roads GeoPackage is available at `data/raw/osm_camarines_norte_roads.gpkg` (5,276 line features, EPSG:4326; dataset metadata timestamp 2026-10-16). It is a preliminary network source, not an authoritative or field-verified route inventory. Basud locations must remain candidate destinations until the client or responsible local authorities identify appropriate sites and confirm access, safety, and usable capacity.

## Provisional client assumptions to review

These are scenario inputs pending confirmation, not validated local measurements:

- Household size: test a 5-10 person range using MPDO/PSA aggregate distributions when available. Do not infer exact household sizes from the barangay total.
- Vehicle access: the one-vehicle-per-family statement is an assumption to check. Ask for aggregate vehicle ownership/availability, driver availability, vehicle seats, and pickup/boarding arrangements before modeling vehicle evacuation.
- Shelter space: the Sphere Handbook 2018 shelter guidance states a minimum 3.5 m² living space per person in the relevant warm-climate guidance, excluding cooking, bathing, and sanitation areas. The client's 2.5 m²/person assumption is different and must not be labelled the Sphere minimum. Keep both as clearly named scenarios only if advisers and responsible local authorities approve the comparison. At 3.5 m²/person, 50 people require 175 m² of usable covered living area; at 2.5 m²/person, 50 require 125 m². Actual safe capacity must also account for usable area, facility condition, access/egress, and applicable local requirements. A blanket “50 people per room” assumption needs room-by-room confirmation.

The model currently does not integrate the supplied hazard polygons, the local OpenStreetMap road GeoPackage, household points, household sizes, vehicles, or room-level shelter capacity. Integrate and validate these inputs before interpreting route or capacity outputs for Gubat, southern Daet, or Basud.

## Start locally

Requires Python 3.10 or newer.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run app.py
```

The app opens in a browser on the same computer. The sample scenario is ready to explore. You can edit the CSV files in `data/` and reload the page.

## Data files

Two large GIS inputs are intentionally kept outside version control to stay within GitHub's per-file size limit: `Geottaged Population of Gubat_modified.tif` in the project root and the `data/raw/elum2025_cmn_r05.*` shapefile bundle. They remain on the original workstation but must be obtained separately and placed at those paths when setting up a fresh clone. The rest of the project files do not include those datasets.

- `data/nodes.csv`: graph nodes with a stable `node_id`, display name, and local `x`,`y` coordinates. Coordinates are schematic in the sample. For real GIS data use longitude/latitude and choose one consistent coordinate reference system; the present graph display only uses relative positions.
- `data/roads.csv`: directed road/path segments (`from_node`, `to_node`) with length in meters, width in meters, and pedestrian capacity in people per minute. Add a reverse row if movement is allowed both ways.
- `data/origins.csv`: origin node, estimated population, group label, and free-flow walking speed in meters per second. Group totals should be aggregate estimates, not identifiable resident records.
- `data/shelters.csv`: destination node and estimated capacity in people.
- `data/scenario.csv`: scenario label and departure delay in minutes. Additional scenario controls are available in the app.

Every ID in roads, origins, and shelters must match an ID in `nodes.csv`. Values must be nonnegative; road length, width, capacity, speed, and shelter capacity must be positive. Keep a record of each data source, geographic coverage, resolution, confidence, license, and usage restrictions in `data/data_sources.csv`.

## Current model behavior

The prototype routes each origin group to its nearest reachable shelter by free-flow walking time, then estimates link queues using a simplified capacity model. It reports estimated completion time, arrival counts, unserved people, shelter overflow, and heavily loaded links. It does not represent individual people, children accompanying adults, road-crossing conflicts, vehicle boarding, panic, water depth, or route closures caused by inundation. These can be added only when data and scope justify them.

## Suggested next improvements

1. Clip and inspect the available road network for the Gubat–southern Daet–potential Basud corridor; verify pedestrian access, connectivity, bridges, sidewalks, closures, and candidate receiving sites with the client and local authorities.
2. Confirm shelter locations and capacities, local evacuation plans, and official hazard interpretations with the Barangay, Daet MDRRMO, Basud representatives as relevant, and PHIVOLCS.
3. Replace the schematic network and synthetic populations, keeping an untouched copy of every source dataset.
4. Add validated assumptions and uncertainty ranges for walking speeds, departure delay, assistance, road capacity, and warning time.
5. Compare baseline routes and carefully defined alternatives; ask local officials to review the assumptions and outputs.
6. If traffic interactions become essential, evaluate adding SUMO. Display supplied inundation polygons as a separate sourced hazard layer rather than implying this evacuation model generated them.

## Project layout

- `app.py`: Streamlit interface and interactive scenario controls
- `simulation.py`: routing and simplified evacuation calculations
- `data/`: replaceable CSV inputs; sample values are synthetic
- `requirements.txt`: Python dependencies
