from pathlib import Path
import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import networkx as nx
import streamlit as st

from gis_layers import read_gpkg_features
import scenario_generation
from simulation import load_inputs, node_coordinate_lookup, run_simulation
from tsunami_scenarios import load_valid_tsunami_scenarios, scenario_input_revision


st.set_page_config(page_title="Evacuation Scenario Explorer", page_icon="🌊", layout="wide")
st.markdown(
    """<style>
    [data-testid="stAppViewBlockContainer"] {
        height: calc(100vh - 4rem); max-height: calc(100vh - 4rem);
        overflow: hidden; padding-top: .25rem; padding-bottom: .5rem;
    }
    section[data-testid="stMain"] { height: calc(100vh - 1rem); overflow: hidden; }
    div[data-testid="stHorizontalBlock"] { align-items: flex-start; }
    .st-key-map_stage {
        position: sticky; top: 0; z-index: 20; align-self: flex-start;
        height: calc(100vh - 6rem) !important; max-height: calc(100vh - 6rem);
        overflow-y: auto; background: var(--background-color); padding: .2rem .4rem .4rem;
    }
    .st-key-details_panel {
        height: calc(100vh - 7rem) !important; max-height: calc(100vh - 7rem);
        overflow-y: auto; padding: .15rem .4rem .5rem; background: var(--background-color);
    }
    .st-key-details_panel [data-testid="stTabs"] [role="tablist"] {
        background: #fff; padding: .35rem 0;
        display: grid; grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: .2rem .35rem; border-bottom: 1px solid rgba(100,116,139,.25);
    }
    .st-key-details_panel [data-testid="stTabs"] button[role="tab"] {
        width: 100%; min-height: 2.2rem; padding: .35rem .45rem; font-size: .84rem;
        white-space: normal; line-height: 1.15; justify-content: flex-start;
    }
    .map-legend { display:flex; flex-wrap:wrap; gap:.35rem .75rem; padding:.5rem .25rem; font-size:.78rem; line-height:1.3; }
    .map-legend-item { display:inline-flex; align-items:center; gap:.35rem; white-space:nowrap; }
    .map-legend-swatch { width:1rem; height:.65rem; display:inline-block; border:1px solid rgba(15,23,42,.25); border-radius:2px; }
    .map-legend-line { width:1rem; height:0; display:inline-block; border-top:2px solid; }
    .map-legend-dot { width:.65rem; height:.65rem; display:inline-block; border-radius:50%; }
    .st-key-map_stage [data-testid="stVerticalBlock"] { gap: .45rem !important; }
    .st-key-expand_explore_details button {
        min-height: 3rem; padding: .45rem .6rem; white-space: nowrap;
    }
    [data-testid="stSidebar"] > div:first-child { max-height: 100vh; overflow-y: auto; }
    @media (max-width: 1050px) {
        section[data-testid="stMain"] { height: auto; overflow: visible; }
        [data-testid="stAppViewBlockContainer"] { height: auto; max-height: none; overflow: visible; }
        .st-key-map_stage, .st-key-details_panel { position: static; height: auto; max-height: none; overflow: visible; }
    }
    </style>""",
    unsafe_allow_html=True,
)

map_pdf_path = Path(__file__).parent / "gubat_tsunami_exposure_map.pdf"
map_preview_path = Path(__file__).parent / "gubat_tsunami_exposure_map_preview.png"
project_dir = Path(__file__).parent

road_review_png = Path(__file__).parent / "output" / "daet_basud_road_review.png"
road_review_pdf = Path(__file__).parent / "output" / "daet_basud_road_review.pdf"
origin_access_review_csv = Path(__file__).parent / "data" / "origin_access_review.csv"
component_gap_review_csv = Path(__file__).parent / "data" / "daet_basud_component_gap_review.csv"
component_gap_review_geojson = Path(__file__).parent / "data" / "daet_basud_component_gap_review.geojson"

@st.cache_data(show_spinner=False)
def cached_tsunami_scenario_validation(base_dir: str, revision: tuple):
    return load_valid_tsunami_scenarios(base_dir)


tsunami_scenarios, tsunami_scenario_issues = cached_tsunami_scenario_validation(
    str(project_dir), scenario_input_revision(project_dir)
)
tsunami_time_series_available = bool(tsunami_scenarios)
# Scenario loading and playback are separate increments. The clock/renderer
# will be enabled only after the frame loader and timeline engine exist.
tsunami_playback_engine_available = False

try:
    inputs = load_inputs(str(Path(__file__).parent / "data"))
    origin_zones = pd.read_csv(Path(__file__).parent / "data" / "origin_zones.csv")
    gubat_zone = origin_zones.loc[origin_zones["zone_id"].astype(str) == "GUBAT"].iloc[0]
    gubat_population_total = int(gubat_zone["population_total"])
    origin_candidates = pd.read_csv(Path(__file__).parent / "data" / "origin_zone_candidates.csv")
    include_candidate = origin_candidates["include_in_gubat_origins"].astype(str).str.lower().isin({"true", "1", "yes"})
    origin_candidates = origin_candidates.loc[include_candidate].copy()
except Exception as exc:
    st.error(f"Could not load the project data: {exc}")
    st.stop()

with st.sidebar:
    st.header("Scenario settings")
    population_scale = st.slider("Population multiplier", 0.5, 2.0, 1.0, 0.1)
    speed_scale = st.slider(
        "Walking speed multiplier", 0.5, 1.5, 1.0, 0.05,
        help="Scales modeled walking time from a uniform baseline of 1.15 m/s. It does not change the selected route because every included road link uses the same speed.",
    )
    st.caption(
        f"Modeled walk speed: {1.15 * speed_scale:.2f} m/s on every included link. "
        "No congestion, slope, crossing delay, mobility differences, or time-varying tsunami conditions are modeled."
    )
    capacity_scale = st.slider("Path capacity multiplier", 0.5, 1.5, 1.0, 0.05)
    departure_delay = st.slider("Departure delay (minutes)", 0, 15, 0)
    planning_window = st.slider(
        "Arrival checkpoint (minutes)", 5, 60, 20,
        help="Shows how many assigned synthetic groups are estimated to reach candidate pins by this minute. It is not a tsunami arrival time or warning window.",
    )
    edge_ids = inputs["roads"]["edge_id"].astype(str).tolist()
    closed_edges = set(st.multiselect("Close sample path segments (demo network)", edge_ids))
    st.caption("Adjust these values only as scenario assumptions. Replace them with evidence when available.")
    st.divider()
    st.subheader("Synthetic group scenario")
    custom_origins = list(st.session_state.get("scenario_custom_origins", []))
    pending_origin_node_id = st.session_state.get("pending_origin_node_id")
    roadside_origin_exists = any(
        str(item["zone_name"]).strip().casefold() == "roadside residents"
        for item in custom_origins
    ) or origin_candidates["zone_name"].astype(str).str.strip().str.casefold().eq("roadside residents").any()
    if pending_origin_node_id:
        st.info(f"Selected candidate origin road node: {pending_origin_node_id}")
    with st.expander("Add a named origin area", expanded=bool(pending_origin_node_id)):
        st.caption("Choose a representative road node on the map first. This creates an aggregate scenario origin, not a household point or a mapped neighborhood boundary.")
        if custom_origins:
            st.caption("User-created origin labels and road-node anchors last for this app session; add them again after a server restart.")
        if not roadside_origin_exists:
            st.caption("For Roadside residents, first choose **Map point type → Origin area**, enable **Pick a road point**, and click the teal road node nearest the cluster you want to represent.")
            if st.button(
                "Add Roadside residents at selected node",
                key="add_roadside_residents_origin",
                disabled=not pending_origin_node_id,
                help="First set Map point type to Origin area and select a teal road node where this aggregate should be represented.",
            ) and pending_origin_node_id:
                origin_id = "MAP_ROADSIDE_RESIDENTS"
                used_ids = {str(item["zone_id"]) for item in custom_origins}
                suffix = 2
                while origin_id in used_ids or origin_id in set(origin_candidates["zone_id"].astype(str)):
                    origin_id = f"MAP_ROADSIDE_RESIDENTS_{suffix}"
                    suffix += 1
                custom_origins.append({
                    "zone_id": origin_id,
                    "zone_name": "Roadside residents",
                    "map_label": "Roadside residents",
                    "road_node_id": str(pending_origin_node_id),
                })
                st.session_state["scenario_custom_origins"] = custom_origins
                st.session_state["selected_origin_ids_widget"] = [
                    *st.session_state.get("selected_origin_ids_widget", origin_candidates["zone_id"].astype(str).tolist()),
                    origin_id,
                ]
                st.session_state.pop("pending_origin_node_id", None)
                st.rerun()
        else:
            st.caption("Roadside residents has already been added for this app session.")
        custom_origin_name = st.text_input("Origin area name", key="custom_origin_name_input", placeholder="e.g., Borabod north-side homes")
        can_add_origin = bool(pending_origin_node_id and custom_origin_name.strip())
        if st.button("Add this origin area", key="add_custom_origin", disabled=not can_add_origin):
            base = "".join(character if character.isalnum() else "_" for character in custom_origin_name.strip().upper()).strip("_")
            origin_id = f"MAP_{base or 'ORIGIN'}"
            used_ids = {str(item["zone_id"]) for item in custom_origins}
            suffix = 2
            while origin_id in used_ids or origin_id in set(origin_candidates["zone_id"].astype(str)):
                origin_id = f"MAP_{base or 'ORIGIN'}_{suffix}"
                suffix += 1
            custom_origins.append({"zone_id": origin_id, "zone_name": custom_origin_name.strip(), "map_label": custom_origin_name.strip(), "road_node_id": str(pending_origin_node_id)})
            st.session_state["scenario_custom_origins"] = custom_origins
            st.session_state["selected_origin_ids_widget"] = [
                *st.session_state.get("selected_origin_ids_widget", origin_candidates["zone_id"].astype(str).tolist()),
                origin_id,
            ]
            st.session_state.pop("pending_origin_node_id", None)
            st.rerun()

    origin_labels = {
        **dict(zip(origin_candidates["zone_id"].astype(str), origin_candidates["zone_name"].astype(str))),
        **{str(item["zone_id"]): str(item["zone_name"]) for item in custom_origins},
    }
    all_origin_ids = list(origin_labels)
    origin_widget_key = "selected_origin_ids_widget"
    if origin_widget_key not in st.session_state:
        st.session_state[origin_widget_key] = all_origin_ids.copy()
    selected_origin_ids = st.multiselect(
        "Origin areas included", all_origin_ids,
        key=origin_widget_key,
        format_func=lambda zone_id: origin_labels[str(zone_id)],
        help="Select the named origin areas that will contribute synthetic evacuee groups.",
    )
    scenario_people_limit = st.number_input(
        "Maximum people in this run", min_value=1, max_value=100_000,
        value=gubat_population_total, step=100,
        help=f"Overall scenario cap. The only current population reference is the provisional Gubat total of {gubat_population_total:,}; amounts beyond it are user-entered assumptions for a wider study area.",
    )
    origin_people_caps = {}
    remaining_people = int(scenario_people_limit)
    if selected_origin_ids:
        default_cap, remainder = divmod(remaining_people, len(selected_origin_ids))
        for index, zone_id in enumerate(selected_origin_ids):
            candidate_name = origin_labels[str(zone_id)]
            available = max(remaining_people, 0)
            default_value = min(available, default_cap + (1 if index < remainder else 0))
            cap_key = f"origin_people_cap_{zone_id}"
            if int(st.session_state.get(cap_key, default_value)) > available:
                st.session_state[cap_key] = available
            origin_people_caps[zone_id] = int(st.number_input(
                f"Scenario evacuees · {candidate_name}", min_value=0, max_value=available,
                value=default_value, step=50, key=cap_key,
            ))
            remaining_people -= origin_people_caps[zone_id]
    else:
        st.warning("Select at least one origin area to generate a scenario.")
    small_party_share_pct = st.slider("Small-party share (%) · assumption", 0, 50, 15, 5)
    departure_window_min = st.slider("Random departure window (minutes)", 0, 60, 15, 1)
    random_seed = st.number_input("Random seed (repeatable run)", min_value=0, max_value=2_147_483_647, value=2026, step=1)
    st.caption("Per-area amounts are user-set scenario assumptions, not measured population counts. Their sum cannot exceed the run cap.")
    origin_pin_shares = {}
    scenario_destination_ids = list(dict.fromkeys(
        str(node_id) for node_id in st.session_state.get("candidate_destination_node_ids", [])
    ))
    if scenario_destination_ids and selected_origin_ids:
        st.divider()
        st.subheader("Send each origin to pins")
        st.caption("Set the planned share of each origin assigned to each pin. Unassigned shares remain unassigned; area shares are scenario choices, not observed movement patterns.")
        for origin_id in selected_origin_ids:
            origin_name = origin_labels[str(origin_id)]
            with st.expander(origin_name, expanded=False):
                shares = {}
                share_cols = st.columns(2)
                for pin_index, node_id in enumerate(scenario_destination_ids):
                    pin_key = f"origin_pin_share_{origin_id}_{node_id}"
                    shares[node_id] = int(share_cols[pin_index % 2].number_input(
                        f"Pin {pin_index + 1} share (%)",
                        min_value=0, max_value=100, value=0, step=5, key=pin_key,
                        help=f"Share of {origin_name}'s scenario evacuees assigned to road node {node_id}.",
                    ))
                origin_pin_shares[origin_id] = shares
                share_total = sum(shares.values())
                st.caption(f"Configured: {share_total}% · {max(100 - share_total, 0)}% remains intentionally unassigned" if share_total <= 100 else f"Configured: {share_total}% · reduce this to 100% or less")

