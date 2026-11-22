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
    speed_scale = st.slider("Walking speed multiplier", 0.5, 1.5, 1.0, 0.05)
    capacity_scale = st.slider("Path capacity multiplier", 0.5, 1.5, 1.0, 0.05)
    departure_delay = st.slider("Departure delay (minutes)", 0, 15, 0)
    planning_window = st.slider("Planning comparison window (minutes)", 5, 60, 20)
    edge_ids = inputs["roads"]["edge_id"].astype(str).tolist()
    closed_edges = set(st.multiselect("Close sample path segments (demo network)", edge_ids))
    st.caption("Adjust these values only as scenario assumptions. Replace them with evidence when available.")
    st.divider()
    st.subheader("Synthetic group scenario")
    custom_origins = list(st.session_state.get("scenario_custom_origins", []))
    pending_origin_node_id = st.session_state.get("pending_origin_node_id")
    if pending_origin_node_id:
        st.info(f"Selected candidate origin road node: {pending_origin_node_id}")
    with st.expander("Add a named origin area", expanded=bool(pending_origin_node_id)):
        st.caption("Choose a representative road node on the map first. This creates an aggregate scenario origin, not a household point or a mapped neighborhood boundary.")
        if custom_origins:
            st.caption("User-created origin labels and road-node anchors last for this app session; add them again after a server restart.")
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
def load_interactive_map_data(base_dir: str):
    base = Path(base_dir)
    return {
        "hazard": read_gpkg_features(base / "data" / "gubat_tsunami_clip_fixed.gpkg"),
        "gubat_boundary": read_gpkg_features(base / "data" / "gubat_boundary_traced_fixed.gpkg"),
        "daet_boundary": read_gpkg_features(base / "data" / "daet_boundary.gpkg"),
        "regional_boundary": read_gpkg_features(base / "data" / "daet_basud_boundary.gpkg"),
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


def add_polygon_layer(fig, features, fill_color, line_color, name, show_legend=False, fill_opacity=0.35):
    first = True
    for feature in features:
        for polygon in polygon_parts(feature["geometry"]):
            if not polygon:
                continue
            ring = polygon[0]
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
                hoverinfo="skip",
            ))
            first = False


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
    map_data = load_interactive_map_data(str(project_dir))
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
    for edge in forward_edges.itertuples(index=False):
        length_m = max(float(edge.length_m), 0.0)
        candidate_graph.add_edge(
            str(edge.from_node), str(edge.to_node),
            length_m=length_m,
            free_flow_min=length_m / (1.15 * float(speed_scale)) / 60.0,
            highway=str(edge.highway),
            name=str(edge.name),
        )
        access_tag = str(edge.access).strip().lower()
        foot_tag = str(edge.foot).strip().lower()
        highway_tag = str(edge.highway).strip().lower()
        if (highway_tag != "construction"
                and access_tag not in {"no", "private"}
                and foot_tag not in {"no", "private", "use_sidepath"}):
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
        path_nodes, routing_graph, map_node_lookup, map_data["hazard"]
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
    }
    for index, node_id in enumerate(destination_node_ids)
]

departure_counts = (
    synthetic_groups.assign(departure_minute=synthetic_groups["departure_min"].astype(int))
    .groupby("departure_minute", as_index=False)["group_size"].sum()
    .rename(columns={"group_size": "people_departing"})
)
departure_counts = departure_counts.set_index("departure_minute").reindex(
    range(departure_window_min + 1), fill_value=0
).rename_axis("departure_minute").reset_index()

