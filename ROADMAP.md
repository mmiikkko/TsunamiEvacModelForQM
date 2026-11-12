# Project Roadmap

## Project objective

Build a research prototype that assesses evacuation routes and evacuation progress for residents starting in Barangay Gubat, with routes extending through southern Daet and potentially to confirmed destinations in Basud. The prototype should make its assumptions visible and distinguish validated local inputs from provisional scenarios.

The existing QGIS exposure map is a static view of Gubat. It is not a tsunami propagation model. A moving-wave feature is a separate scope decision and requires time-resolved hazard inputs or a separately validated physical model.

## Current baseline

- A QGIS layout and PDF show a static Gubat exposure map.
- The Streamlit app can preview the map image and download the PDF.
- The app's evacuation calculations still use a schematic 12-edge network and synthetic population, shelter, and road-capacity data. R1-R12 are sample edge IDs, not real road names.
- A Camarines Norte OpenStreetMap roads GeoPackage is available, but it has not been clipped, checked, or connected to the evacuation model.
- The current tsunami file contains static inundation-depth classes; it does not provide wave-arrival times or time slices.

## Roadmap

### 1. Lock the study scope and questions — in progress

- Keep the local exposure map centered on Gubat.
- Expand the evacuation-network extent along connected roads through southern Daet.
- Treat Basud as a possible receiving area only after candidate sites are identified and their access, safety, and usable capacities are confirmed.
- Decide whether the research evaluates evacuation progress against a static hazard scenario, or also includes a time-varying tsunami model. Do not promise an animation until its data and method are defined.
- Keep the distinction clear between tsunami inundation extent/depth, tsunami arrival time, and evacuation completion time.

**Exit condition:** agreed study area, questions, outputs, and explicit limits recorded in the paper and app.

### 2. Audit and prepare the geographic inputs — next

- Inspect the available road GeoPackage for Daet and the southbound corridor toward Basud. Clip a working copy to the agreed study extent while preserving the original source.
- Check road connectivity, directionality, pedestrian access, highway crossings, bridges, sidewalks/roadside walking space, and missing links. OSM attributes and geometry are starting evidence, not field verification.
- Confirm the tsunami layer's coverage, depth-class meanings, source, date, and permitted interpretation. Record that it is static unless time-resolved data are obtained.
- Identify candidate evacuation destinations with the client/local authorities. Record name/location, access, usable capacity, and source; do not invent Basud shelters.
- Obtain population inputs in aggregate form. Avoid storing household names or identifiable records in the shared repository or deployed app.
- Record each dataset's source, date, CRS, extent/resolution, license, confidence, and transformations in `data/data_sources.csv`.

**Exit condition:** documented, reviewable geographic inputs and a list of unresolved data gaps.

### 3. Refine the maps

- Keep the Gubat exposure map as the local hazard/exposure view, but make the map and legend agree: show the inundation depth classes with clearly distinguishable fills, and symbolize houses/buildings/population points separately.
- Improve title, typography, label placement, boundary contrast, margins, and legend wording; remove clipped or unexplained map elements.
- Create a separate regional evacuation-network map covering Gubat, southern Daet, and confirmed receiving sites. Show route context without suggesting every mapped road is a safe evacuation route.
- Attribute OSM and all other map sources correctly.

**Exit condition:** reviewed static maps that can be interpreted without confusing hazard classes, buildings, and routes.

### 4. Replace the schematic road graph

- Convert the checked road network into connected graph edges with stable IDs and human-readable road/segment descriptions.
- Represent permitted pedestrian directions, road/path type, lengths, and capacity assumptions. Distinguish the four-lane national highway from usable pedestrian space; do not assume all lanes or shoulders serve evacuees in the same way.
- Replace the R1-R12 closure control with meaningful segment labels and use it only for documented scenario closures.
- Add confirmed origin areas and destination sites in the expanded study area.