result = run_simulation(
    inputs,
    population_scale=population_scale,
    speed_scale=speed_scale,
    capacity_scale=capacity_scale,
    departure_delay_min=departure_delay,
    planning_window_min=planning_window,
    closed_edges=closed_edges,
)

@st.cache_data
def load_interactive_map_data(base_dir: str, graph_revision: tuple[int, int]):
    base = Path(base_dir)
    return {
        "hazard": read_gpkg_features(base / "data" / "gubat_tsunami_clip_fixed.gpkg"),
        "daet_hazard": read_gpkg_features(base / "data" / "daet_tsunami_inundation.gpkg"),
        "gubat_boundary": read_gpkg_features(base / "data" / "gubat_boundary_traced_fixed.gpkg"),
        "daet_boundary": read_gpkg_features(base / "data" / "daet_boundary.gpkg"),
        "regional_boundary": read_gpkg_features(base / "data" / "daet_basud_boundary.gpkg"),
        "buildings": read_gpkg_features(base / "data" / "raw" / "osm_daet_buildings.gpkg"),
        "road_nodes": pd.read_csv(base / "data" / "daet_basud_network_nodes.csv"),
        "road_edges": pd.read_csv(base / "data" / "daet_basud_network_edges.csv"),
    }


def polygon_parts(geometry):
    if geometry["type"] == "Polygon":
        return [geometry["coordinates"]]
    if geometry["type"] == "MultiPolygon":
        return geometry["coordinates"]
    return []


def point_in_ring(lon, lat, ring):
    """Ray-casting point-in-ring check for the local EPSG:4326 hazard overlay."""
    inside = False
    if not ring:
        return False
    x1, y1 = ring[-1][0], ring[-1][1]
    for point in ring:
        x2, y2 = point[0], point[1]
        crosses = (y1 > lat) != (y2 > lat)
        if crosses:
            crossing_lon = (x2 - x1) * (lat - y1) / (y2 - y1) + x1
            if lon < crossing_lon:
                inside = not inside
        x1, y1 = x2, y2
    return inside


def point_in_polygon(lon, lat, rings):
    """Return whether a point lies in a polygon, excluding its interior holes."""
    if not rings or not point_in_ring(lon, lat, rings[0]):
        return False
    return not any(point_in_ring(lon, lat, hole) for hole in rings[1:])


def route_hazard_overlap(route_nodes, routing_graph, node_lookup, hazard_features, sample_spacing_m=5.0):
    """Estimate route length within the static maximum-inundation polygons by sampling."""
    hazard_polygons = []
    for feature in hazard_features:
        depth_class = str(feature.get("properties", {}).get("Inun_depth", "Unclassified"))
        for rings in polygon_parts(feature["geometry"]):
            if not rings or not rings[0]:
                continue
            outer = rings[0]
            bounds = (
                min(point[0] for point in outer), min(point[1] for point in outer),
                max(point[0] for point in outer), max(point[1] for point in outer),
            )
            hazard_polygons.append((depth_class, rings, bounds))

    distance_by_class = {}
    for start_node, end_node in zip(route_nodes, route_nodes[1:]):
        start = node_lookup.loc[start_node]
        end = node_lookup.loc[end_node]
        lon1, lat1 = float(start["lon"]), float(start["lat"])
        lon2, lat2 = float(end["lon"]), float(end["lat"])
        edge_length_m = float(routing_graph[start_node][end_node].get("length_m", 0.0))
        if edge_length_m <= 0:
            continue
        edge_bounds = (min(lon1, lon2), min(lat1, lat2), max(lon1, lon2), max(lat1, lat2))
        candidates = [
            polygon for polygon in hazard_polygons
            if polygon[2][0] <= edge_bounds[2] and polygon[2][2] >= edge_bounds[0]
            and polygon[2][1] <= edge_bounds[3] and polygon[2][3] >= edge_bounds[1]
        ]
        if not candidates:
            continue
        samples = max(1, math.ceil(edge_length_m / sample_spacing_m))
        counts = {}
        for index in range(samples + 1):
            fraction = index / samples
            lon = lon1 + (lon2 - lon1) * fraction
            lat = lat1 + (lat2 - lat1) * fraction
            classes_here = {
                depth_class for depth_class, rings, bounds in candidates
                if bounds[0] <= lon <= bounds[2] and bounds[1] <= lat <= bounds[3]
                and point_in_polygon(lon, lat, rings)
            }
            for depth_class in classes_here:
                counts[depth_class] = counts.get(depth_class, 0) + 1
        for depth_class, count in counts.items():
            distance_by_class[depth_class] = distance_by_class.get(depth_class, 0.0) + edge_length_m * count / (samples + 1)
    return distance_by_class


def closest_nodes_between_components(source_component, destination_components, component_nodes, node_lookup):
    """Find the closest mapped-node pair across disconnected routing components for review only."""
    source_nodes = component_nodes.get(source_component, set())
    target_nodes = set().union(*(component_nodes.get(component, set()) for component in destination_components))
    if not source_nodes or not target_nodes:
        return None
    latitude_reference = float(node_lookup.loc[list(source_nodes | target_nodes), "lat"].mean())
    lon_scale = 111_320.0 * math.cos(math.radians(latitude_reference))
    lat_scale = 111_320.0
    source_ids = list(source_nodes)
    target_ids = list(target_nodes)
    source_xy = np.array([
        [float(node_lookup.loc[node_id, "lon"]) * lon_scale,
         float(node_lookup.loc[node_id, "lat"]) * lat_scale]
        for node_id in source_ids
    ])
    target_xy = np.array([
        [float(node_lookup.loc[node_id, "lon"]) * lon_scale,
         float(node_lookup.loc[node_id, "lat"]) * lat_scale]
        for node_id in target_ids
    ])
    best = None
    for offset in range(0, len(source_ids), 128):
        chunk = source_xy[offset:offset + 128]
        squared_distances = (
            (chunk[:, None, 0] - target_xy[None, :, 0]) ** 2
            + (chunk[:, None, 1] - target_xy[None, :, 1]) ** 2
        )
        flat_index = int(np.argmin(squared_distances))
        row_index, target_index = np.unravel_index(flat_index, squared_distances.shape)
        distance = math.sqrt(float(squared_distances[row_index, target_index]))
        if best is None or distance < best["gap_m"]:
            best = {
                "gap_m": distance,
                "source_node": source_ids[offset + int(row_index)],
                "target_node": target_ids[int(target_index)],
            }
    return best


def add_polygon_layer(
    fig, features, fill_color, line_color, name, show_legend=False,
    fill_opacity=0.35, visible=True,
):
    first = True
    trace_indices = []
    for feature in features:
        for polygon in polygon_parts(feature["geometry"]):
            if not polygon:
                continue
            ring = polygon[0]
            trace_indices.append(len(fig.data))
            fig.add_trace(go.Scattermapbox(
                lon=[point[0] for point in ring],
                lat=[point[1] for point in ring],
                mode="lines",
                fill="toself",
                fillcolor=fill_color,
                opacity=fill_opacity,
                line={"color": line_color, "width": 1.5},
                name=name,
                legendgroup=name,
                showlegend=show_legend and first,
                visible=visible,
                hoverinfo="skip",
            ))
            first = False
    return trace_indices


def add_evacuation_movement_animation(
    fig, group_routes, node_lookup, graph, destination_node_ids, speed_mps
):
    """Animate anonymous groups along assigned candidate road-graph paths."""
    if not group_routes or speed_mps <= 0:
        return 0

    colors = ["#7c3aed", "#f97316", "#06b6d4", "#e11d48", "#16a34a", "#eab308"]
    pin_index_by_node = {str(node_id): index for index, node_id in enumerate(destination_node_ids)}
    trace_index_by_pin = {}
    for pin_index, node_id in enumerate(destination_node_ids):
        trace_index_by_pin[str(node_id)] = len(fig.data)
        fig.add_trace(go.Scattermapbox(
            lon=[], lat=[], mode="markers",
            marker={"size": [], "color": colors[pin_index % len(colors)], "opacity": 0.95},
            customdata=[],
            name=f"Evacuee groups moving to Pin {pin_index + 1}",
            hovertemplate=(
                "%{customdata[0]}<br>Synthetic group size: %{customdata[1]} people<br>"
                "Moving to Pin %{customdata[2]}"
                "<extra></extra>"
            ),
        ))

    prepared = []
    path_cache = {}
    for group in group_routes:
        node_ids = [str(node_id) for node_id in group["nodes"]]
        if len(node_ids) < 2 or str(group["destination_node_id"]) not in trace_index_by_pin:
            continue
        path_key = (str(group["destination_node_id"]), tuple(node_ids))
        if path_key not in path_cache:
            coordinates = [node_lookup.loc[node_id] for node_id in node_ids]
            cumulative_m = [0.0]
            for left, right in zip(node_ids, node_ids[1:]):
                cumulative_m.append(
                    cumulative_m[-1] + float(graph[left][right].get("length_m", 0.0))
                )
            path_cache[path_key] = (coordinates, cumulative_m)
        coordinates, cumulative_m = path_cache[path_key]
        route_length_m = cumulative_m[-1]
        if route_length_m <= 0:
            continue
        travel_min = route_length_m / speed_mps / 60.0
        prepared.append({
            **group,
            "node_ids": node_ids,
            "coordinates": coordinates,
            "cumulative_m": cumulative_m,
            "route_length_m": route_length_m,
            "travel_min": travel_min,
        })

    if not prepared:
        return 0

    end_min = max(float(group["departure_min"]) + group["travel_min"] for group in prepared)
    frame_count = min(40, max(8, math.ceil(end_min / 0.5)))
    step_min = end_min / frame_count if end_min > 0 else 1.0
    times = [index * step_min for index in range(frame_count + 1)]
    frame_names = [f"evacuation-{index:03d}" for index in range(len(times))]
    moving_trace_indices = [trace_index_by_pin[node_id] for node_id in destination_node_ids]
    frames = []

    for frame_index, minute in enumerate(times):
        pin_positions = {str(node_id): {"lon": [], "lat": [], "sizes": [], "customdata": []}
                         for node_id in destination_node_ids}
        for group in prepared:
            elapsed = minute - float(group["departure_min"])
            if elapsed < 0 or elapsed >= group["travel_min"]:
                continue
            distance_m = min(elapsed * speed_mps * 60.0, group["route_length_m"])
            segment = 0
            cumulative = group["cumulative_m"]
            while segment < len(cumulative) - 2 and cumulative[segment + 1] < distance_m:
                segment += 1
            segment_length = cumulative[segment + 1] - cumulative[segment]
            fraction = (distance_m - cumulative[segment]) / segment_length if segment_length else 0.0
            start, finish = group["coordinates"][segment], group["coordinates"][segment + 1]
            lon = float(start["lon"]) + (float(finish["lon"]) - float(start["lon"])) * fraction
            lat = float(start["lat"]) + (float(finish["lat"]) - float(start["lat"])) * fraction
            destination = str(group["destination_node_id"])
            slot = pin_positions[destination]
            slot["lon"].append(lon)
            slot["lat"].append(lat)
            slot["sizes"].append(min(20, 8 + math.sqrt(int(group["group_size"]))))
            slot["customdata"].append([
                str(group["origin"]), int(group["group_size"]), pin_index_by_node[destination] + 1,
            ])
        frame_data = [
            go.Scattermapbox(
                lon=pin_positions[str(node_id)]["lon"],
                lat=pin_positions[str(node_id)]["lat"],
                marker={"size": pin_positions[str(node_id)]["sizes"]},
                customdata=pin_positions[str(node_id)]["customdata"],
            )
            for node_id in destination_node_ids
        ]
        frames.append(go.Frame(
            name=frame_names[frame_index], data=frame_data, traces=moving_trace_indices,
        ))

    fig.frames += tuple(frames)
    fig.update_layout(
        height=550,
        margin={"l": 0, "r": 0, "t": 0, "b": 10},
        mapbox={**fig.layout.mapbox.to_plotly_json(), "domain": {"x": [0, 1], "y": [0.23, 1]}},
        updatemenus=[{
            "type": "buttons", "direction": "left", "showactive": False,
            "x": 0.01, "y": 0.02, "xanchor": "left", "yanchor": "bottom",
            "pad": {"r": 8, "t": 0},
            "buttons": [
                {"label": "▶ Play movement", "method": "animate",
                 "args": [frame_names, {"frame": {"duration": 450, "redraw": True},
                                          "transition": {"duration": 0}, "fromcurrent": True,
                                          "mode": "immediate"}]},
                {"label": "Ⅱ Pause", "method": "animate",
                 "args": [[None], {"frame": {"duration": 0, "redraw": False},
                                     "mode": "immediate", "transition": {"duration": 0}}]},
                {"label": "↺ Restart", "method": "animate",
                 "args": [[frame_names[0]], {"frame": {"duration": 0, "redraw": True},
                                               "mode": "immediate", "transition": {"duration": 0}}]},
            ],
        }],
        sliders=[{
            "active": 0, "x": 0.28, "y": 0.045, "len": 0.70,
            "currentvalue": {"prefix": "Evacuation minute ", "visible": True},
            "steps": [
                {"label": f"{minute:.1f}", "method": "animate",
                 "args": [[frame_name], {"frame": {"duration": 0, "redraw": True},
                                            "mode": "immediate", "transition": {"duration": 0}}]}
                for minute, frame_name in zip(times, frame_names)
            ],
        }],
    )
    return len(prepared)


