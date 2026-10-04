# Tsunami evacuation planning prototype

An early, local web prototype for comparing evacuation scenarios. It is designed so the model and interface can be started with synthetic example data, then updated as verified Barangay Gubat data becomes available.

## Important scope note

The included network and population are **synthetic demonstration data**, not measurements or official recommendations for Barangay Gubat. The prototype models movement over a road graph; it does not simulate tsunami generation, wave propagation, inundation, warning issuance, or real-time navigation. Do not use its sample outputs for emergency decisions. Replace the example data and review assumptions with the Barangay and Daet MDRRMO before interpreting results.

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

- `data/nodes.csv`: graph nodes with a stable `node_id`, display name, and local `x`,`y` coordinates. Coordinates are schematic in the sample. For real GIS data use longitude/latitude and choose one consistent coordinate reference system; the present graph display only uses relative positions.
- `data/roads.csv`: directed road/path segments (`from_node`, `to_node`) with length in meters, width in meters, and pedestrian capacity in people per minute. Add a reverse row if movement is allowed both ways.
- `data/origins.csv`: origin node, estimated population, group label, and free-flow walking speed in meters per second. Group totals should be aggregate estimates, not identifiable resident records.
- `data/shelters.csv`: destination node and estimated capacity in people.
- `data/scenario.csv`: scenario label and departure delay in minutes. Additional scenario controls are available in the app.

Every ID in roads, origins, and shelters must match an ID in `nodes.csv`. Values must be nonnegative; road length, width, capacity, speed, and shelter capacity must be positive. Keep a record of each data source, date, resolution, and confidence in `data/data_sources.csv`.

## Current model behavior

The prototype routes each origin group to its nearest reachable shelter by free-flow walking time, then estimates link queues using a simplified capacity model. It reports estimated completion time, arrival counts, unserved people, shelter overflow, and heavily loaded links. It does not represent individual people, children accompanying adults, road-crossing conflicts, vehicle boarding, panic, water depth, or route closures caused by inundation. These can be added only when data and scope justify them.

## Suggested next improvements

1. Confirm the local evacuation plan, actual road/path network, shelter locations/capacities, and official hazard information with the Barangay, Daet MDRRMO, and PHIVOLCS.
2. Replace the schematic network and synthetic populations, keeping an untouched copy of every source dataset.
3. Add validated assumptions and uncertainty ranges for walking speeds, departure delay, assistance, road capacity, and warning time.
4. Compare baseline routes and carefully defined alternatives; ask local officials to review the assumptions and outputs.
5. If traffic interactions become essential, evaluate adding SUMO. If authoritative inundation surfaces become available, display them as a separate sourced layer rather than implying this evacuation model generated them.

## Project layout

- `app.py`: Streamlit interface and interactive scenario controls
- `simulation.py`: routing and simplified evacuation calculations
- `data/`: replaceable CSV inputs; sample values are synthetic
- `requirements.txt`: Python dependencies