**Exit condition:** routes can be traced on the regional map, and edge attributes and limitations are reviewable.

### 5. Replace synthetic population and mobility assumptions

- Use aggregate household/population totals and spatial distributions supported by permitted data.
- Represent elderly residents, children, and PWDs with aggregate counts or explicit scenario shares and suitable assistance/speed assumptions; never infer individual needs from identifiable records.
- Treat one vehicle per household and local vehicle mix (including tricycles and motorcycles) as scenario assumptions until aggregate ownership, driver availability, passenger capacity, and boarding/pickup arrangements are confirmed.
- Model congestion and vehicle interactions only if data and project scope support them. Otherwise, state their limits and compare clearly labeled scenarios.

**Exit condition:** every population, mobility, and vehicle input has a source or is clearly marked as a provisional scenario.

### 6. Implement and explain the evacuation simulation

- Build on the discrete-event simulation approach for time-ordered departures, travel, queues/capacity constraints, and arrivals at destinations.
- Report evacuation progress over time, route assignments, bottlenecks, unserved people, and destination-capacity exceedance.
- Use sensitivity/scenario comparisons for departure delay, walking speed, group assistance, road capacity, closures, and any vehicle/tricycle assumptions.
- Keep evacuation completion time separate from tsunami arrival time. Without validated time-resolved hazard data, do not claim that the simulation predicts whether evacuees beat the wave.

**Exit condition:** results are reproducible from documented inputs and limitations are visible beside outputs.

### 7. Decide on optional tsunami animation

- First check whether the supplied agency data include time-stamped inundation extents/depths or validated arrival-time rasters.
- If not, decide whether to acquire a suitable validated model/data source or keep the tsunami layer static. A hypothetical animation may be used only as an explicitly illustrative scenario, not a local forecast.
- A physically meaningful wave animation is a separate hazard-modeling task requiring appropriate source, bathymetry/topography, boundary conditions, and validation.

**Exit condition:** either a sourced and validated time-dependent hazard feature, or an explicit decision to keep the hazard static for this project.

### 8. Align the paper with the implemented project

- Build the review of related literature from accessible, verifiable scholarly and official sources; replace inaccessible references and revise claims that depended on them.
- Update the introduction and methodology to match the expanded Gubat–southern Daet–potential Basud study area, actual data sources, DES design, population groups, mobility assumptions, and the static/time-dependent hazard decision.
- Keep unpublished instructor modules out of the reference list; retain relevant concepts only when supported by published sources.
- Follow the provided IEEE conference template. Add results and conclusions only after the model is implemented and reviewed.

**Exit condition:** the paper describes what the app actually does, cites accessible sources, and distinguishes verified data from assumptions.

### 9. Improve the app, validate, and share

- Redesign the Streamlit interface with clear sections for the exposure map, regional routes, scenario controls, results, sources, and limitations.
- Use clear names, accessible colors, and concise explanations. Make it visually distinct from a generic default dashboard without hiding assumptions.
- Review outputs with the client/adviser and compare them against known routes and feasible travel/capacity assumptions.
- Before deployment, commit and push the required app assets and code; check repository visibility and remove/private any household-identifying or sensitive location data.
- For the current Streamlit app, use Streamlit Community Cloud for the simplest GitHub-based shareable link. Consider Vercel only if the interface is rebuilt or adapted for that hosting model.

**Exit condition:** a stable demo link, documented limitations, and no unapproved sensitive data exposed.

## Immediate next action

Start with **Step 2**: inspect the available OSM roads for the Gubat–southern Daet–potential Basud corridor and determine what needs field/local verification. In parallel, fix the Gubat map's depth-class and point-symbol styling before presenting it as a final exposure map.

## Progress estimate

The overall project was previously estimated at roughly 40%. That is a rough planning estimate: the static map and a basic app prototype exist, while verified local network/population inputs, an integrated realistic evacuation simulation, validation, and deployment remain outstanding.