def add_boundary_layer(fig, features, color, name):
    first = True
    for feature in features:
        geometry = feature["geometry"]
        for polygon in polygon_parts(geometry):
            for ring in polygon:
                fig.add_trace(go.Scattermapbox(
                    lon=[point[0] for point in ring],
                    lat=[point[1] for point in ring],
                    mode="lines",
                    line={"color": color, "width": 2.5},
                    name=name,
                    showlegend=first,
                    hoverinfo="skip",
                ))
                first = False


def road_bbox_for_extent(extent):
    return {
        "Gubat": (122.957, 14.104, 122.991, 14.133),
        "Daet": (122.887, 14.065, 123.005, 14.155),
        "Daet–Basud": (122.887, 13.918, 123.058, 14.148),
    }[extent]


def add_road_layer(fig, road_edges, road_nodes, bounds):
    min_lon, min_lat, max_lon, max_lat = bounds
    nodes = {
        str(row.node_id): (float(row.lon), float(row.lat))
        for row in road_nodes.itertuples(index=False)
    }
    edges = road_edges.loc[road_edges["edge_id"].astype(str).str.endswith("_F")]
    edges = edges.loc[edges["highway"].isin([
        "primary", "secondary", "tertiary", "trunk", "residential", "unclassified",
        "service", "track", "path", "footway", "construction",
    ])]
    colors = {
        "primary": "#c2410c", "secondary": "#ea580c", "tertiary": "#f59e0b",
        "trunk": "#b91c1c", "residential": "#64748b", "unclassified": "#94a3b8",
        "service": "#a8a29e", "track": "#65a30d", "path": "#16a34a",
        "footway": "#0d9488", "construction": "#dc2626",
    }
    for highway, group in edges.groupby("highway", sort=False):
        lons, lats = [], []
        for row in group.itertuples(index=False):
            a = nodes.get(str(row.from_node))
            b = nodes.get(str(row.to_node))
            if not a or not b:
                continue
            if max(a[0], b[0]) < min_lon or min(a[0], b[0]) > max_lon or max(a[1], b[1]) < min_lat or min(a[1], b[1]) > max_lat:
                continue
            lons.extend((a[0], b[0], None))
            lats.extend((a[1], b[1], None))
        if lons:
            fig.add_trace(go.Scattermapbox(
                lon=lons, lat=lats, mode="lines",
                line={"color": colors.get(highway, "#64748b"), "width": 1.4},
                name=f"Road · {highway}", hoverinfo="skip",
            ))


def geometry_coordinate_pairs(value):
    """Yield coordinate pairs from a GeoJSON geometry coordinate tree."""
    if isinstance(value, (list, tuple)):
        if len(value) >= 2 and isinstance(value[0], (int, float)) and isinstance(value[1], (int, float)):
            yield float(value[0]), float(value[1])
        else:
            for child in value:
                yield from geometry_coordinate_pairs(child)


def clear_map_search_selection():
    st.session_state["map_search_selected"] = None


def apply_map_search_selection():
    selected_label = st.session_state.get("map_search_selected")
    selected = next((item for item in map_search_catalog if item["label"] == selected_label), None)
    if selected:
        lon, lat = selected["lon"], selected["lat"]
        if 122.957 <= lon <= 122.991 and 14.104 <= lat <= 14.133:
            st.session_state["map_extent"] = "Gubat"
        elif 122.887 <= lon <= 123.005 and 14.065 <= lat <= 14.155:
            st.session_state["map_extent"] = "Daet"
        else:
            st.session_state["map_extent"] = "Daet–Basud"


@st.cache_data
def load_map_search_catalog(base_dir: str, graph_revision: tuple[int, int]):
    """Build local name search entries from the packaged OSM project layers."""
    base = Path(base_dir)
    nodes = pd.read_csv(base / "data" / "daet_basud_network_nodes.csv").assign(
        node_id=lambda frame: frame["node_id"].astype(str)
    ).set_index("node_id")
    edges = pd.read_csv(base / "data" / "daet_basud_network_edges.csv")
    forward_edges = edges.loc[edges["edge_id"].astype(str).str.endswith("_F")]
    entries = []

    for _, road in forward_edges.iterrows():
        name = str(road.get("name", "")).strip()
        if not name or name.lower() == "nan":
            name = str(road.get("ref", "")).strip()
        if name and name.lower() != "nan":
            entries.append((name, str(road.get("highway", "road")), str(road["from_node"]), str(road["to_node"])))

    road_search_rows = {}
    for name, road_type, from_node, to_node in entries:
        key = (name, road_type)
        road_search_rows.setdefault(key, set()).update((from_node, to_node))
    catalog = []
    for (name, road_type), node_ids in road_search_rows.items():
        valid_nodes = [node_id for node_id in node_ids if node_id in nodes.index]
        if not valid_nodes:
            continue
        subset = nodes.loc[valid_nodes]
        catalog.append({
            "label": f"Road · {name} ({road_type})",
            "search_text": f"{name} {road_type} road street",
            "kind": "Road",
            "name": name,
            "lat": float(subset["lat"].mean()),
            "lon": float(subset["lon"].mean()),
        })

    for feature in read_gpkg_features(base / "data" / "raw" / "osm_daet_buildings.gpkg"):
        properties = feature["properties"]
        name = next((str(properties.get(field, "")).strip() for field in
                     ("name", "name:en", "official_name", "short_name", "addr:housename", "brand")
                     if properties.get(field) and str(properties.get(field)).strip().lower() != "nan"), "")
        if not name:
            continue
        coordinates = list(geometry_coordinate_pairs(feature["geometry"].get("coordinates", [])))
        if not coordinates:
            continue
        min_lon = min(point[0] for point in coordinates)
        max_lon = max(point[0] for point in coordinates)
        min_lat = min(point[1] for point in coordinates)
        max_lat = max(point[1] for point in coordinates)
        category = next((str(properties.get(field, "")).strip() for field in
                         ("amenity", "shop", "office", "building", "tourism")
                         if properties.get(field) and str(properties.get(field)).strip().lower() != "nan"), "building")
        catalog.append({
            "label": f"Building/place · {name} ({category})",
            "search_text": f"{name} {category} building place",
            "kind": "Building/place",
            "name": name,
            "lat": (min_lat + max_lat) / 2,
            "lon": (min_lon + max_lon) / 2,
        })

    candidates = pd.read_csv(base / "data" / "origin_zone_candidates.csv")
    for row in candidates.itertuples(index=False):
        catalog.append({
            "label": f"Named area · {row.zone_name}",
            "search_text": f"{row.zone_name} {row.map_label} {row.locality_type}",
            "kind": "Named area",
            "name": str(row.zone_name),
            "lat": float(row.latitude),
            "lon": float(row.longitude),
        })
    catalog.sort(key=lambda item: (item["kind"], item["name"].casefold(), item["label"]))
    label_counts = {}
    for item in catalog:
        base_label = item["label"]
        label_counts[base_label] = label_counts.get(base_label, 0) + 1
        if label_counts[base_label] > 1:
            item["label"] = f"{base_label} · result {label_counts[base_label]}"
    return catalog


def remember_map_point_selection():
    """Save a clicked graph node as a staged origin anchor or receiving pin."""
    event = st.session_state.get("scenario_geographic_map", {})
    selection = event.get("selection", {}) if hasattr(event, "get") else {}
    points = selection.get("points", []) if hasattr(selection, "get") else []
    for point in points:
        custom = point.get("customdata")
        if isinstance(custom, (list, tuple)) and len(custom) >= 2:
            if custom[0] == "CANDIDATE_DESTINATION_NODE":
                st.session_state["candidate_destination_node_id"] = str(custom[1])
                return
            if custom[0] == "CANDIDATE_ORIGIN_NODE":
                st.session_state["pending_origin_node_id"] = str(custom[1])
                return


try:
    graph_paths = (
        Path(project_dir) / "data" / "daet_basud_network_nodes.csv",
        Path(project_dir) / "data" / "daet_basud_network_edges.csv",
    )
    graph_revision = tuple(path.stat().st_mtime_ns for path in graph_paths)
    map_data = load_interactive_map_data(str(project_dir), graph_revision)
    active_extent = st.session_state.get("map_extent", "Gubat")
    active_hazard_features = (
        map_data["hazard"] if active_extent == "Gubat" else map_data["daet_hazard"]
    )
    map_search_catalog = load_map_search_catalog(str(project_dir), graph_revision)
    zone_anchors = scenario_generation.load_named_zone_anchors(
        Path(project_dir) / "data" / "origin_zone_candidates.csv",
        map_data["gubat_boundary"],
    )
    access_candidates = pd.read_csv(Path(project_dir) / "data" / "origin_access_candidates.csv")
    # Keep the QGIS-reviewed road-node candidates as the explicit graph entry
    # points for aggregate scenario groups. These are not confirmed entrances.
    access_columns = ["zone_id", "candidate_node_id", "candidate_lon", "candidate_lat", "distance_m", "status"]
    access_for_zones = access_candidates[access_columns].rename(columns={
        "candidate_node_id": "road_node_id",
        "candidate_lon": "road_lon",
        "candidate_lat": "road_lat",
        "distance_m": "anchor_to_road_m",
        "status": "road_access_status",
    })
    node_road_names = {}
    for row in map_data["road_edges"].itertuples(index=False):
        node_road_names.setdefault(str(row.from_node), set()).add(str(row.name).strip())
        node_road_names.setdefault(str(row.to_node), set()).add(str(row.name).strip())
    access_for_zones["candidate_road_name"] = access_for_zones["road_node_id"].map(
        lambda node_id: "; ".join(sorted(
            name for name in node_road_names.get(str(node_id), set()) if name and name.lower() != "nan"
        )) or "Unnamed OSM road/path"
    )
    zone_anchors = zone_anchors.merge(access_for_zones, on="zone_id", how="left", validate="one_to_one")
    if zone_anchors["road_node_id"].isna().any():
        missing_access = zone_anchors.loc[zone_anchors["road_node_id"].isna(), "zone_name"].tolist()
        raise ValueError(f"No candidate road-node connection is recorded for: {missing_access}")
    road_node_lookup = map_data["road_nodes"].assign(
        node_id=lambda frame: frame["node_id"].astype(str)
    ).set_index("node_id")
    custom_anchor_rows = []
    for custom_origin in custom_origins:
        custom_node_id = str(custom_origin["road_node_id"])
        if custom_node_id not in road_node_lookup.index:
            continue
        selected_node = road_node_lookup.loc[custom_node_id]
        row = zone_anchors.iloc[0].to_dict()
        row.update({
            "zone_id": str(custom_origin["zone_id"]),
            "zone_name": str(custom_origin["zone_name"]),
            "map_label": str(custom_origin.get("map_label", custom_origin["zone_name"])),
            "locality_type": "user-defined aggregate origin",
            "lon": float(selected_node["lon"]),
            "lat": float(selected_node["lat"]),
            "road_node_id": custom_node_id,
            "road_lon": float(selected_node["lon"]),
            "road_lat": float(selected_node["lat"]),
            "anchor_to_road_m": 0.0,
            "candidate_road_name": "; ".join(sorted(
                name for name in node_road_names.get(custom_node_id, set()) if name and name.lower() != "nan"
            )) or "Unnamed OSM road/path",
            "road_access_status": "USER_SELECTED_REPRESENTATIVE_NODE_NOT_FIELD_VERIFIED",
            "notes": "User-defined aggregate scenario origin placed at an existing road graph node; not a household point or official zone boundary.",
        })
        custom_anchor_rows.append(row)
    if custom_anchor_rows:
        zone_anchors = pd.concat([zone_anchors, pd.DataFrame(custom_anchor_rows)], ignore_index=True)
    # Report raw geometric graph connectivity without treating it as verified
    # pedestrian connectivity. The exported OSM graph may contain unmapped gaps.
    candidate_graph = nx.Graph()
    candidate_graph.add_nodes_from(map_data["road_nodes"]["node_id"].astype(str))
    routing_graph = nx.Graph()
    routing_graph.add_nodes_from(map_data["road_nodes"]["node_id"].astype(str))
    forward_edges = map_data["road_edges"].loc[
        map_data["road_edges"]["edge_id"].astype(str).str.endswith("_F")
    ]
    def pedestrian_link_allowed(access_value, foot_value, highway_value):
        access_tag = str(access_value).strip().lower()
        foot_tag = str(foot_value).strip().lower()
        highway_tag = str(highway_value).strip().lower()
        denied = {"no", "private", "restricted", "customers", "delivery", "permit"}
        allowed = {"yes", "designated", "permissive", "official"}
        if highway_tag == "construction" or foot_tag in denied | {"use_sidepath"}:
            return False
        # OSM's foot-specific tag takes precedence over the general access tag.
        if foot_tag in allowed:
            return True
        return access_tag not in denied

    for edge in forward_edges.itertuples(index=False):
        length_m = max(float(edge.length_m), 0.0)
        candidate_graph.add_edge(
            str(edge.from_node), str(edge.to_node),
            length_m=length_m,
            free_flow_min=length_m / (1.15 * float(speed_scale)) / 60.0,
            highway=str(edge.highway),
            name=str(edge.name),
        )
        highway_tag = str(edge.highway).strip().lower()
        if pedestrian_link_allowed(edge.access, edge.foot, highway_tag):
            routing_graph.add_edge(
                str(edge.from_node), str(edge.to_node),
                length_m=length_m,
                free_flow_min=length_m / (1.15 * float(speed_scale)) / 60.0,
                highway=highway_tag,
                name=str(edge.name),
            )
    component_for_node = {}
    component_size_for_node = {}
    component_counter = 0
    for component in nx.connected_components(candidate_graph):
        for node_id in component:
            component_for_node[node_id] = component_counter
            component_size_for_node[node_id] = len(component)
        component_counter += 1
    candidate_zone_component = {
        str(row.road_node_id): (component_for_node.get(str(row.road_node_id)), component_size_for_node.get(str(row.road_node_id), 0))
        for row in zone_anchors.itertuples(index=False)
    }
    zone_component_ids = {
        str(row.zone_id): candidate_zone_component[str(row.road_node_id)][0]
        for row in zone_anchors.itertuples(index=False)
    }
    selected_zone_anchors = zone_anchors.loc[zone_anchors["zone_id"].astype(str).isin(selected_origin_ids)].copy()
    groups_by_area = []
    for area_index, origin in enumerate(selected_zone_anchors.to_dict("records")):
        people_cap = int(origin_people_caps.get(str(origin["zone_id"]), 0))
        if people_cap <= 0:
            continue
        area_groups = scenario_generation.generate_synthetic_groups(
            total_people=people_cap,
            small_party_share=small_party_share_pct / 100.0,
            departure_window_min=departure_window_min,
            seed=int(random_seed) + area_index * 10_007,
        )
        area_groups["group_id"] = [f"{origin['zone_id']}-{group_id}" for group_id in area_groups["group_id"]]
        area_groups["zone_id"] = str(origin["zone_id"])
        area_groups["zone"] = str(origin["zone_name"])
        groups_by_area.append(area_groups)
    if not groups_by_area:
        raise ValueError("Set at least one selected origin area's evacuee cap above zero")
    synthetic_groups = pd.concat(groups_by_area, ignore_index=True).sort_values(
        ["departure_min", "group_id"], ignore_index=True
    )
    zone_people = synthetic_groups.groupby("zone_id", as_index=False).agg(
        groups=("group_id", "count"), people=("group_size", "sum")
    )
    zone_summary = zone_anchors.merge(zone_people, on="zone_id", how="left").fillna({"groups": 0, "people": 0})
    zone_summary["groups"] = zone_summary["groups"].astype(int)
    zone_summary["people"] = zone_summary["people"].astype(int)
    scenario_people_total = max(int(synthetic_groups["group_size"].sum()), 1)
    zone_summary["simulated_share_pct"] = (zone_summary["people"] / scenario_people_total * 100).round(1)
    zone_access = zone_anchors.set_index("zone_id")
    synthetic_groups["road_node_id"] = synthetic_groups["zone_id"].map(zone_access["road_node_id"])
    zone_summary["graph_component_vertices"] = zone_summary["road_node_id"].map(
        lambda node_id: component_size_for_node.get(str(node_id), 0)
    )
    zone_summary["shares_candidate_component_with"] = zone_summary.apply(
        lambda row: ", ".join(
            str(other.zone_name) for other in zone_anchors.itertuples(index=False)
            if str(other.zone_id) != str(row.zone_id)
            and zone_component_ids[str(other.zone_id)] == zone_component_ids[str(row.zone_id)]
        ) or "No other included origin candidate",
        axis=1,
    )
