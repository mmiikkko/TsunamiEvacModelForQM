from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from simulation import load_inputs, node_coordinate_lookup, run_simulation


st.set_page_config(page_title="Evacuation Scenario Explorer", page_icon="🌊", layout="wide")
st.title("Tsunami Evacuation Scenario Explorer")
st.caption("Research prototype · aggregate route and capacity estimates")
st.warning(
    "The included data are synthetic and schematic. This prototype does not model tsunami water or provide emergency guidance. "
    "Do not use sample results for real-world decisions. Replace data and validate the model with local authorities."
)

map_pdf_path = Path(__file__).parent / "gubat_tsunami_exposure_map.pdf"
map_preview_path = Path(__file__).parent / "gubat_tsunami_exposure_map_preview.png"
with st.expander("View Gubat Tsunami Exposure Map", expanded=True):
    st.caption(
        "Static QGIS exposure-map export for visual reference. It is not a moving tsunami simulation "
        "and is not connected to the synthetic evacuation scenarios below."
    )
    if map_pdf_path.exists():
        map_pdf = map_pdf_path.read_bytes()
        st.download_button(
            "Download exposure map (PDF)",
            data=map_pdf,
            file_name="gubat_tsunami_exposure_map.pdf",
            mime="application/pdf",
        )
        if map_preview_path.exists():
            st.image(
                map_preview_path,
                caption="Static QGIS exposure map · for visual reference",
                use_container_width=True,
            )
        else:
            st.info(
                "The image preview is missing. The PDF is still available to download; "
                "restore `gubat_tsunami_exposure_map_preview.png` beside `app.py` for the in-app preview."
            )
    else:
        st.info(
            "The map PDF is not in the project folder yet. Export it from the QGIS layout and "
            "save it as `gubat_tsunami_exposure_map.pdf` beside `app.py`."
        )

try:
    inputs = load_inputs(str(Path(__file__).parent / "data"))
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
    closed_edges = set(st.multiselect("Close path segments", edge_ids))
    st.caption("Adjust these values only as scenario assumptions. Replace them with evidence when available.")

result = run_simulation(
    inputs,
    population_scale=population_scale,
    speed_scale=speed_scale,
    capacity_scale=capacity_scale,
    departure_delay_min=departure_delay,
    planning_window_min=planning_window,
    closed_edges=closed_edges,
)

left, middle, right = st.columns(3)
left.metric("Estimated population", f"{result['total_population']:,}")
middle.metric("Estimated completion", f"{result['completion_min']:.1f} min")
right.metric(f"Estimated within {planning_window} min", f"{result['within_window']:,}")

st.subheader("Schematic evacuation network")
st.caption("Example coordinates only; replace with verified geographic data before using a map as a local representation.")
coords = node_coordinate_lookup(inputs["nodes"])
fig = go.Figure()
for row in result["edges"].to_dict("records"):
    x1, y1 = coords[str(row["from_node"])]
    x2, y2 = coords[str(row["to_node"])]
    is_closed = row["closed"]
    load = float(row["load_ratio"])
    color = "#98a2b3" if is_closed else ("#dc2626" if load >= 1 else "#167d74")
    fig.add_trace(go.Scatter(
        x=[x1, x2], y=[y1, y2], mode="lines",
        line={"width": 2 + min(float(row["people"]) / 120, 7), "color": color, "dash": "dash" if is_closed else "solid"},
        hovertemplate=(f"Segment {row['edge_id']}<br>Assigned: {row['people']} people<br>"
                       f"Capacity: {row['capacity']:.0f} people/min<br>Estimated queue: {row['queue_min']:.1f} min<extra></extra>"),
        showlegend=False,
    ))
node_rows = inputs["nodes"].to_dict("records")
fig.add_trace(go.Scatter(
    x=[float(r["x"]) for r in node_rows], y=[float(r["y"]) for r in node_rows],
    mode="markers+text", text=[str(r["name"]) for r in node_rows], textposition="top center",
    marker={"size": 13, "color": ["#2b6cb0" if str(r["node_id"]).startswith("O") else "#7c3aed" if str(r["node_id"]).startswith("S") else "#475467" for r in node_rows]},
    customdata=[str(r["node_id"]) for r in node_rows], hovertemplate="%{text}<br>ID: %{customdata}<extra></extra>",
    showlegend=False,
))
fig.update_layout(height=480, margin={"l": 10, "r": 10, "t": 10, "b": 10}, xaxis={"visible": False}, yaxis={"visible": False, "scaleanchor": "x", "scaleratio": 1}, plot_bgcolor="#f6f8fa")
st.plotly_chart(fig, use_container_width=True)

tab_routes, tab_shelters, tab_sources = st.tabs(["Route assignments", "Destination capacity", "Data sources"])
with tab_routes:
    st.dataframe(result["assignments"], use_container_width=True, hide_index=True)
with tab_shelters:
    st.dataframe(result["shelters"], use_container_width=True, hide_index=True)
    st.caption("Assignments are by shortest free-flow walking time. The model does not automatically balance loads across destinations.")
with tab_sources:
    st.dataframe(inputs["data_sources"], use_container_width=True, hide_index=True)
    st.info("Document source, date, resolution/coverage, confidence, license, and any transformations for each real dataset.")

st.subheader("Interpretation")
st.write(
    "This early estimator uses a simplified network capacity calculation. Its completion-time estimate is a screening indicator, "
    "not a validated prediction. The comparison window is a scenario setting, not a confirmed warning time; "
    "confirm any applicable warning or evacuation time with PHIVOLCS and the local MDRRMO."
)
