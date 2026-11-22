from pathlib import Path

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
    synthetic_population_scale = st.slider("Aggregate population multiplier", 0.5, 1.5, 1.0, 0.05)
    small_party_share_pct = st.slider("Small-party share (%) · assumption", 0, 50, 15, 5)
    departure_window_min = st.slider("Random departure window (minutes)", 0, 60, 15, 1)
    zone_balance = st.slider("Zone share balance (1 uneven · 10 even)", 1, 10, 4)
    random_seed = st.number_input("Random seed (repeatable run)", min_value=0, max_value=2_147_483_647, value=2026, step=1)

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


def remember_map_destination():
    """Save a clicked graph-node marker as the candidate receiving point."""
    event = st.session_state.get("scenario_geographic_map", {})
    selection = event.get("selection", {}) if hasattr(event, "get") else {}
    points = selection.get("points", []) if hasattr(selection, "get") else []
    for point in points:
        custom = point.get("customdata")
        if isinstance(custom, (list, tuple)) and len(custom) >= 2 and custom[0] == "CANDIDATE_DESTINATION_NODE":
            st.session_state["candidate_destination_node_id"] = str(custom[1])
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
    synthetic_population = int(round(gubat_population_total * synthetic_population_scale))
    synthetic_groups = scenario_generation.generate_synthetic_groups(
        total_people=synthetic_population,
        small_party_share=small_party_share_pct / 100.0,
        departure_window_min=departure_window_min,
        seed=int(random_seed),
    )
    synthetic_groups, zone_summary = scenario_generation.allocate_groups_to_zones(
        synthetic_groups,
        zone_anchors,
        seed=int(random_seed),
        zone_balance=zone_balance,
    )
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
route_result = None
route_error = None

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
        route_control_cols = st.columns([2.2, 2.3, 1.8, 3.7])
        route_origin_zone_id = route_control_cols[0].selectbox(
            "Route from",
            options=zone_anchors["zone_id"].astype(str).tolist(),
            format_func=lambda zone_id: str(zone_anchors.loc[zone_anchors["zone_id"].astype(str) == zone_id, "zone_name"].iloc[0]),
            key="route_origin_zone_id",
        )
        pick_destination_on_map = route_control_cols[1].toggle(
            "Pick a road point",
            value=False,
            key="pick_destination_on_map",
            help="Then click a teal mapped road node to use it as a candidate receiving location.",
        )
        if route_control_cols[2].button("Clear pin", key="clear_candidate_destination"):
            st.session_state.pop("candidate_destination_node_id", None)
        route_control_cols[3].caption("Pin = scenario candidate only; not a verified safe or available site.")
        selected_destination_node_id = st.session_state.get("candidate_destination_node_id")
        route_origin = zone_anchors.loc[zone_anchors["zone_id"].astype(str) == str(route_origin_zone_id)].iloc[0]
        route_result = None
        route_error = None
        if selected_destination_node_id:
            origin_node_id = str(route_origin["road_node_id"])
            if selected_destination_node_id not in routing_graph:
                route_error = "The selected map node is not present in the current candidate road graph."
            elif origin_node_id not in routing_graph:
                route_error = "This origin's candidate entry point is missing from the road graph."
            elif not nx.has_path(routing_graph, origin_node_id, selected_destination_node_id):
                route_error = "No path connects these points after excluding mapped construction and explicit access restrictions."
            else:
                route_nodes = nx.shortest_path(
                    routing_graph, origin_node_id, selected_destination_node_id, weight="free_flow_min"
                )
                route_length_m = sum(
                    float(routing_graph[a][b].get("length_m", 0.0))
                    for a, b in zip(route_nodes, route_nodes[1:])
                )
                route_result = {
                    "nodes": route_nodes,
                    "length_m": route_length_m,
                    "time_min": route_length_m / (1.15 * float(speed_scale)) / 60.0,
                    "origin_component_size": component_size_for_node.get(origin_node_id, 0),
                    "destination_component_size": component_size_for_node.get(selected_destination_node_id, 0),
                    "origin_coordinates": (float(route_origin["road_lon"]), float(route_origin["road_lat"])),
                    "destination_coordinates": (
                        float(map_node_lookup.loc[selected_destination_node_id, "lon"]),
                        float(map_node_lookup.loc[selected_destination_node_id, "lat"]),
                    ),
                    "named_roads": list(dict.fromkeys(
                        str(routing_graph[a][b].get("name", "")).strip()
                        for a, b in zip(route_nodes, route_nodes[1:])
                        if str(routing_graph[a][b].get("name", "")).strip()
                        and str(routing_graph[a][b].get("name", "")).strip().lower() != "nan"
                    )),
                }
        if pick_destination_on_map:
            st.info("Click a teal road-node dot to pin a candidate receiving location. Zoom in first for easier selection.")

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
            if route_result:
                route_node_coordinates = [
                    map_node_lookup.loc[node_id]
                    for node_id in route_result["nodes"]
                ]
                fig.add_trace(go.Scattermapbox(
                    lon=[float(row["lon"]) for row in route_node_coordinates],
                    lat=[float(row["lat"]) for row in route_node_coordinates],
                    mode="lines",
                    line={"color": "#7c3aed", "width": 5},
                    name="Candidate shortest-time route · unverified",
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
                fig.add_trace(go.Scattermapbox(
                    lon=selectable_nodes["lon"],
                    lat=selectable_nodes["lat"],
                    mode="markers",
                    marker={"size": 7, "color": "#0f766e", "opacity": 0.35},
                    customdata=[["CANDIDATE_DESTINATION_NODE", row.node_id, row.component_vertices]
                                for row in selectable_nodes.itertuples(index=False)],
                    name="Click a road node to set candidate destination",
                    hovertemplate=("Candidate road node<br>ID: %{customdata[1]}<br>"
                                   "Raw component vertices: %{customdata[2]}<br>"
                                   "Click to select as a scenario destination<extra></extra>"),
                    selected={"marker": {"color": "#0f766e", "opacity": 1, "size": 12}},
                    unselected={"marker": {"opacity": 0.25}},
                ))
            if selected_destination_node_id in map_node_lookup.index:
                selected_destination = map_node_lookup.loc[selected_destination_node_id]
                fig.add_trace(go.Scattermapbox(
                    lon=[float(selected_destination["lon"])],
                    lat=[float(selected_destination["lat"])],
                    mode="markers+text",
                    text=["Candidate destination pin"],
                    textposition="top center",
                    marker={"size": 16, "color": "#dc2626", "symbol": "circle"},
                    name="Selected candidate destination pin",
                    customdata=[[selected_destination_node_id]],
                    hovertemplate="Candidate map point<br>Road node: %{customdata[0]}<br>Not a verified safe site<extra></extra>",
                ))
            if show_synthetic_zones:
                if map_extent == "Daet–Basud" and show_boundaries:
                    add_boundary_layer(fig, map_data["gubat_boundary"], "#111827", "Gubat boundary")
                max_zone_people = max(int(zone_summary["people"].max()), 1)
                fig.add_trace(go.Scattermapbox(
                    lon=[coordinate for pair in zip(zone_summary["lon"], zone_summary["road_lon"]) for coordinate in (pair[0], pair[1], None)],
                    lat=[coordinate for pair in zip(zone_summary["lat"], zone_summary["road_lat"]) for coordinate in (pair[0], pair[1], None)],
                    mode="lines", line={"color": "#2563eb", "width": 1},
                    name="Anchor offset · not a route", hoverinfo="skip",
                ))
                fig.add_trace(go.Scattermapbox(
                    lon=zone_summary["lon"], lat=zone_summary["lat"], mode="markers+text",
                    text=zone_summary["map_label"], textposition="top center",
                    marker={"size": [12 + 18 * int(value) / max_zone_people for value in zone_summary["people"]], "color": "#f59e0b", "opacity": 0.9, "symbol": "circle"},
                    name="Named-area origin anchors",
                    customdata=zone_summary[["zone_id", "zone_name", "people", "groups", "simulated_share_pct"]].to_numpy(),
                    hovertemplate=("%{customdata[1]}<br>Origin ID: %{customdata[0]}<br>"
                                   "Synthetic people: %{customdata[2]}<br>Synthetic groups: %{customdata[3]}<br>"
                                   "Randomized share: %{customdata[4]}%<br>Named-place anchor; no household locations<extra></extra>"),
                ))
                fig.add_trace(go.Scattermapbox(
                    lon=zone_summary["road_lon"], lat=zone_summary["road_lat"], mode="markers",
                    marker={"size": [10 + 14 * int(value) / max_zone_people for value in zone_summary["people"]], "color": "#2563eb", "symbol": "circle", "opacity": 0.95},
                    name="Scenario groups · candidate road nodes",
                    customdata=zone_summary[["zone_name", "candidate_road_name", "road_node_id", "people", "groups", "anchor_to_road_m", "road_access_status"]].to_numpy(),
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
                on_select=remember_map_destination,
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
            if route_result:
                legend_items.append('<span class="map-legend-item"><i class="map-legend-line" style="border-color:#7c3aed;border-top-width:4px"></i>Shortest-time candidate route · unverified</span>')
            if pick_destination_on_map:
                legend_items.append('<span class="map-legend-item"><i class="map-legend-dot" style="background:#0f766e"></i>Selectable candidate road node</span>')
            if selected_destination_node_id:
                legend_items.append('<span class="map-legend-item"><i class="map-legend-dot" style="background:#dc2626"></i>Selected candidate destination pin</span>')
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
                st.markdown("### Project status")
                st.metric("Roadmap progress", "80%")
                st.write("Named-area groups now display at candidate nodes on the mapped OSM graph.")
                st.warning("The map pin route is an unreviewed screening preview. The separate R1–R12 demo still drives the route tables below.")
                st.markdown("**Map key**")
                st.write("🟠 Named residential-area reference point")
                st.write("🔵 Candidate OSM graph entry node; size reflects synthetic group totals")
                st.write("🔹 Short connector shows anchor offset only, not a walking route")
                st.caption("The tsunami polygons are static depth classes; no moving-water timeline is available.")

            with detail_tabs[1]:
                st.markdown("### Synthetic origin groups")
                st.warning(
                    f"Scenario assumption: uses the workbook's aggregate Gubat total of {gubat_population_total:,}. "
                    "Its definitions and permission, plus the randomized area shares, need confirmation. No household locations are generated."
                )
                st.metric("Groups generated", f"{len(synthetic_groups):,}")
                st.metric("People in this run", f"{int(synthetic_groups['group_size'].sum()):,}")
                st.metric("Candidate areas", f"{len(zone_summary):,}")
                st.metric("Repeatable seed", f"{int(random_seed)}")
                st.caption(
                    f"Departure draws: 0–{departure_window_min} minutes; typical groups 5–10; small-party assumption 2–3 "
                    f"({small_party_share_pct}% of draws); zone balance control {zone_balance}/10."
                )
                st.bar_chart(departure_counts.set_index("departure_minute"), y="people_departing", height=180)
                st.markdown("**Randomized totals by area**")
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
                    file_name=f"synthetic_gubat_groups_seed_{int(random_seed)}.csv", mime="text/csv",
                )

            with detail_tabs[2]:
                st.markdown("### Route to a map-selected candidate")
                st.caption("Pick a teal road-node point on the map. The app uses the selected origin's candidate graph node as the start and the clicked graph node as the receiving-point pin.")
                if not selected_destination_node_id:
                    st.info("No candidate destination is pinned yet. Turn on **Pick a road point on the map**, then click a teal node. Zoom in to choose the intended street segment.")
                elif route_error:
                    destination_component_size = component_size_for_node.get(str(selected_destination_node_id), 0)
                    origin_component_size = component_size_for_node.get(str(route_origin["road_node_id"]), 0)
                    st.error(route_error)
                    st.write(f"Origin raw component size: {origin_component_size:,} graph nodes")
                    st.write(f"Selected point raw component size: {destination_component_size:,} graph nodes")
                    st.caption("Disconnected points are not joined by straight-line connectors. Review missing links and pedestrian access before routing.")
                elif route_result:
                    st.success("A graph path exists for this selected origin and candidate map point.")
                    metric_cols = st.columns(3)
                    metric_cols[0].metric("Estimated shortest walking time", f"{route_result['time_min']:.1f} min")
                    metric_cols[1].metric("Candidate path length", f"{route_result['length_m'] / 1000:.2f} km")
                    metric_cols[2].metric("Graph segments", f"{len(route_result['nodes']) - 1:,}")
                    st.write(f"Origin: **{route_origin['zone_name']}**")
                    st.write(f"Candidate destination road node: `{selected_destination_node_id}`")
                    st.write(f"Selected point coordinates: {route_result['destination_coordinates'][1]:.6f}, {route_result['destination_coordinates'][0]:.6f}")
                    st.write("OSM road names on path: " + ("; ".join(route_result["named_roads"]) if route_result["named_roads"] else "No names recorded; segment IDs are not shown as street names."))
                    st.caption("The pin is placed directly on a graph node, so its graph snap offset is 0 m. Selecting an arbitrary off-road coordinate is not part of this first version.")
                    st.warning("This is shortest estimated free-flow time on an unreviewed OSM graph, not a congestion-aware evacuation assignment or a safe-route finding. The static inundation polygons contain no tsunami arrival times, so the app cannot model whether this route remains passable as water advances.")
                else:
                    st.info("Select a candidate road node to calculate its screening path.")

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