except Exception as exc:
    st.error(f"Could not prepare the synthetic origin zones: {exc}")
    st.stop()

map_node_lookup = map_data["road_nodes"].assign(
    node_id=lambda frame: frame["node_id"].astype(str)
).set_index("node_id")
route_component_for_node = {}
route_component_size = {}
route_component_nodes = {}
for component_index, component in enumerate(nx.connected_components(routing_graph), start=1):
    members = set(component)
    route_component_nodes[component_index] = members
    for node_id in members:
        route_component_for_node[node_id] = component_index
        route_component_size[node_id] = len(members)

destination_node_ids = list(dict.fromkeys(
    str(node_id) for node_id in st.session_state.get("candidate_destination_node_ids", [])
    if str(node_id) in map_node_lookup.index
))
destination_pin_colors = ["#7c3aed", "#f97316", "#06b6d4", "#e11d48", "#16a34a", "#eab308"]
destination_capacity_remaining = {
    node_id: int(st.session_state.get(f"receiving_capacity_{node_id}", 0))
    for node_id in destination_node_ids
}
destination_path_options = {}
for origin in zone_summary.loc[zone_summary["people"] > 0].to_dict("records"):
    origin_node_id = str(origin["road_node_id"])
    options = []
    for destination_node_id in destination_node_ids:
        if origin_node_id not in routing_graph or destination_node_id not in routing_graph:
            continue
        if not nx.has_path(routing_graph, origin_node_id, destination_node_id):
            continue
        path_nodes = nx.shortest_path(
            routing_graph, origin_node_id, destination_node_id, weight="free_flow_min"
        )
        path_length = sum(float(routing_graph[a][b].get("length_m", 0.0)) for a, b in zip(path_nodes, path_nodes[1:]))
        path_time = sum(float(routing_graph[a][b].get("free_flow_min", 0.0)) for a, b in zip(path_nodes, path_nodes[1:]))
        options.append((path_time, path_length, destination_node_id, path_nodes))
    destination_path_options[str(origin["zone_id"])] = options

route_assignments = []
group_route_assignments = []
unassigned_by_origin = {}
route_summary = {}
origin_assignment_totals = {}
origin_assignment_by_pin = {}
for group in synthetic_groups.sort_values(["departure_min", "group_id"]).to_dict("records"):
    zone_id = str(group["zone_id"])
    options = destination_path_options.get(zone_id, [])
    shares = origin_pin_shares.get(zone_id, {})
    share_total = sum(int(share) for share in shares.values())
    reachable_destination_ids = {item[2] for item in options}
    unreachable_share_pct = sum(
        int(shares.get(destination_id, 0))
        for destination_id in destination_node_ids
        if int(shares.get(destination_id, 0)) > 0 and destination_id not in reachable_destination_ids
    )
    origin_total = int(zone_summary.loc[zone_summary["zone_id"].astype(str) == zone_id, "people"].iloc[0])
    origin_assignment_totals.setdefault(zone_id, 0)
    origin_assignment_by_pin.setdefault(zone_id, {})
    unassigned_by_origin.setdefault(zone_id, {"network": 0, "capacity": 0, "allocation": 0, "invalid": 0, "groups": 0})
    group_size = int(group["group_size"])
    if share_total > 100:
        unassigned_by_origin[zone_id]["invalid"] += group_size
        unassigned_by_origin[zone_id]["groups"] += 1
        continue
    target_total = int(round(origin_total * share_total / 100.0))
    if share_total <= 0 or origin_assignment_totals[zone_id] >= target_total:
        unassigned_by_origin[zone_id]["allocation"] += group_size
        unassigned_by_origin[zone_id]["groups"] += 1
        continue
    configured_options = [item for item in options if int(shares.get(item[2], 0)) > 0]
    if not configured_options:
        unassigned_by_origin[zone_id]["network"] += group_size
        unassigned_by_origin[zone_id]["groups"] += 1
        continue
    if origin_assignment_totals[zone_id] + group_size > target_total:
        unassigned_by_origin[zone_id]["allocation"] += group_size
        unassigned_by_origin[zone_id]["groups"] += 1
        continue
    fitting_options = [
        item for item in configured_options
        if destination_capacity_remaining.get(item[2], 0) >= group_size
        and origin_assignment_by_pin[zone_id].get(item[2], 0) < origin_total * int(shares[item[2]]) / 100.0
    ]
    if not fitting_options:
        capacity_fits = [item for item in configured_options if destination_capacity_remaining.get(item[2], 0) >= group_size]
        reason = "network" if capacity_fits and unreachable_share_pct > 0 else "allocation" if capacity_fits else "capacity"
        unassigned_by_origin[zone_id][reason] += group_size
        unassigned_by_origin[zone_id]["groups"] += 1
        continue
    path_time, path_length, destination_node_id, path_nodes = max(
        fitting_options,
        key=lambda item: (origin_total * int(shares[item[2]]) / 100.0 - origin_assignment_by_pin[zone_id].get(item[2], 0), -item[0]),
    )
    destination_capacity_remaining[destination_node_id] -= group_size
    origin_assignment_totals[zone_id] += group_size
    origin_assignment_by_pin[zone_id][destination_node_id] = origin_assignment_by_pin[zone_id].get(destination_node_id, 0) + group_size
    group_departure_min = float(group["departure_min"]) + float(departure_delay)
    group_travel_min = sum(
        float(routing_graph[start][end].get("free_flow_min", 0.0))
        for start, end in zip(path_nodes, path_nodes[1:])
    )
    group_route_assignments.append({
        "group_id": str(group["group_id"]),
        "origin": str(group["zone"]),
        "group_size": group_size,
        "departure_min": group_departure_min,
        "travel_min": group_travel_min,
        "arrival_min": group_departure_min + group_travel_min,
        "destination_node_id": destination_node_id,
        "nodes": path_nodes,
    })
    assignment_key = (zone_id, destination_node_id)
    route_summary.setdefault(assignment_key, {
        "zone_id": zone_id,
        "origin": str(group["zone"]),
        "destination_node_id": destination_node_id,
        "nodes": path_nodes,
        "time_min": path_time,
        "length_m": path_length,
        "people": 0,
        "groups": 0,
    })
    route_summary[assignment_key]["people"] += group_size
    route_summary[assignment_key]["groups"] += 1

for assignment in route_summary.values():
    path_nodes = assignment["nodes"]
    assignment["hazard_overlap_m_by_class"] = route_hazard_overlap(
        path_nodes, routing_graph, map_node_lookup, active_hazard_features
    )
    assignment["named_roads"] = list(dict.fromkeys(
        str(routing_graph[a][b].get("name", "")).strip()
        for a, b in zip(path_nodes, path_nodes[1:])
        if str(routing_graph[a][b].get("name", "")).strip()
        and str(routing_graph[a][b].get("name", "")).strip().lower() != "nan"
    ))
    route_assignments.append(assignment)

unrouted_origins = []
active_origin_lookup = zone_summary.set_index("zone_id")
for zone_id, counts in unassigned_by_origin.items():
    if counts["network"] + counts["capacity"] + counts["allocation"] + counts["invalid"] == 0:
        continue
    origin = active_origin_lookup.loc[zone_id]
    origin_node_id = str(origin["road_node_id"])
    origin_component = route_component_for_node.get(origin_node_id)
    target_components = {
        route_component_for_node.get(destination_id)
        for destination_id in destination_node_ids
        if int(origin_pin_shares.get(zone_id, {}).get(destination_id, 0)) > 0
        and route_component_for_node.get(destination_id) is not None
        and route_component_for_node.get(destination_id) != origin_component
    }
    gap = closest_nodes_between_components(
        origin_component, target_components, route_component_nodes, map_node_lookup
    ) if counts["network"] and origin_component is not None and target_components else None
    reason_parts = []
    if counts["network"]:
        reason_parts.append("No connected selected pin for the configured shares")
    if counts["capacity"]:
        reason_parts.append("Pin headcount limit reached")
    if counts["allocation"]:
        reason_parts.append("No share allocated or configured share already reached")
    if counts["invalid"]:
        reason_parts.append("Origin-to-pin percentages exceed 100%")
    unrouted_origins.append({
        "Origin area": origin["zone_name"],
        "People not assigned": counts["network"] + counts["capacity"] + counts["allocation"] + counts["invalid"],
        "Groups not assigned": counts["groups"],
        "Reason": "; ".join(reason_parts),
        "No connected pin": counts["network"],
        "Pin capacity reached": counts["capacity"],
        "Share target reached": counts["allocation"],
        "Invalid shares": counts["invalid"],
        "Origin component": origin_component if origin_component is not None else "Missing",
        "Component nodes": route_component_size.get(origin_node_id, 0),
        "Closest unconnected node gap (m)": round(gap["gap_m"], 1) if gap else None,
        "Gap endpoint node IDs": f"{gap['source_node']} ↔ {gap['target_node']}" if gap else "",
    })

destination_capacity_summary = [
    {
        "Candidate pin": index + 1,
        "Road node": node_id,
        "Capacity entered": int(st.session_state.get(f"receiving_capacity_{node_id}", 0)),
        "People assigned": int(st.session_state.get(f"receiving_capacity_{node_id}", 0)) - destination_capacity_remaining[node_id],
        "Capacity remaining": destination_capacity_remaining[node_id],
        "Capacity used (%)": round(
            (int(st.session_state.get(f"receiving_capacity_{node_id}", 0)) - destination_capacity_remaining[node_id])
            / max(int(st.session_state.get(f"receiving_capacity_{node_id}", 0)), 1) * 100,
            1,
        ),
    }
    for index, node_id in enumerate(destination_node_ids)
]

pin_pair_routes = []
for left_index, left_node_id in enumerate(destination_node_ids):
    for right_index in range(left_index + 1, len(destination_node_ids)):
        right_node_id = destination_node_ids[right_index]
        connected = (
            left_node_id in routing_graph
            and right_node_id in routing_graph
            and nx.has_path(routing_graph, left_node_id, right_node_id)
        )
        if connected:
            pair_nodes = nx.shortest_path(
                routing_graph, left_node_id, right_node_id, weight="free_flow_min"
            )
            pair_length_m = sum(
                float(routing_graph[a][b].get("length_m", 0.0))
                for a, b in zip(pair_nodes, pair_nodes[1:])
            )
            pair_time_min = sum(
                float(routing_graph[a][b].get("free_flow_min", 0.0))
                for a, b in zip(pair_nodes, pair_nodes[1:])
            )
        else:
            pair_nodes = []
            pair_length_m = None
            pair_time_min = None
        pin_pair_routes.append({
            "Pin pair": f"Pin {left_index + 1} ↔ Pin {right_index + 1}",
            "Filtered graph connection": "Connected" if connected else "Not connected",
            "Road path (km)": round(pair_length_m / 1000, 2) if pair_length_m is not None else None,
            "Modeled walk time (min)": round(pair_time_min, 1) if pair_time_min is not None else None,
            "nodes": pair_nodes,
        })

