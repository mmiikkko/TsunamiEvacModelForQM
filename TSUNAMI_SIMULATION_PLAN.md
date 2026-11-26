# Tsunami and evacuation simulation plan

## Goal

When the user has selected an area, scenario inputs, origins, receiving pins, capacity limits, and origin-to-pin shares, they can start a **coupled scenario replay**. A persistent simulation clock advances while the map displays time-dependent tsunami conditions and the modeled movement of aggregate evacuee groups. The user can pause, resume, seek, change playback speed, and restart.

The map remains a research/planning prototype. It must not present an unvalidated model as a warning, safe route, or real-time emergency tool.

## Current data gate

The project currently contains the static six-class tsunami inundation layer in `tsunamishp/tsunami.*` and the static Gubat clip in `data/gubat_tsunami_clip_fixed.gpkg`. The project inventory contains no tsunami arrival-time grid, time-stepped depth/current output, or propagation series. The shapefile's QGIS metadata (`tsunamishp/tsunami.qmd`) has no title, abstract, or dates recorded. Therefore, the existing layer can show mapped maximum inundation/depth classes, but it cannot determine when water reaches a road, origin, pin, or town location.

**Gate:** do not animate expanding water from the static polygons. Obtain and document a time-dependent tsunami model product or run produced/approved by an appropriate technical source. Numerical tsunami inundation products can provide arrival times and time series in addition to maximum inundation; these depend on model scenarios and suitable elevation/bathymetry data. See NOAA's [Tsunami Modeling and Research](https://nctr.pmel.noaa.gov/model.html), [ComMIT model background](https://nctr.pmel.noaa.gov/ComMIT/background.html), and UNESCO-IOC's [inundation modeling example](https://tsunami.ioc.unesco.org/sites/default/files/medias/fichiers/2025/01/MH_MAJ_hazard_map_1.pdf). PHIVOLCS provides official tsunami hazard maps and notes that availability varies by location; see [PHIVOLCS Tsunami Hazard Maps](https://www.phivolcs.dost.gov.ph/tsunami-hazard-maps-3/).

## Increments and completion gates

### Increment 1 — Confirm data and scenario contract

**Status: local project inventory complete; authoritative time-dependent input still needed.**

- Ask the client/local DRRMO and relevant technical source which tsunami scenario(s) should be represented and what “intensity” means for this project.
- Prefer a selector for named, sourced scenarios (with source/event/scenario ID and parameters) over an ungrounded free-form intensity slider.
- Obtain data and metadata: time-indexed inundation depth (or a validated arrival-time plus suitable depth progression), units, simulation start reference, timestep, CRS/vertical datum, spatial resolution, coverage, model/source/version, scenario parameters, uncertainty, validation basis, and reuse terms.
- Confirm whether the product represents first arrival, later waves, maximum depth, current speed, or all of these. Do not treat a maximum-depth layer as a time sequence.

The public PHIVOLCS Daet listing exposes a tsunami JPG and KMZ; the Camarines Norte provincial listing exposes dated KMZ/PNG map products. These listings do not identify time-stepped inundation outputs. See the [data intake contract](data/tsunami_time_series_data_contract.md) and the unsent [request draft](data/tsunami_time_series_request_template.md).

**Done when:** each selectable scenario maps to documented time-dependent hazard data with a clear clock origin and units, or the team explicitly chooses a clearly labeled illustrative-only replay that does not claim physical tsunami propagation.

### Increment 2 — Specify the simulation clock and states

**Status: first UI shell added; playback/state transitions are not implemented yet.** The sourced-scenario selector, Start/Pause/Restart controls, inactive clock/timeline, and setup checklist sit below the map so they do not cover its default view. They remain disabled until both reviewed time-dependent data and a playback engine are available. `data/tsunami_time_series_data_contract.md` defines the intake format and validation gate; `data/tsunami_scenario_manifest_template.csv` is ready for source metadata.

**Illustrative preview added:** the six classes in `data/gubat_tsunami_clip_fixed.gpkg` can optionally be revealed cumulatively in a Plotly map preview, with Play/Pause/Restart and a 0–6 illustrative-step scrubber below the map viewport. The preview explicitly states that class order and playback speed are visual assumptions; it does not provide arrival times, animate a modeled wave, or drive evacuation movement. The default remains the static map. This preview does not satisfy the time-dependent data gate and does not unlock **Start simulation**.

**Separate evacuation movement preview added:** when groups have been assigned to connected candidate receiving pins, the map can animate anonymous synthetic groups along their assigned shortest free-flow graph paths. Group departure draws, the delay setting, and the uniform walking-speed assumption determine the displayed evacuation minutes. Play/Pause/Restart and a scrubber are independent of tsunami playback; mapped depth classes stay static during this view. This is not individual-based movement, a crowd model, a safe-route check, or a claim that evacuees beat tsunami arrival. It does not unlock **Start simulation**.

- Define states: `Ready`, `Running`, `Paused`, `Completed`, and `Invalid setup`.
- Show elapsed simulated time (for example, `00:12:30`) and, where available, the model's event-relative timestamp.
- Define play/pause, resume, step, seek/scrub, playback speed, and restart behavior.
- Validate setup before enabling **Start simulation**: a selected area/scenario, at least one included origin with a nonzero scenario population, at least one receiving pin, usable entered capacities, and valid planned shares. Explain any unmet requirement beside the button.
- Keep simulation time separate from real wall-clock time; starting or replaying a scenario must not imply a live warning.

**Done when:** clock controls are deterministic, replayable, and reset all hazard and evacuation state consistently.

### Increment 3 — Replay the sourced tsunami hazard

**Status: manifest/frame structural validator implemented in `tsunami_scenarios.py`; no time-series dataset is present, and the playback renderer is not implemented.** The app will list only scenarios that pass the manifest, GeoPackage, time, units, CRS, and prototype-review-status checks. Structural checks do not validate the physical tsunami model or safety.

- At time `t`, draw the hazard state from the selected scenario's time-indexed model output.
- Update depth/arrival legend with units and a visible scenario/source label.
- Keep the static maximum-inundation layer available as a reference outline, visually distinct from the current-time water state.
- If data has gaps or a coarser timestep than the display rate, show/interpolate only what the source supports and disclose it; do not invent wave fronts between observations/model steps.

**Done when:** pausing/stepping/seeking shows the corresponding sourced hazard state, including before arrival and after the modeled run ends.

### Increment 4 — Animate aggregate evacuation movement on the same clock

- Represent only aggregate groups, not household/person locations.
- Use the selected origin-to-pin allocations and the road graph for scenario movement, with route time assumptions visible.
- Advance groups according to departure time and modeled travel time while the same simulation clock advances the hazard.
- Display clear aggregate states such as waiting, en route, arrived at candidate pin, and not assigned; do not label a candidate pin as safe or officially available without evidence.
- Report route/hazard overlap only when the hazard data and route geometry support a time-specific comparison. Avoid casualty or survival claims without a validated impact model.

**Done when:** changing an origin, share, pin capacity, walking assumption, or scenario changes the replay in a traceable way and pausing freezes both people and hazard.

### Increment 5 — User interface and accessibility

- Put **Start simulation** with the scenario controls where it remains visible beside the anchored map.
- Add a persistent timeline bar with elapsed time, play/pause, step, scrubber, playback speed, and restart.
- Keep scenario selection/intensity meaning explicit; show the scenario name and data source during playback.
- Use distinct hazard and group symbology, color-safe visual distinctions, text equivalents, and readable map legends below the map.
- Show a concise model/data limitations panel throughout playback.

**Done when:** a first-time user can configure, start, pause, inspect, and restart a scenario without scrolling away from the map or mistaking the replay for a live forecast.

### Increment 6 — Validation and release review

- Check selected timestamps against the source model's maps or time series.
- Have the client/technical adviser review scenario definitions, hazard interpretation, road assumptions, and candidate receiving sites.
- Exercise setup errors, multiple origins/pins, capacity/share limits, disconnected graph cases, pause/seek/restart, and different supported data resolutions.
- Record known uncertainties and test with the intended group before any public deployment.

**Done when:** outputs are reproducible, limitations are visible, the technical reviewer accepts the interpretation, and the team agrees on a research-prototype label and sharing plan.

## Proposed control behavior

1. User selects extent and a sourced tsunami scenario, configures origins, receiving pins, capacities, shares, and evacuation assumptions.
2. The app checks the setup and previews the selected scenario/source and modeled population.
3. User presses **Start simulation**; the simulation clock starts at the model's defined zero/event reference.
4. Hazard state and aggregate movement advance together.
5. User can pause, resume, seek within the model output, change playback speed, or restart without losing the configured scenario.

“Intensity” should be attached to a documented scenario parameter or named official/model scenario. A generic severity slider should not alter the water animation unless its values are backed by corresponding time-dependent model runs.

## Current next action

Obtain time-dependent tsunami scenario outputs and metadata from the client/local DRRMO or an appropriate technical source, using the data contract, manifest, and unsent request draft. The app currently has a locked control shell and structural intake validator, but no playback engine. Once a real dataset is received and passes intake validation, implement the clock/state transitions and time-frame rendering against that data. Keep tsunami-water animation disabled until sourced data is loaded; do not animate the static maximum extent.