details_open = st.session_state.get("explore_details_open", True)
map_col, details_col = st.columns([4.1, 1.25] if details_open else [14, 0.8], gap="small")
with map_col:
    with st.container(height=760, key="map_stage"):
        st.markdown("### Tsunami Evacuation Scenario Explorer")
        st.caption("Research prototype · map-selected route is a screening estimate on an unreviewed OSM graph; tsunami depths are static. Not for emergency guidance.")
        control_cols = st.columns([3.5, 1.05, 1.2, 1.0, 1.45])
        map_extent = control_cols[0].radio("Map extent", ["Gubat", "Daet", "Daet–Basud"], horizontal=True, key="map_extent")
        show_roads = control_cols[1].checkbox("OSM roads", value=True, key="show_roads")
        show_hazard = control_cols[2].checkbox("Depth zones", value=True, key="show_hazard")
        show_boundaries = control_cols[3].checkbox("Boundaries", value=True, key="show_boundaries")
        show_synthetic_zones = control_cols[4].checkbox("Named origins", value=True, key="show_origins")
        route_control_cols = st.columns([2.2, 2.0, 1.6, 1.4, 3.5])
        map_selection_mode = route_control_cols[0].selectbox("Map point type", ["Receiving pin", "Origin area"], key="map_point_type")
        pick_destination_on_map = route_control_cols[1].toggle(
            "Pick a road point",
            value=False,
            key="pick_destination_on_map",
            help="Click a teal mapped road node. Add it as a receiving pin, or use it to define an aggregate origin area.",
        )
        staged_destination = st.session_state.get("candidate_destination_node_id")
        if route_control_cols[2].button("Add selected pin", key="add_candidate_destination", disabled=not staged_destination or map_selection_mode != "Receiving pin"):
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
        selected_destination_node_id = st.session_state.get("candidate_destination_node_id")
        if pick_destination_on_map:
            if map_selection_mode == "Receiving pin":
                st.info("Click a teal road-node dot, then choose **Add selected pin**. Repeat to add more than one candidate receiving point.")
            else:
                st.info("Click a teal road-node dot for the aggregate origin's representative access point. Then name it in the left sidebar under **Add a named origin area**.")

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
                for feature in map_data["hazard"]:
                    depth = feature["properties"].get("Inun_depth", "Depth not classified")
                    fill, outline = depth_colors.get(depth, ("#7c3aed", "#4c1d95"))
                    add_polygon_layer(fig, [feature], fill, outline, f"Inundation · {depth}", True, 0.45)
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
            route_colors = ["#7c3aed", "#e11d48", "#0891b2", "#ca8a04", "#2563eb"]
            for route_index, assignment in enumerate(route_assignments):
                route_node_coordinates = [map_node_lookup.loc[node_id] for node_id in assignment["nodes"]]
                fig.add_trace(go.Scattermapbox(
                    lon=[float(row["lon"]) for row in route_node_coordinates],
                    lat=[float(row["lat"]) for row in route_node_coordinates],
                    mode="lines",
                    line={"color": route_colors[route_index % len(route_colors)], "width": 5},
                    name=f"Candidate route · {assignment['origin']}",
                    hoverinfo="skip",
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
                    mode="markers+text",
                    text=[f"Candidate {index + 1}" for index in range(len(committed_destination_rows))],
                    textposition="top center",
                    marker={"size": 16, "color": "#dc2626", "symbol": "circle"},
                    name="Selected candidate destination pins",
                    customdata=[[node_id] for node_id in destination_node_ids],
                    hovertemplate="Candidate map point<br>Road node: %{customdata[0]}<br>Not a verified safe site<extra></extra>",
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
            centers = {
                "Gubat": {"lon": 122.975, "lat": 14.118},
                "Daet": {"lon": 122.944, "lat": 14.109},
                "Daet–Basud": {"lon": 122.973, "lat": 14.025},
            }
            zoom_levels = {"Gubat": 13.0, "Daet": 10.5, "Daet–Basud": 9.2}
            fig.update_layout(
                height=480, margin={"l": 0, "r": 0, "t": 0, "b": 0}, showlegend=False,
                mapbox={"style": "open-street-map", "center": centers[map_extent], "zoom": zoom_levels[map_extent]},
                clickmode="event+select",
                uirevision=f"gubat-map-{map_extent}",
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
                legend_items.append('<span class="map-legend-item"><i class="map-legend-line" style="border-color:#7c3aed;border-top-width:4px"></i>Candidate origin-to-pin routes · unverified</span>')
            if pick_destination_on_map:
                selectable_label = "Selectable origin road node" if map_selection_mode == "Origin area" else "Selectable receiving-point node"
                legend_items.append(f'<span class="map-legend-item"><i class="map-legend-dot" style="background:#0f766e"></i>{selectable_label}</span>')
            if destination_node_ids:
                legend_items.append('<span class="map-legend-item"><i class="map-legend-dot" style="background:#dc2626"></i>Candidate receiving-point pins</span>')
            if st.session_state.get("pending_origin_node_id"):
                legend_items.append('<span class="map-legend-item"><i class="map-legend-dot" style="background:#9333ea"></i>Staged origin anchor</span>')
            if show_synthetic_zones:
                legend_items.extend([
                    '<span class="map-legend-item"><i class="map-legend-line" style="border-color:#2563eb"></i>Anchor offset · not a route</span>',
                    '<span class="map-legend-item"><i class="map-legend-dot" style="background:#f59e0b"></i>Named-area origin anchor</span>',
                    '<span class="map-legend-item"><i class="map-legend-dot" style="background:#2563eb"></i>Candidate road node · size shows group total</span>',
                ])
            st.markdown('<div class="map-legend">' + ''.join(legend_items) + '</div>', unsafe_allow_html=True)
            shared_component_zones = max(len(zone_summary) - zone_summary["shares_candidate_component_with"].eq("No other included origin candidate").sum(), 0)
            st.caption(
                f"OSM © OpenStreetMap contributors · pan/zoom enabled · raw graph screen: {shared_component_zones}/{len(zone_summary)} "
                f"origin candidates share a geometry component. A plotted shortest-time route is based on unreviewed graph geometry and is not a safe-route recommendation."
            )
        except Exception as exc:
            st.error(f"Could not load the geographic map layers: {exc}")

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
                    st.dataframe(pd.DataFrame(destination_capacity_summary), use_container_width=True, hide_index=True)
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
                        st.warning("Some synthetic groups remain unassigned because no selected pin is connected or the connected pins have reached their entered capacities.")
                        st.dataframe(pd.DataFrame(unrouted_origins), use_container_width=True, hide_index=True)
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
                st.metric("Mapped road/path features", "1,551")
                st.metric("Geometry-screening components", "136")
                st.caption("Components are review aids; they are not proof of disconnected real-world roads. Component review remains incomplete.")
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