# Make origin-to-pin reachability visible before users interpret allocation
# totals. A high pin share can remain unassigned when its road node is in a
# different filtered graph component from the origin's representative node.
origin_pin_connectivity_rows = []
component_gap_cache = {}
for origin in zone_summary.loc[zone_summary["people"] > 0].to_dict("records"):
    zone_id = str(origin["zone_id"])
    origin_node_id = str(origin["road_node_id"])
    origin_component = route_component_for_node.get(origin_node_id)
    options_by_destination = {
        item[2]: item for item in destination_path_options.get(zone_id, [])
    }
    for pin_index, destination_node_id in enumerate(destination_node_ids, start=1):
        destination_component = route_component_for_node.get(destination_node_id)
        configured_share = int(origin_pin_shares.get(zone_id, {}).get(destination_node_id, 0))
        path = options_by_destination.get(destination_node_id)
        row = {
            "Origin area": str(origin["zone_name"]),
            "Candidate pin": pin_index,
            "Planned share (%)": configured_share,
            "Connectivity": "Connected in filtered graph" if path else "Not connected in filtered graph",
            "Origin component": origin_component if origin_component is not None else "Missing",
            "Pin component": destination_component if destination_component is not None else "Missing",
            "Shortest path (km)": round(path[1] / 1000, 2) if path else None,
            "Modeled walk time (min)": round(path[0], 1) if path else None,
            "Closest graph-node gap (m)": None,
            "Closest origin-side node ID": None,
            "Closest origin-side node": None,
            "Origin-side mapped road(s)": None,
            "Closest pin-side node ID": None,
            "Closest pin-side node": None,
            "Pin-side mapped road(s)": None,
        }
        if origin_component is not None and destination_component is not None and origin_component != destination_component:
            component_pair = (origin_component, destination_component)
            if component_pair not in component_gap_cache:
                component_gap_cache[component_pair] = closest_nodes_between_components(
                    origin_component, {destination_component}, route_component_nodes, map_node_lookup
                )
            gap = component_gap_cache[component_pair]
            row["Closest graph-node gap (m)"] = round(gap["gap_m"], 1) if gap else None
            if gap:
                origin_gap_node = str(gap["source_node"])
                pin_gap_node = str(gap["target_node"])
                origin_gap_location = map_node_lookup.loc[origin_gap_node]
                pin_gap_location = map_node_lookup.loc[pin_gap_node]
                row["Closest origin-side node ID"] = origin_gap_node
                row["Closest origin-side node"] = (
                    f"{float(origin_gap_location['lat']):.5f}, {float(origin_gap_location['lon']):.5f}"
                )
                row["Origin-side mapped road(s)"] = "; ".join(sorted(node_road_names.get(origin_gap_node, set()))) or "Unnamed mapped road/path"
                row["Closest pin-side node ID"] = pin_gap_node
                row["Closest pin-side node"] = (
                    f"{float(pin_gap_location['lat']):.5f}, {float(pin_gap_location['lon']):.5f}"
                )
                row["Pin-side mapped road(s)"] = "; ".join(sorted(node_road_names.get(pin_gap_node, set()))) or "Unnamed mapped road/path"
        origin_pin_connectivity_rows.append(row)

departure_counts = (
    synthetic_groups.assign(departure_minute=synthetic_groups["departure_min"].astype(int))
    .groupby("departure_minute", as_index=False)["group_size"].sum()
    .rename(columns={"group_size": "people_departing"})
)
departure_counts = departure_counts.set_index("departure_minute").reindex(
    range(departure_window_min + 1), fill_value=0
).rename_axis("departure_minute").reset_index()

simulation_setup_issues = []
active_scenario_origins = [
    str(zone_id) for zone_id in selected_origin_ids
    if int(origin_people_caps.get(zone_id, 0)) > 0
]
if not active_scenario_origins:
    simulation_setup_issues.append("set a positive evacuee amount for at least one origin")
if not any(destination_capacity_remaining.get(node_id, 0) > 0 for node_id in destination_node_ids):
    simulation_setup_issues.append("add a receiving pin with positive scenario capacity")
active_share_totals = [
    sum(int(value) for value in origin_pin_shares.get(zone_id, {}).values())
    for zone_id in active_scenario_origins
]
if not active_share_totals or not any(total > 0 for total in active_share_totals):
    simulation_setup_issues.append("assign a positive origin share to at least one pin")
if any(total > 100 for total in active_share_totals):
    simulation_setup_issues.append("keep each origin's configured pin shares at or below 100%")
if not route_assignments:
    simulation_setup_issues.append("ensure at least one group has a connected route to a pin")

