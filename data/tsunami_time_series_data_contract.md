# Tsunami time-series data intake contract

This defines the data we need before the app can display a tsunami changing over simulation time. The project contains a static maximum-inundation layer for Gubat and the broader original client layer used in the Daet extent; neither contains time steps or shoreline arrival times, so neither satisfies this contract.

Public PHIVOLCS listings include a Daet tsunami JPG and KMZ map, and Camarines Norte-wide 2007/2021 KMZ/PNG maps; those listings establish that map products exist, but do not establish that time-stepped depth/arrival outputs are publicly available. See the [Daet municipal listing](https://gisweb.phivolcs.dost.gov.ph/gisweb/storage/hazard-maps/region-v-%28bicol-region%29/camarines-norte/daet-%28capital%29/earthquake/tsunami/) and the [Camarines Norte provincial listing](https://gisweb.phivolcs.dost.gov.ph/gisweb/storage/hazard-maps/region-v-%28bicol-region%29/camarines-norte/provincial/earthquake/tsunami/). A map file alone should not be assumed to contain animation frames.

## Scenario manifest

Start from `data/tsunami_scenario_manifest_template.csv`. Create one row for each sourced scenario. The manifest must identify:

- a stable scenario ID and user-facing scenario name;
- source organization, source title/reference or URL, version/date, and scenario parameters;
- what simulation time zero means and the run's start/end and timestep in seconds;
- horizontal CRS, vertical datum, depth units, and spatial resolution;
- the time-frame GeoPackage path and layer name;
- the time, depth, and optional depth-class field names;
- validation reference, known uncertainty/limitations, and reuse terms.
- technical reviewer role, review date, and `technical_review_status=REVIEWED_FOR_PROTOTYPE` after an appropriate reviewer approves the interpretation for this prototype.

Do not use a generic “low/medium/high” intensity label unless the source defines which modeled scenario and parameters each choice represents.

## Time-frame GeoPackage

The normalized input is a GeoPackage vector layer containing the water-covered polygons for each model timestep. Every feature must have:

| Field | Meaning |
|---|---|
| `scenario_id` | Must match the manifest row. |
| `time_seconds` | Elapsed model seconds from the manifest's time-zero reference. |
| `depth_m` | Water depth at that frame, in meters. |
| `depth_class` | Optional source class; do not substitute for numeric depth if depth is available. |
| geometry | Polygon or multipolygon in the CRS recorded in the manifest, representing the source model's inundated area at that time. |

Create frame polygons from the actual time-specific model output. Do not create them by growing the static maximum-inundation polygon, linearly interpolating between arbitrary outlines, or inventing arrival times. Preserve the source timestep; if frames are discrete, the UI should identify the displayed model frame and avoid implying finer temporal precision.

If the technical source provides a raster, NetCDF, or another format, preserve that original untouched and prepare a documented conversion into this normalized layer. Record conversion software/version, thresholds, nodata handling, and any loss of resolution. Do not discard the original model output.

## Intake checks before enabling the Start button

1. Manifest fields are complete and source/reuse terms are recorded; technical review status is explicitly approved for prototype use.
2. Frame file and layer exist and contain the declared fields.
3. All frames match the scenario ID, have valid nonnegative time values and depths, and use one consistent CRS/vertical datum.
4. Frame times are ordered and unique; timestep and run duration agree with the frame values.
5. Geometry extent covers the selected study area and plausible offshore approach; nodata is not mistaken for dry land.
6. The source/technical reviewer confirms what the time series represents (arrival, depth, later waves, currents) and its limitations.

Only scenarios passing these checks should appear as playable options. If no valid scenario is available, keep tsunami playback disabled and show the reason.