details_open = st.session_state.get("explore_details_open", True)
map_col, details_col = st.columns([4.1, 1.25] if details_open else [14, 0.8], gap="small")
with map_col:
    with st.container(height=760, key="map_stage"):
        st.markdown("### Tsunami Evacuation Scenario Explorer")
        st.session_state.setdefault("map_search_query", "")
        st.session_state.setdefault("map_search_selected", None)
        st.session_state.setdefault("map_extent", "Gubat")
        st.session_state.setdefault("show_roads", True)
        st.session_state.setdefault("show_hazard_v2", False)
        st.session_state.setdefault("show_boundaries_v2", False)
        st.session_state.setdefault("show_origins_v2", False)
        st.session_state.setdefault("map_point_type", "Receiving pin")
        st.session_state.setdefault("pick_destination_on_map", False)
        map_search_query = str(st.session_state.get("map_search_query", ""))
        search_matches = [
            item for item in map_search_catalog
            if len(map_search_query.strip()) >= 2
            and map_search_query.strip().casefold() in item["search_text"].casefold()
        ][:100]
        search_labels = [item["label"] for item in search_matches]
        search_selection = st.session_state.get("map_search_selected")
        if search_selection not in search_labels:
            search_selection = None
            st.session_state["map_search_selected"] = None
        selected_map_search = next(
            (item for item in map_search_catalog if item["label"] == search_selection), None
        )
        map_extent = st.session_state["map_extent"]
        show_roads = bool(st.session_state["show_roads"])
        show_hazard = bool(st.session_state["show_hazard_v2"])
        st.session_state.setdefault("evacuation_movement_enabled_v2", True)
        animate_evacuation_groups = bool(
            st.session_state.get("evacuation_movement_enabled_v2", True)
            and group_route_assignments
        )
        show_boundaries = bool(st.session_state["show_boundaries_v2"])
        show_synthetic_zones = bool(st.session_state["show_origins_v2"])
        map_selection_mode = st.session_state["map_point_type"]
        pick_destination_on_map = bool(st.session_state["pick_destination_on_map"])
        staged_destination = st.session_state.get("candidate_destination_node_id")
        selected_destination_node_id = st.session_state.get("candidate_destination_node_id")

        try:
            fig = go.Figure()
            if show_hazard:
                depth_colors = {
                    "< 1 meter": ("#d6b76c", "#8f7842"),
                    "1 to 1.99 meters": ("#df263e", "#922032"),
                    "2 to 2.99 meters": ("#20a6dc", "#116184"),
                    "3 to 3.99 meters": ("#7dbd59", "#426b32"),
                    "4 to 4.99 meters": ("#47d49a", "#1a805a"),
                    "5 to 6 meters": ("#d76bd8", "#813c83"),
                }
                for feature in active_hazard_features:
                    depth = feature["properties"].get("Inun_depth", "Depth not classified")
                    fill, outline = depth_colors.get(depth, ("#7c3aed", "#4c1d95"))
                    add_polygon_layer(
                        fig, [feature], fill, outline, f"Mapped depth · {depth}",
                        True, 0.45,
                    )
            if show_roads:
                add_road_layer(fig, map_data["road_edges"], map_data["road_nodes"], road_bbox_for_extent(map_extent))
            if show_boundaries:
                if map_extent == "Gubat":
                    add_boundary_layer(fig, map_data["gubat_boundary"], "#111827", "Gubat boundary")
                else:
                    add_boundary_layer(fig, map_data["daet_boundary"], "#334155", "Daet boundary")
                    if map_extent == "Daet–Basud":
                        add_boundary_layer(fig, map_data["regional_boundary"], "#0f172a", "Daet–Basud extent")
                    else:
                        add_boundary_layer(fig, map_data["gubat_boundary"], "#111827", "Gubat boundary")
            routed_pin_indices = set()
            for assignment in route_assignments:
                route_node_coordinates = [map_node_lookup.loc[node_id] for node_id in assignment["nodes"]]
                pin_index = destination_node_ids.index(assignment["destination_node_id"]) + 1
                routed_pin_indices.add(pin_index)
                pin_color = destination_pin_colors[(pin_index - 1) % len(destination_pin_colors)]
                fig.add_trace(go.Scattermapbox(
                    lon=[float(row["lon"]) for row in route_node_coordinates],
                    lat=[float(row["lat"]) for row in route_node_coordinates],
                    mode="lines",
                    line={"color": pin_color, "width": 5},
                    name=f"Candidate route · {assignment['origin']} → Pin {pin_index}",
                    hoverinfo="skip",
                ))
            for pair in pin_pair_routes:
                if not pair["nodes"]:
                    continue
                pair_coordinates = [map_node_lookup.loc[node_id] for node_id in pair["nodes"]]
                pair_lon = [float(row["lon"]) for row in pair_coordinates]
                pair_lat = [float(row["lat"]) for row in pair_coordinates]
                # Layer a white casing under the teal road path so the pin link
                # stays visible over roads, route lines, and depth polygons.
                fig.add_trace(go.Scattermapbox(
                    lon=pair_lon, lat=pair_lat, mode="lines",
                    line={"color": "#ffffff", "width": 12},
                    name=f"Pin connection outline · {pair['Pin pair']}",
                    hoverinfo="skip",
                ))
                fig.add_trace(go.Scattermapbox(
                    lon=pair_lon, lat=pair_lat, mode="lines",
                    line={"color": "#00a6a6", "width": 7},
                    name=f"Connected road path · {pair['Pin pair']}",
                    hovertemplate=(
                        f"{pair['Pin pair']} · connected in filtered road graph<br>"
                        f"{pair['Road path (km)']} km · {pair['Modeled walk time (min)']} min"
                        "<extra></extra>"
                    ),
                ))
            if pick_destination_on_map:
                min_lon, min_lat, max_lon, max_lat = road_bbox_for_extent(map_extent)
                selectable_nodes = map_data["road_nodes"].loc[
                    (map_data["road_nodes"]["lon"] >= min_lon)
                    & (map_data["road_nodes"]["lon"] <= max_lon)
                    & (map_data["road_nodes"]["lat"] >= min_lat)
                    & (map_data["road_nodes"]["lat"] <= max_lat)
                ].copy()
                selectable_nodes["node_id"] = selectable_nodes["node_id"].astype(str)
                selectable_nodes["component_vertices"] = selectable_nodes["node_id"].map(
                    lambda node: component_size_for_node.get(node, 0)
                )
                selection_kind = "CANDIDATE_ORIGIN_NODE" if map_selection_mode == "Origin area" else "CANDIDATE_DESTINATION_NODE"
                selection_label = "origin-area representative node" if map_selection_mode == "Origin area" else "candidate receiving pin"
                fig.add_trace(go.Scattermapbox(
                    lon=selectable_nodes["lon"],
                    lat=selectable_nodes["lat"],
                    mode="markers",
                    marker={"size": 7, "color": "#0f766e", "opacity": 0.35},
                    customdata=[[selection_kind, row.node_id, row.component_vertices]
                                for row in selectable_nodes.itertuples(index=False)],
                    name=f"Click a road node to set {selection_label}",
                    hovertemplate=("Candidate road node<br>ID: %{customdata[1]}<br>"
                                   "Raw component vertices: %{customdata[2]}<br>"
                                   f"Click to select as a scenario {selection_label}<extra></extra>"),
                    selected={"marker": {"color": "#0f766e", "opacity": 1, "size": 12}},
                    unselected={"marker": {"opacity": 0.25}},
                ))
            if destination_node_ids:
                committed_destination_rows = [map_node_lookup.loc[node_id] for node_id in destination_node_ids]
                fig.add_trace(go.Scattermapbox(
                    lon=[float(row["lon"]) for row in committed_destination_rows],
                    lat=[float(row["lat"]) for row in committed_destination_rows],
                    mode="markers",
                    marker={"size": 28, "color": "#ffffff", "opacity": 0.98, "symbol": "circle"},
                    name="Receiving pin highlight",
                    hoverinfo="skip",
                ))
                for pin_index, node_id in enumerate(destination_node_ids, start=1):
                    pin_row = map_node_lookup.loc[node_id]
                    pin_color = destination_pin_colors[(pin_index - 1) % len(destination_pin_colors)]
                    fig.add_trace(go.Scattermapbox(
                        lon=[float(pin_row["lon"])],
                        lat=[float(pin_row["lat"])],
                        mode="markers+text",
                        text=[f"Pin {pin_index}"],
                        textposition="top center",
                        marker={"size": 20, "color": pin_color, "symbol": "circle"},
                        name=f"Candidate receiving pin {pin_index}",
                        customdata=[[node_id]],
                        hovertemplate=(
                            f"Pin {pin_index}<br>Road node: %{{customdata[0]}}<br>"
                            "Not a verified safe site<extra></extra>"
                        ),
                    ))
            pending_origin_node_id = st.session_state.get("pending_origin_node_id")
            if pending_origin_node_id in map_node_lookup.index:
                pending_origin = map_node_lookup.loc[pending_origin_node_id]
                fig.add_trace(go.Scattermapbox(
                    lon=[float(pending_origin["lon"])], lat=[float(pending_origin["lat"])],
                    mode="markers+text", text=["New origin anchor"], textposition="bottom center",
                    marker={"size": 15, "color": "#9333ea", "symbol": "circle"},
                    name="User-selected origin road node",
                    customdata=[[pending_origin_node_id]],
                    hovertemplate="User-selected candidate origin node<br>%{customdata[0]}<br>Not a mapped neighborhood boundary<extra></extra>",
                ))
            if show_synthetic_zones:
                if map_extent == "Daet–Basud" and show_boundaries:
                    add_boundary_layer(fig, map_data["gubat_boundary"], "#111827", "Gubat boundary")
                active_zone_summary = zone_summary.loc[zone_summary["people"] > 0].copy()
                max_zone_people = max(int(active_zone_summary["people"].max()), 1)
                fig.add_trace(go.Scattermapbox(
                    lon=[coordinate for pair in zip(active_zone_summary["lon"], active_zone_summary["road_lon"]) for coordinate in (pair[0], pair[1], None)],
                    lat=[coordinate for pair in zip(active_zone_summary["lat"], active_zone_summary["road_lat"]) for coordinate in (pair[0], pair[1], None)],
                    mode="lines", line={"color": "#2563eb", "width": 1},
                    name="Anchor offset · not a route", hoverinfo="skip",
                ))
                fig.add_trace(go.Scattermapbox(
                    lon=active_zone_summary["lon"], lat=active_zone_summary["lat"], mode="markers+text",
                    text=active_zone_summary["map_label"], textposition="top center",
                    marker={"size": [12 + 18 * int(value) / max_zone_people for value in active_zone_summary["people"]], "color": "#f59e0b", "opacity": 0.9, "symbol": "circle"},
                    name="Named-area origin anchors",
                    customdata=active_zone_summary[["zone_id", "zone_name", "people", "groups", "simulated_share_pct"]].to_numpy(),
                    hovertemplate=("%{customdata[1]}<br>Origin ID: %{customdata[0]}<br>"
                                   "Synthetic people: %{customdata[2]}<br>Synthetic groups: %{customdata[3]}<br>"
                                   "Scenario share: %{customdata[4]}%<br>Named-place anchor; no household locations<extra></extra>"),
                ))
                fig.add_trace(go.Scattermapbox(
                    lon=active_zone_summary["road_lon"], lat=active_zone_summary["road_lat"], mode="markers",
                    marker={"size": [10 + 14 * int(value) / max_zone_people for value in active_zone_summary["people"]], "color": "#2563eb", "symbol": "circle", "opacity": 0.95},
                    name="Scenario groups · candidate road nodes",
                    customdata=active_zone_summary[["zone_name", "candidate_road_name", "road_node_id", "people", "groups", "anchor_to_road_m", "road_access_status"]].to_numpy(),
                    hovertemplate=("%{customdata[0]}<br>Mapped road/path: %{customdata[1]}<br>Candidate graph node: %{customdata[2]}<br>"
                                   "Synthetic people: %{customdata[3]}<br>Synthetic groups: %{customdata[4]}<br>"
                                   "Anchor offset: %{customdata[5]} m<br>%{customdata[6]}<extra></extra>"),
                ))
            if selected_map_search:
                fig.add_trace(go.Scattermapbox(
                    lon=[selected_map_search["lon"]],
                    lat=[selected_map_search["lat"]],
                    mode="markers+text",
                    text=[selected_map_search["name"]],
                    textposition="top center",
                    marker={"size": 18, "color": "#7c3aed", "symbol": "circle"},
                    name="Search result",
                    customdata=[[selected_map_search["kind"], selected_map_search["name"]]],
                    hovertemplate="%{customdata[0]} · %{customdata[1]}<br>Approximate search location<extra></extra>",
                ))
            centers = {
                "Gubat": {"lon": 122.975, "lat": 14.118},
                "Daet": {"lon": 122.944, "lat": 14.109},
                "Daet–Basud": {"lon": 122.973, "lat": 14.025},
            }
            zoom_levels = {"Gubat": 13.0, "Daet": 10.5, "Daet–Basud": 9.2}
            map_center = (
                {"lon": selected_map_search["lon"], "lat": selected_map_search["lat"]}
                if selected_map_search else centers[map_extent]
            )
            map_zoom = 16.0 if selected_map_search else zoom_levels[map_extent]
            fig.update_layout(
                height=480, margin={"l": 0, "r": 0, "t": 0, "b": 0}, showlegend=False,
                mapbox={"style": "open-street-map", "center": map_center, "zoom": map_zoom},
                clickmode="event+select",
                uirevision=f"scenario-map-{map_extent}-{selected_map_search['label'] if selected_map_search else 'default'}",
            )
            animated_group_count = 0
            if animate_evacuation_groups:
                animated_group_count = add_evacuation_movement_animation(
                    fig, group_route_assignments, map_node_lookup, routing_graph,
                    destination_node_ids, 1.15 * float(speed_scale),
                )
            st.plotly_chart(
                fig,
                use_container_width=True,
                config={"scrollZoom": True},
                key="scenario_geographic_map",
                on_select=remember_map_point_selection,
                selection_mode="points",
            )
            legend_items = []
            if show_hazard:
                for label, (fill, _) in depth_colors.items():
                    legend_items.append(f'<span class="map-legend-item"><i class="map-legend-swatch" style="background:{fill}"></i>Inundation · {label}</span>')
            if show_roads:
                road_legend = [("#64748b", "service"), ("#f97316", "secondary"), ("#64748b", "residential"),
                               ("#94a3b8", "unclassified"), ("#f59e0b", "tertiary"), ("#14b8a6", "footway"), ("#65a30d", "track")]
                legend_items.extend(f'<span class="map-legend-item"><i class="map-legend-line" style="border-color:{color}"></i>Road · {label}</span>' for color, label in road_legend)
            if show_boundaries:
                legend_items.append('<span class="map-legend-item"><i class="map-legend-line" style="border-color:#111827;border-top-width:3px"></i>Boundary</span>')
            if route_assignments:
                for pin_index in sorted(routed_pin_indices):
                    pin_color = destination_pin_colors[(pin_index - 1) % len(destination_pin_colors)]
                    legend_items.append(
                        f'<span class="map-legend-item"><i class="map-legend-line" style="border-color:{pin_color};border-top-width:4px"></i>Routes to pin {pin_index} · unverified</span>'
                    )
            if any(pair["nodes"] for pair in pin_pair_routes):
                legend_items.append('<span class="map-legend-item"><i class="map-legend-line" style="border-color:#00a6a6;border-top-width:5px"></i>Connected road path between pins · graph screen</span>')
            if pick_destination_on_map:
                selectable_label = "Selectable origin road node" if map_selection_mode == "Origin area" else "Selectable receiving-point node"
                legend_items.append(f'<span class="map-legend-item"><i class="map-legend-dot" style="background:#0f766e"></i>{selectable_label}</span>')
            if destination_node_ids:
                for pin_index, _ in enumerate(destination_node_ids, start=1):
                    pin_color = destination_pin_colors[(pin_index - 1) % len(destination_pin_colors)]
                    legend_items.append(
                        f'<span class="map-legend-item"><i class="map-legend-dot" style="background:{pin_color}"></i>Receiving pin {pin_index}</span>'
                    )
            if st.session_state.get("pending_origin_node_id"):
                legend_items.append('<span class="map-legend-item"><i class="map-legend-dot" style="background:#9333ea"></i>Staged origin anchor</span>')
            if show_synthetic_zones:
                legend_items.extend([
                    '<span class="map-legend-item"><i class="map-legend-line" style="border-color:#2563eb"></i>Anchor offset · not a route</span>',
                    '<span class="map-legend-item"><i class="map-legend-dot" style="background:#f59e0b"></i>Named-area origin anchor</span>',
                    '<span class="map-legend-item"><i class="map-legend-dot" style="background:#2563eb"></i>Candidate road node · size shows group total</span>',
                ])
            if animate_evacuation_groups and animated_group_count:
                legend_items.append(
                    '<span class="map-legend-item"><i class="map-legend-dot" style="background:linear-gradient(90deg,#7c3aed,#f97316,#06b6d4,#e11d48)"></i>Moving synthetic group · color identifies receiving pin</span>'
                )
            st.markdown('<div class="map-legend">' + ''.join(legend_items) + '</div>', unsafe_allow_html=True)
            st.toggle(
                "Animate assigned evacuation groups",
                key="evacuation_movement_enabled_v2",
                disabled=not bool(group_route_assignments),
                help="Plays anonymous synthetic groups along their assigned shortest free-flow road-graph paths. This is separate from tsunami playback.",
            )
            if not group_route_assignments:
                st.caption("Add connected receiving pins, positive pin limits, and origin-to-pin shares to create assigned groups for playback.")
            elif animate_evacuation_groups:
                st.caption(
                    f"Evacuation movement preview · {animated_group_count:,} of {len(synthetic_groups):,} generated groups have assigned paths. "
                    "Dots start at representative origin road nodes; size represents group size and color matches the receiving pin. "
                    "Playback time is an assumed free-flow estimate. It does not model actual household locations, congestion, individual movement, road safety, or tsunami arrival. Unassigned groups do not move."
                )
            shared_component_zones = max(len(zone_summary) - zone_summary["shares_candidate_component_with"].eq("No other included origin candidate").sum(), 0)
            st.caption(
                f"OSM © OpenStreetMap contributors · pan/zoom enabled · raw graph screen: {shared_component_zones}/{len(zone_summary)} "
                f"origin candidates share a geometry component. A plotted shortest-distance path uses a uniform assumed walking speed and unreviewed graph geometry; it is not a safe-route recommendation."
            )
        except Exception as exc:
            st.error(f"Could not load the geographic map layers: {exc}")

        with st.container(border=True):
            st.caption("Research prototype · map-selected routes are screening estimates on an unreviewed OSM graph; tsunami depths are static. Not for emergency guidance.")
            search_cols = st.columns([2.1, 3.9])
            search_cols[0].text_input(
                "Find a building, road, or street",
                key="map_search_query",
                placeholder="Type at least 2 characters",
                on_change=clear_map_search_selection,
            )
            search_cols[1].selectbox(
                "Search results",
                options=search_labels,
                index=None,
                placeholder="Choose a matching map feature",
                key="map_search_selected",
                disabled=not search_matches,
                on_change=apply_map_search_selection,
                help="Type at least two characters, then choose a matching named OpenStreetMap feature. Unnamed buildings and roads are not searchable.",
            )
            if len(map_search_query.strip()) >= 2 and not search_matches:
                search_cols[1].caption("No named map features match that text in the included data.")
            control_cols = st.columns([3.5, 1.05, 1.2, 1.0, 1.45])
            control_cols[0].radio("Map extent", ["Gubat", "Daet", "Daet–Basud"], horizontal=True, key="map_extent")
            control_cols[1].checkbox("OSM roads", key="show_roads")
            control_cols[2].checkbox("Depth zones", key="show_hazard_v2")
            control_cols[3].checkbox("Boundaries", key="show_boundaries_v2")
            control_cols[4].checkbox("Named origins", key="show_origins_v2")
            route_control_cols = st.columns([2.2, 2.0, 1.6, 1.4, 3.5])
            route_control_cols[0].selectbox("Map point type", ["Receiving pin", "Origin area"], key="map_point_type")
            route_control_cols[1].toggle(
                "Pick a road point",
                key="pick_destination_on_map",
                help="Click a teal mapped road node. Add it as a receiving pin, or use it to define an aggregate origin area.",
            )
            if route_control_cols[2].button(
                "Add selected pin", key="add_candidate_destination",
                disabled=not staged_destination or map_selection_mode != "Receiving pin",
            ):
                pins = list(st.session_state.get("candidate_destination_node_ids", []))
                if staged_destination not in pins:
                    pins.append(staged_destination)
                st.session_state["candidate_destination_node_ids"] = pins
                st.rerun()
            if route_control_cols[3].button("Clear pins", key="clear_candidate_destinations"):
                st.session_state["candidate_destination_node_ids"] = []
                st.session_state.pop("candidate_destination_node_id", None)
                st.rerun()
            route_control_cols[4].caption("Pins and origin anchors are scenario inputs—not verified safe or available sites.")
            if pick_destination_on_map:
                if map_selection_mode == "Receiving pin":
                    st.info("Click a teal road-node dot, then choose **Add selected pin**. Repeat to add more than one candidate receiving point.")
                else:
                    st.info("Click a teal road-node dot for the aggregate origin's representative access point. Then name it in the left sidebar under **Add a named origin area**.")

        with st.container(border=True):
            st.markdown("### Tsunami map preview")
            st.caption(
                "Mapped maximum-inundation depth is shown statically. The Daet extent uses the full area of the bundled client layer; "
                "areas outside its polygons are unclassified, not evidence of zero tsunami risk. A shoreline-to-inland animation needs "
                "validated arrival-time or time-step data and is not inferred from these depth classes."
            )
            if animate_evacuation_groups:
                st.info("The evacuation group playback shows people moving along assigned candidate routes; the mapped tsunami depth remains static.")

        with st.container(border=True):
            st.markdown("### Time-dependent tsunami simulation")
            sim_controls = st.columns([2.3, 1.0, 1.0, 1.0, 1.25])
            scenario_by_id = {item["scenario_id"]: item for item in tsunami_scenarios}
            if tsunami_scenarios:
                selected_tsunami_scenario_id = sim_controls[0].selectbox(
                    "Tsunami scenario / intensity",
                    options=list(scenario_by_id),
                    format_func=lambda scenario_id: scenario_by_id[scenario_id]["scenario_name"],
                    key="selected_tsunami_scenario_id",
                    help="Each choice is a documented model scenario, not a free-form intensity estimate.",
                )
            else:
                selected_tsunami_scenario_id = None
                sim_controls[0].selectbox(
                    "Tsunami scenario / intensity",
                    ["No validated time-dependent scenario"],
                    disabled=True,
                    help="Intensity must come from a documented, sourced tsunami scenario; it cannot be inferred from the static maximum-inundation polygons.",
                )
            simulation_can_start = bool(
                tsunami_time_series_available
                and tsunami_playback_engine_available
                and not simulation_setup_issues
                and selected_tsunami_scenario_id
            )
            sim_controls[1].button(
                "▶ Start simulation", key="start_tsunami_simulation", disabled=not simulation_can_start,
                help="Playback unlocks after a reviewed time-dependent scenario and the simulation engine are available.",
                use_container_width=True,
            )
            sim_controls[2].button("Ⅱ Pause", key="pause_tsunami_simulation", disabled=True, use_container_width=True)
            sim_controls[3].button("↺ Restart", key="restart_tsunami_simulation", disabled=True, use_container_width=True)
            sim_controls[4].metric("Simulation time", "00:00:00")
            st.progress(0, text="Simulation timeline · inactive")
            if not tsunami_time_series_available:
                st.caption(
                    "🔒 The project has static maximum-inundation depth polygons, but no validated time-dependent tsunami scenario. "
                    + (tsunami_scenario_issues[0] if tsunami_scenario_issues else "Add sourced model frames before animating water.")
                )
            elif not tsunami_playback_engine_available:
                st.caption("Scenario frames pass intake validation, but the playback engine is the next implementation step.")
            if simulation_setup_issues:
                st.caption("Scenario setup still needs: " + "; ".join(simulation_setup_issues) + ".")
            elif tsunami_scenarios:
                st.caption("Evacuation inputs pass the current setup checks.")

with details_col:
    if details_open:
        heading_col, collapse_col = st.columns([5, 1])
        heading_col.markdown("### Explore details")
        if collapse_col.button("‹", key="collapse_explore_details", help="Collapse details sideways"):
            st.session_state["explore_details_open"] = False
            st.rerun()
        with st.container(height=620, key="details_panel"):
            detail_tabs = st.tabs(["Overview", "Origin groups", "Pin route", "Route demo", "Sources & limits", "Road coverage", "Printable map"])

            with detail_tabs[0]:
                st.markdown("### Scenario interpretation")
                st.warning("The map routes are an unreviewed screening preview. R1–R12 still drive the separate schematic demo tables. User-created origin anchors are session-only road-node representatives, not mapped neighborhood boundaries.")
                st.markdown("**Map key**")
                st.write("🟠 Named residential-area reference point")
                st.write("🔵 Candidate OSM graph entry node; size reflects synthetic group totals")
                st.write("🔹 Short connector shows anchor offset only, not a walking route")
                st.caption("The tsunami polygons are static depth classes; no moving-water timeline is available.")

            with detail_tabs[1]:
                st.markdown("### Synthetic origin groups")
                st.warning(
                    f"Scenario assumption: selected origin amounts total {scenario_people_total:,} people under the user-set run cap of {int(scenario_people_limit):,}. "
                    f"The only current source aggregate is {gubat_population_total:,} for Gubat; any wider-area counts or finer-area splits are user assumptions until approved totals are supplied. No household locations are generated."
                )
                st.metric("Groups generated", f"{len(synthetic_groups):,}")
                st.metric("People in this run", f"{int(synthetic_groups['group_size'].sum()):,}")
                st.metric("Origin areas with evacuees", f"{int((zone_summary['people'] > 0).sum()):,}")
                st.metric("Repeatable seed", f"{int(random_seed)}")
                st.caption(
                    f"Departure draws: 0–{departure_window_min} minutes; typical groups 5–10; small-party assumption 2–3 "
                    f"({small_party_share_pct}% of draws). Group sizes and departure times are synthetic assumptions."
                )
                st.bar_chart(departure_counts.set_index("departure_minute"), y="people_departing", height=180)
                st.markdown("**Scenario evacuees by selected origin area**")
                st.dataframe(zone_summary[["zone_name", "groups", "people", "simulated_share_pct"]], use_container_width=True, hide_index=True)
                st.markdown("**Candidate graph entry points**")
                st.dataframe(
                    zone_summary[["zone_name", "candidate_road_name", "road_node_id", "anchor_to_road_m", "graph_component_vertices", "shares_candidate_component_with", "road_access_status"]],
                    use_container_width=True, hide_index=True,
                )
                with st.expander("Preview anonymous groups"):
                    st.dataframe(synthetic_groups.head(25), use_container_width=True, hide_index=True)
                    st.caption("No household locations or individual map points are included.")
                st.download_button(
                    "Download group run (CSV)", data=synthetic_groups.to_csv(index=False).encode("utf-8"),
                    file_name=f"synthetic_scenario_groups_seed_{int(random_seed)}.csv", mime="text/csv",
                )

            with detail_tabs[2]:
                st.markdown("### Origins routed to selected candidate pins")
                st.caption("Set a receiving limit for each pin below. Origin-to-pin shares are set in the left scenario sidebar. Whole groups are routed in departure order toward those shares, subject to graph connectivity and remaining pin capacity.")
                assigned_group_count = len(group_route_assignments)
                assigned_people_total = sum(int(group["group_size"]) for group in group_route_assignments)
                unassigned_group_count = sum(int(counts["groups"]) for counts in unassigned_by_origin.values())
                unassigned_people_total = sum(
                    int(counts["network"] + counts["capacity"] + counts["allocation"] + counts["invalid"])
                    for counts in unassigned_by_origin.values()
                )
                arrived_by_checkpoint = [
                    group for group in group_route_assignments
                    if float(group["arrival_min"]) <= float(planning_window)
                ]
                remaining_at_checkpoint = [
                    group for group in group_route_assignments
                    if float(group["arrival_min"]) > float(planning_window)
                ]
                checkpoint_people = sum(int(group["group_size"]) for group in arrived_by_checkpoint)
                remaining_checkpoint_people = sum(int(group["group_size"]) for group in remaining_at_checkpoint)
                last_assigned_arrival = max(
                    (float(group["arrival_min"]) for group in group_route_assignments), default=None
                )
                st.markdown("#### Scenario completion summary")
                summary_cols_top = st.columns(2)
                summary_cols_bottom = st.columns(2)
                summary_cols_top[0].metric(
                    f"Estimated at candidate pins by {planning_window} min",
                    f"{checkpoint_people:,} people",
                    f"{len(arrived_by_checkpoint):,} of {len(synthetic_groups):,} groups",
                )
                summary_cols_top[1].metric(
                    "Last assigned group arrival",
                    f"{last_assigned_arrival:.1f} min" if last_assigned_arrival is not None else "No assigned route",
                    f"{assigned_people_total:,} people · {assigned_group_count:,} groups assigned",
                )
                summary_cols_bottom[0].metric(
                    f"Still en route at {planning_window} min",
                    f"{remaining_checkpoint_people:,} people",
                    f"{len(remaining_at_checkpoint):,} groups",
                )
                summary_cols_bottom[1].metric(
                    "Not assigned to a pin",
                    f"{unassigned_people_total:,} people",
                    f"{unassigned_group_count:,} groups",
                )
                st.warning(
                    "These are estimated arrivals at user-selected candidate points using assumed departures and uniform free-flow walking speed. "
                    "They are not confirmed safe evacuations: the receiving sites are unverified, and these times are not compared with tsunami arrival."
                )
                if group_route_assignments:
                    arrival_events = pd.DataFrame([
                        {
                            "minute": max(0, math.ceil(float(group["arrival_min"]))),
                            "people": int(group["group_size"]),
                        }
                        for group in group_route_assignments
                    ]).groupby("minute", as_index=True)["people"].sum()
                    chart_end_minute = max(int(arrival_events.index.max()), int(planning_window))
                    arrival_curve = arrival_events.reindex(range(chart_end_minute + 1), fill_value=0).cumsum()
                    with st.expander("Estimated arrivals over time", expanded=False):
                        st.area_chart(arrival_curve, height=180)
                        st.caption("Cumulative people by whole model minute. This chart shows route-model estimates, not tsunami timing or safety.")
                else:
                    st.info("No groups have assigned routes yet. Add connected candidate pins, enter positive pin limits, and allocate origin shares to see an outcome summary.")
                if not destination_node_ids:
                    st.info("No candidate receiving pins yet. Turn on **Pick a road point**, select a teal node, then click **Add selected pin**. Repeat for additional destinations.")
                else:
                    st.write(f"Selected candidate receiving points: **{len(destination_node_ids)}**")
                    st.markdown("**Maximum evacuees each candidate pin can receive**")
                    st.caption("Enter each location's assumed scenario capacity. These limits are user assumptions; none of the pins is a confirmed shelter or approved safe area.")
                    for pin_index, node_id in enumerate(destination_node_ids, start=1):
                        capacity_key = f"receiving_capacity_{node_id}"
                        if capacity_key not in st.session_state:
                            st.session_state[capacity_key] = 0
                        if int(st.session_state[capacity_key]) > int(scenario_people_limit):
                            st.session_state[capacity_key] = int(scenario_people_limit)
                        pin_location = map_node_lookup.loc[node_id]
                        st.caption(f"Pin {pin_index} · road node `{node_id}` · {float(pin_location['lat']):.5f}, {float(pin_location['lon']):.5f}")
                        st.number_input(
                            f"Candidate pin {pin_index} · maximum evacuees",
                            min_value=0, max_value=int(scenario_people_limit), step=50,
                            key=capacity_key,
                            help="Scenario capacity only. Confirm the site's permission, usable space, access, and capacity locally before treating it as a real receiving area.",
                        )
                    st.markdown("**Capacity used in this scenario**")
                    st.dataframe(
                        pd.DataFrame(destination_capacity_summary)[[
                            "Candidate pin", "Capacity entered", "People assigned",
                            "Capacity remaining", "Capacity used (%)",
                        ]],
                        use_container_width=True,
                        hide_index=True,
                    )
                    if pin_pair_routes:
                        st.markdown("**Pin-to-pin road connection**")
                        st.dataframe(
                            pd.DataFrame(pin_pair_routes)[[
                                "Pin pair", "Filtered graph connection", "Road path (km)", "Modeled walk time (min)"
                            ]],
                            use_container_width=True,
                            hide_index=True,
                        )
                        if any(pair["nodes"] for pair in pin_pair_routes):
                            st.caption(
                                "The teal line follows the shortest-distance path in the filtered OSM graph. "
                                "All links use one uniform assumed walking speed, so the speed control changes the time estimate, not the chosen path. "
                                "Missing access tags are treated as candidate links. Connectivity is not a reviewed or safe route."
                            )
                        else:
                            st.warning("No selected pins are connected in the current filtered road graph, so no connecting line is drawn.")
                    if origin_pin_connectivity_rows:
                        st.markdown("**Origin-to-pin connectivity and planned shares**")
                        st.dataframe(
                            pd.DataFrame(origin_pin_connectivity_rows)[[
                                "Origin area", "Candidate pin", "Planned share (%)", "Connectivity",
                            ]],
                            use_container_width=True,
                            hide_index=True,
                        )
                        disconnected_rows = [
                            row for row in origin_pin_connectivity_rows
                            if row["Connectivity"] == "Not connected in filtered graph"
                            and row["Closest graph-node gap (m)"] is not None
                        ]
                        if disconnected_rows:
                            st.markdown("**Disconnected pairs · nearest mapped endpoints for review**")
                            st.dataframe(pd.DataFrame(disconnected_rows)[[
                                "Origin area", "Candidate pin", "Closest graph-node gap (m)",
                                "Closest origin-side node ID", "Closest origin-side node", "Origin-side mapped road(s)",
                                "Closest pin-side node ID", "Closest pin-side node", "Pin-side mapped road(s)",
                            ]], use_container_width=True, hide_index=True)
                        st.caption(
                            "A planned share is only allocatable when the origin and pin are connected in the filtered graph. "
                            "Nearest endpoints and gaps are screening diagnostics to locate a review area; they do not establish a real-world road connection or route safety."
                        )
                    if route_assignments:
                        assigned_people = sum(item["people"] for item in route_assignments)
                        assigned_groups = sum(item["groups"] for item in route_assignments)
                        st.success(f"Assigned {assigned_people:,} people in {assigned_groups:,} groups across the candidate paths.")
                        route_table = pd.DataFrame([{
                            "Origin area": item["origin"],
                            "People assigned": item["people"],
                            "Groups": item["groups"],
                            "Assigned candidate pin": destination_node_ids.index(item["destination_node_id"]) + 1,
                            "Configured origin share (%)": int(origin_pin_shares.get(item["zone_id"], {}).get(item["destination_node_id"], 0)),
                            "Actual origin share (%)": round(item["people"] / max(int(zone_summary.loc[zone_summary["zone_id"].astype(str) == item["zone_id"], "people"].iloc[0]), 1) * 100, 1),
                            "Estimated walk time (min)": round(item["time_min"], 1),
                            "Path length (km)": round(item["length_m"] / 1000, 2),
                            "OSM road names": "; ".join(item["named_roads"]) or "No names recorded",
                        } for item in route_assignments])
                        st.dataframe(route_table, use_container_width=True, hide_index=True)
                        hazard_rows = [
                            {"Origin area": item["origin"], "Candidate pin": destination_node_ids.index(item["destination_node_id"]) + 1,
                             "Static depth class": depth_class, "Sampled path length in polygon (m)": round(distance_m, 1)}
                            for item in route_assignments
                            for depth_class, distance_m in sorted(item["hazard_overlap_m_by_class"].items())
                        ]
                        st.markdown("**Approximate overlap with static inundation classes**")
                        if hazard_rows:
                            st.dataframe(pd.DataFrame(hazard_rows), use_container_width=True, hide_index=True)
                        else:
                            st.info("No sampled overlap with the available static inundation polygons was found on these paths.")
                    if unrouted_origins:
                        st.warning("Some synthetic groups remain unassigned. The breakdown below separates graph disconnection, pin capacity, planned-share limits, and invalid shares.")
                        st.dataframe(
                            pd.DataFrame(unrouted_origins)[[
                                "Origin area", "People not assigned", "No connected pin",
                                "Pin capacity reached", "Share target reached", "Invalid shares",
                            ]],
                            use_container_width=True,
                            hide_index=True,
                        )
                        st.caption("Component IDs, node counts, and closest node gaps describe the exported graph only. They are review leads and do not identify a safe shortcut or justify drawing a connector.")
                    if selected_destination_node_id and selected_destination_node_id not in destination_node_ids:
                        st.caption("A road node is staged on the map but has not been added to the receiving-points list yet.")
                    st.caption("Entered destination limits are total scenario headcounts, not throughput rates. Path/hazard overlap uses approximate 5 m map samples and does not estimate tsunami arrival, changing road depth, congestion, road capacity, or route safety.")

            with detail_tabs[3]:
                st.markdown("### Schematic route demo")
                st.warning("These outputs still come from the sample R1–R12 network, not the geographic roads on the map.")
                st.metric("Demo population", f"{result['total_population']:,}")
                st.metric("Demo completion estimate", f"{result['completion_min']:.1f} min")
                st.metric(f"Demo within {planning_window} min", f"{result['within_window']:,}")
                with st.expander("Show sample route graph"):
                    st.caption("Illustrative node positions; not local streets or recommended routes.")
                    coords = node_coordinate_lookup(inputs["nodes"])
                    route_fig = go.Figure()
                    for row in result["edges"].to_dict("records"):
                        x1, y1 = coords[str(row["from_node"])]
                        x2, y2 = coords[str(row["to_node"])]
                        is_closed = row["closed"]
                        load = float(row["load_ratio"])
                        color = "#98a2b3" if is_closed else ("#dc2626" if load >= 1 else "#167d74")
                        route_fig.add_trace(go.Scatter(
                            x=[x1, x2], y=[y1, y2], mode="lines",
                            line={"width": 2 + min(float(row["people"]) / 120, 7), "color": color, "dash": "dash" if is_closed else "solid"},
                            hovertemplate=(f"Sample segment {row['edge_id']}<br>Assigned: {row['people']} people<br>"
                                           f"Capacity: {row['capacity']:.0f} people/min<br>Estimated queue: {row['queue_min']:.1f} min<extra></extra>"),
                            showlegend=False,
                        ))
                    node_rows = inputs["nodes"].to_dict("records")
                    route_fig.add_trace(go.Scatter(
                        x=[float(row["x"]) for row in node_rows], y=[float(row["y"]) for row in node_rows],
                        mode="markers+text", text=[str(row["name"]) for row in node_rows], textposition="top center",
                        marker={"size": 10, "color": ["#2b6cb0" if str(row["node_id"]).startswith("O") else "#7c3aed" if str(row["node_id"]).startswith("S") else "#475467" for row in node_rows]},
                        customdata=[str(row["node_id"]) for row in node_rows], hovertemplate="%{text}<br>ID: %{customdata}<extra></extra>",
                        showlegend=False,
                    ))
                    route_fig.update_layout(height=300, margin={"l": 5, "r": 5, "t": 5, "b": 5}, xaxis={"visible": False}, yaxis={"visible": False, "scaleanchor": "x", "scaleratio": 1}, plot_bgcolor="#f6f8fa")
                    st.plotly_chart(route_fig, use_container_width=True)
                st.markdown("**Route assignments**")
                st.dataframe(result["assignments"], use_container_width=True, hide_index=True)
                st.markdown("**Demo destination capacity**")
                st.dataframe(result["shelters"], use_container_width=True, hide_index=True)
                st.caption("Assignments use shortest free-flow paths in the sample graph; capacity figures are illustrative.")

            with detail_tabs[4]:
                st.markdown("### Data sources")
                st.dataframe(inputs["data_sources"], use_container_width=True, hide_index=True)
                st.markdown("### Tsunami hazard layer used by the map")
                st.write(
                    "Gubat uses `data/gubat_tsunami_clip_fixed.gpkg`, clipped to the traced Gubat boundary. "
                    "Daet uses `data/daet_tsunami_inundation.gpkg`, converted from the complete bundled "
                    "client shapefile `tsunamishp/tsunami.shp`. The Daet layer has six `Inun_depth` classes "
                    "from < 1 meter through 5 to 6 meters in WGS 84 (EPSG:4326). The source polygons cover "
                    "only part of Daet, mainly the coastal/eastern area; the map keeps the full Daet boundary "
                    "visible, but does not paint inland areas outside the source polygons as inundated."
                )
                st.warning(
                    "The shapefile's issuing organization, product date/version, and reuse terms are not "
                    "recorded in the project metadata. Its full polygon bounds are approximately "
                    "122.946085–122.997387° E and 14.079401–14.150687° N. These are static depth zones: "
                    "they do not include shoreline arrival times or time frames. Start simulation remains "
                    "unavailable until sourced, reviewed time-dependent model data and a playback engine are present."
                )
                st.markdown("### Interpretation limits")
                st.write(
                    "Completion estimates are screening indicators, not predictions. The planning window is a scenario setting, "
                    "not a confirmed warning time. The app does not model tsunami arrival or water movement."
                )
                st.write("Confirm warning and evacuation assumptions with PHIVOLCS and the local MDRRMO before interpreting outputs.")

            with detail_tabs[5]:
                st.markdown("### Daet–Basud road review")
                st.caption("OSM road/path coverage for GIS screening. This is separate from the R1–R12 route demo.")
                st.warning("The image does not confirm pedestrian access, crossings, road condition, safety, or a receiving site in Basud.")
                st.info(
                    "Bridge coverage check: the full regional OSM source contains Daet Bridge 1 (F. Pimentel Avenue; "
                    "lanes=4, foot=yes, sidewalk=both on one source way), consistent with the user's report of the "
                    "fourth-lane opening. The source tag does not independently confirm when it opened or its current "
                    "condition. A separate candidate road layer now keeps the original Daet–Basud road geometries and "
                    "adds mapped road extensions within 100 m of the unchanged administrative boundary. The bridge "
                    "and its mapped approaches are included in the largest raw graph component. This is still an OSM "
                    "geometry connection, not a field-verified pedestrian route; lane count does not determine "
                    "pedestrian capacity."
                )
                st.markdown("### Gubat origin access screening")
                st.caption(
                    "Compares each named-area anchor with nearby mapped road geometry and its recorded graph node. "
                    "Straight-line proximity does not establish an entrance, walkable connector, or safe route."
                )
                if origin_access_review_csv.exists():
                    access_review = pd.read_csv(origin_access_review_csv)
                    access_columns = {
                        "zone_name": "Origin area",
                        "nearest_road_name_or_ref": "Nearest mapped road name",
                        "nearest_road_highway": "OSM road class",
                        "anchor_to_road_geometry_m": "Anchor to road line (m)",
                        "anchor_to_candidate_node_m": "Anchor to candidate node (m)",
                        "candidate_component_id": "Raw graph component",
                        "candidate_component_vertices": "Component vertices",
                        "other_candidate_origins_same_component": "Other origins in component",
                        "review_status": "Review status",
                    }
                    st.dataframe(access_review[list(access_columns)].rename(columns=access_columns), use_container_width=True, hide_index=True)
                    st.download_button(
                        "Download origin access screen (CSV)",
                        data=origin_access_review_csv.read_bytes(),
                        file_name="origin_access_review.csv",
                        mime="text/csv",
                    )
                else:
                    st.info("Origin access screening CSV has not been generated yet.")
                st.markdown("### Road-component proximity review")
                st.caption(
                    "Ranked pairs of graph components with the closest mapped endpoints. Each gap is a straight-line "
                    "measurement for manual review; it is not a road, connector, or recommended route. No links are "
                    "added automatically."
                )
                if component_gap_review_csv.exists():
                    gap_review = pd.read_csv(component_gap_review_csv).head(10)
                    gap_columns = {
                        "review_rank": "Rank",
                        "component_a": "Component A",
                        "component_a_vertices": "A nodes",
                        "component_b": "Component B",
                        "component_b_vertices": "B nodes",
                        "gap_distance_m": "Endpoint gap (m)",
                        "node_a_mapped_roads": "Roads near A",
                        "node_b_mapped_roads": "Roads near B",
                        "node_a_osm_way_ids": "OSM way IDs near A",
                        "node_b_osm_way_ids": "OSM way IDs near B",
                        "review_status": "Review status",
                    }
                    st.dataframe(gap_review[list(gap_columns)].rename(columns=gap_columns), use_container_width=True, hide_index=True)
                    gap_downloads = st.columns(2)
                    with gap_downloads[0]:
                        st.download_button(
                            "Download full component review (CSV)",
                            data=component_gap_review_csv.read_bytes(),
                            file_name="daet_basud_component_gap_review.csv",
                            mime="text/csv",
                        )
                    with gap_downloads[1]:
                        if component_gap_review_geojson.exists():
                            st.download_button(
                                "Download visual review leads (GeoJSON)",
                                data=component_gap_review_geojson.read_bytes(),
                                file_name="daet_basud_component_gap_review.geojson",
                                mime="application/geo+json",
                            )
                else:
                    st.info("Component-gap review has not been generated yet.")
                st.metric("Road/path features in context layer", "2,018")
                st.metric("Raw candidate-graph components", "37")
                st.caption(
                    "Counts describe the current OSM context layer and graph build. Components are review aids, "
                    "not proof of disconnected real-world roads; all suggested links still need manual review."
                )
                road_edges = map_data["road_edges"]
                bridge_fields = {"bridge", "bridge_name", "lanes", "sidewalk"}
                if bridge_fields.issubset(road_edges.columns):
                    bridge_rows = road_edges.loc[
                        road_edges["edge_id"].astype(str).str.endswith("_F")
                        & (
                            road_edges["bridge"].fillna("").astype(str).ne("")
                            | road_edges["bridge_name"].fillna("").astype(str).ne("")
                        )
                    ].drop_duplicates("osm_id")
                    if not bridge_rows.empty:
                        st.markdown("### Bridges and crossing tags")
                        bridge_columns = {
                            "bridge_name": "Bridge name",
                            "name": "Road",
                            "highway": "OSM class",
                            "lanes": "Road lanes (OSM tag)",
                            "foot": "Foot access (OSM tag)",
                            "sidewalk": "Sidewalk (OSM tag)",
                            "layer": "Layer (grade separation)",
                            "osm_id": "OSM way ID",
                        }
                        for column in bridge_columns:
                            if column not in bridge_rows:
                                bridge_rows[column] = ""
                        st.dataframe(
                            bridge_rows[list(bridge_columns)].rename(columns=bridge_columns),
                            use_container_width=True,
                            hide_index=True,
                        )
                        st.caption(
                            "These are source-map tags, not field confirmation. Lane count is not pedestrian capacity, "
                            "and a foot=yes tag does not verify safe crossing conditions or current bridge status."
                        )
                if road_review_png.exists():
                    st.image(road_review_png, caption="Daet–Basud OSM coverage · screening only", use_container_width=True)
                else:
                    st.info("Regional road-review image is not available.")
                if road_review_pdf.exists():
                    st.download_button(
                        "Download road review (PDF)", data=road_review_pdf.read_bytes(),
                        file_name="daet_basud_road_review.pdf", mime="application/pdf",
                    )
                st.caption("© OpenStreetMap contributors. Road data are preliminary and not field-verified.")

            with detail_tabs[6]:
                st.markdown("### Static Gubat exposure map")
                st.caption("Printable QGIS layout export. The interactive map remains the main working view.")
                if map_preview_path.exists():
                    st.image(map_preview_path, caption="Gubat tsunami exposure map", use_container_width=True)
                if map_pdf_path.exists():
                    st.download_button(
                        "Download Gubat exposure map (PDF)", data=map_pdf_path.read_bytes(),
                        file_name="gubat_tsunami_exposure_map.pdf", mime="application/pdf",
                    )
    else:
        if st.button(
            "Explore", icon=":material/left_panel_open:", key="expand_explore_details",
            help="Open the Explore details panel",
        ):
            st.session_state["explore_details_open"] = True
            st.rerun()
