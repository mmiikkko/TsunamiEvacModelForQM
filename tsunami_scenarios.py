"""Validate sourced, time-stepped tsunami scenario inputs for map playback.

This module performs structural and metadata checks only. It cannot validate
the underlying physical model, hazard interpretation, or real-world safety.
"""

from __future__ import annotations

import math
import sqlite3
from pathlib import Path

import pandas as pd


MANIFEST_NAME = "tsunami_scenario_manifest.csv"
REQUIRED_MANIFEST_COLUMNS = {
    "scenario_id", "scenario_name", "source_organization", "source_title",
    "source_reference", "source_version_date", "scenario_parameters",
    "time_zero_description", "first_time_seconds", "last_time_seconds",
    "time_step_seconds", "depth_units", "horizontal_crs", "vertical_datum",
    "spatial_resolution_m", "frame_geopackage", "frame_layer", "time_field",
    "depth_field", "validation_reference", "uncertainty_limitations",
    "reuse_terms", "technical_review_status", "reviewer_role", "review_date",
}
REQUIRED_NONEMPTY_FIELDS = REQUIRED_MANIFEST_COLUMNS - {
    "first_time_seconds", "last_time_seconds", "time_step_seconds",
    "spatial_resolution_m",
}


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _required_text(row: pd.Series, field: str) -> str:
    value = row.get(field, "")
    if pd.isna(value):
        return ""
    return str(value).strip()


def _validate_frame_file(project_root: Path, row: pd.Series) -> tuple[dict | None, str | None]:
    scenario_id = _required_text(row, "scenario_id")
    gpkg_value = _required_text(row, "frame_geopackage")
    layer = _required_text(row, "frame_layer")
    if not gpkg_value or not layer:
        return None, "frame GeoPackage path or layer name is missing"

    gpkg_path = (project_root / gpkg_value).resolve()
    if not gpkg_path.is_relative_to(project_root.resolve()):
        return None, "frame GeoPackage must be inside the project directory"
    if not gpkg_path.is_file():
        return None, f"frame GeoPackage not found: {gpkg_value}"

    time_field = _required_text(row, "time_field")
    depth_field = _required_text(row, "depth_field")
    depth_class_field = _required_text(row, "depth_class_field")
    scenario_field = "scenario_id"

    try:
        with sqlite3.connect(gpkg_path) as connection:
            contents = connection.execute(
                "SELECT srs_id FROM gpkg_contents WHERE table_name=? AND data_type='features'",
                (layer,),
            ).fetchone()
            if contents is None:
                return None, f"feature layer '{layer}' not found in {gpkg_value}"
            geometry_info = connection.execute(
                "SELECT column_name, geometry_type_name, srs_id FROM gpkg_geometry_columns WHERE table_name=?",
                (layer,),
            ).fetchone()
            if geometry_info is None:
                return None, f"layer '{layer}' has no registered geometry"
            geometry_column, geometry_type, geometry_srs_id = geometry_info
            if str(geometry_type).upper() not in {"POLYGON", "MULTIPOLYGON"}:
                return None, f"layer '{layer}' must contain polygon or multipolygon frames"

            crs_info = connection.execute(
                "SELECT organization, organization_coordsys_id FROM gpkg_spatial_ref_sys WHERE srs_id=?",
                (geometry_srs_id,),
            ).fetchone()
            actual_crs = f"{crs_info[0]}:{crs_info[1]}" if crs_info else "unknown"
            declared_crs = _required_text(row, "horizontal_crs").upper()
            if actual_crs.upper() != "EPSG:4326" or declared_crs != "EPSG:4326":
                return None, (
                    f"map playback currently requires EPSG:4326 coordinates; "
                    f"manifest says {declared_crs or 'blank'}, layer says {actual_crs}"
                )

            columns = {
                info[1] for info in connection.execute(
                    f"PRAGMA table_info({_quote_identifier(layer)})"
                ).fetchall()
            }
            needed_fields = {scenario_field, time_field, depth_field}
            if depth_class_field:
                needed_fields.add(depth_class_field)
            missing_fields = needed_fields - columns
            if missing_fields:
                return None, "frame layer is missing fields: " + ", ".join(sorted(missing_fields))

            quoted_layer = _quote_identifier(layer)
            quoted_scenario = _quote_identifier(scenario_field)
            quoted_time = _quote_identifier(time_field)
            quoted_depth = _quote_identifier(depth_field)
            quoted_geometry = _quote_identifier(geometry_column)
            stats = connection.execute(
                f"SELECT COUNT(*), COUNT(DISTINCT {quoted_time}), MIN({quoted_time}), MAX({quoted_time}), "
                f"SUM(CASE WHEN {quoted_scenario} IS NULL OR {quoted_scenario} != ? THEN 1 ELSE 0 END), "
                f"SUM(CASE WHEN {quoted_time} IS NULL OR typeof({quoted_time}) NOT IN ('integer','real') OR {quoted_time} < 0 OR abs({quoted_time}) >= 1e308 THEN 1 ELSE 0 END), "
                f"SUM(CASE WHEN {quoted_depth} IS NULL OR typeof({quoted_depth}) NOT IN ('integer','real') OR {quoted_depth} < 0 OR abs({quoted_depth}) >= 1e308 THEN 1 ELSE 0 END), "
                f"SUM(CASE WHEN {quoted_geometry} IS NULL OR substr({quoted_geometry},1,2) != x'4750' THEN 1 ELSE 0 END) "
                f"FROM {quoted_layer}",
                (scenario_id,),
            ).fetchone()
            frame_count, time_count, min_time, max_time, scenario_mismatches, invalid_times, invalid_depths, invalid_geometries = stats
            if not frame_count:
                return None, "frame layer contains no features"
            if scenario_mismatches:
                return None, "frame layer contains a scenario_id that does not match the manifest"
            if invalid_times:
                return None, "frame times must be numeric, finite, and nonnegative"
            if invalid_depths:
                return None, "frame depths must be numeric, finite, and nonnegative"
            if invalid_geometries:
                return None, "frame layer contains missing or invalid GeoPackage geometries"
            unique_times = [
                float(item[0]) for item in connection.execute(
                    f"SELECT DISTINCT {quoted_time} FROM {quoted_layer} ORDER BY {quoted_time}"
                ).fetchall()
            ]
    except (sqlite3.Error, OSError) as exc:
        return None, f"could not read frame GeoPackage: {exc}"

    if not unique_times:
        return None, "no valid frame timestamps were found"
    try:
        first_time = float(row["first_time_seconds"])
        last_time = float(row["last_time_seconds"])
        time_step = float(row["time_step_seconds"])
    except (TypeError, ValueError):
        return None, "first time, last time, and timestep must be numeric"
    if not all(math.isfinite(value) for value in (first_time, last_time, time_step)):
        return None, "first time, last time, and timestep must be finite"
    if time_step <= 0 or last_time < first_time:
        return None, "timestep must be positive and last time cannot precede first time"
    try:
        spatial_resolution = float(row["spatial_resolution_m"])
    except (TypeError, ValueError):
        return None, "spatial_resolution_m must be numeric"
    if not math.isfinite(spatial_resolution) or spatial_resolution <= 0:
        return None, "spatial_resolution_m must be a positive finite value"
    tolerance = max(0.5, time_step * 0.01)
    if abs(unique_times[0] - first_time) > tolerance or abs(unique_times[-1] - last_time) > tolerance:
        return None, "manifest start/end times do not match the frame timestamps"
    if len(unique_times) > 1 and any(
        abs((right - left) - time_step) > tolerance
        for left, right in zip(unique_times, unique_times[1:])
    ):
        return None, "frame timestamps do not match the declared timestep"

    return {
        "scenario_id": scenario_id,
        "scenario_name": _required_text(row, "scenario_name"),
        "source_organization": _required_text(row, "source_organization"),
        "source_title": _required_text(row, "source_title"),
        "source_reference": _required_text(row, "source_reference"),
        "time_zero_description": _required_text(row, "time_zero_description"),
        "first_time_seconds": first_time,
        "last_time_seconds": last_time,
        "time_step_seconds": time_step,
        "frame_geopackage": str(gpkg_path),
        "frame_layer": layer,
        "time_field": time_field,
        "depth_field": depth_field,
        "depth_class_field": depth_class_field,
        "frame_count": frame_count,
        "frame_times_seconds": unique_times,
        "technical_review_status": _required_text(row, "technical_review_status"),
    }, None


def load_valid_tsunami_scenarios(project_root: str | Path) -> tuple[list[dict], list[str]]:
    """Return structurally valid, reviewed scenarios and any intake issues."""
    project_root = Path(project_root).resolve()
    manifest_path = project_root / "data" / MANIFEST_NAME
    if not manifest_path.is_file():
        return [], [f"No scenario manifest found at data/{MANIFEST_NAME}."]

    try:
        manifest = pd.read_csv(manifest_path, dtype=str, keep_default_na=False)
    except (OSError, pd.errors.ParserError) as exc:
        return [], [f"Could not read the scenario manifest: {exc}"]

    missing_columns = REQUIRED_MANIFEST_COLUMNS - set(manifest.columns)
    if missing_columns:
        return [], ["Manifest is missing columns: " + ", ".join(sorted(missing_columns))]
    if manifest.empty:
        return [], ["Scenario manifest has no scenario rows yet."]

    valid_scenarios = []
    issues = []
    seen_ids = set()
    for row_index, row in manifest.iterrows():
        row_number = row_index + 2
        scenario_id = _required_text(row, "scenario_id")
        if not scenario_id:
            issues.append(f"Manifest row {row_number}: scenario_id is blank.")
            continue
        if scenario_id in seen_ids:
            issues.append(f"Manifest row {row_number}: duplicate scenario_id '{scenario_id}'.")
            continue
        seen_ids.add(scenario_id)

        missing_values = sorted(
            field for field in REQUIRED_NONEMPTY_FIELDS if not _required_text(row, field)
        )
        if missing_values:
            issues.append(
                f"Scenario '{scenario_id}' is missing required values: "
                + ", ".join(missing_values)
                + "."
            )
            continue
        if _required_text(row, "depth_units").lower() not in {"m", "meter", "meters", "metre", "metres"}:
            issues.append(f"Scenario '{scenario_id}': depth_units must be meters for playback.")
            continue
        if _required_text(row, "technical_review_status").upper() != "REVIEWED_FOR_PROTOTYPE":
            issues.append(
                f"Scenario '{scenario_id}': set technical_review_status to "
                "REVIEWED_FOR_PROTOTYPE only after a qualified reviewer approves prototype interpretation."
            )
            continue

        scenario, error = _validate_frame_file(project_root, row)
        if error:
            issues.append(f"Scenario '{scenario_id}': {error}.")
            continue
        if scenario:
            valid_scenarios.append(scenario)

    if not valid_scenarios and not issues:
        issues.append("No scenario passed the intake checks.")
    return valid_scenarios, issues


def scenario_input_revision(project_root: str | Path) -> tuple:
    """Return file signatures so Streamlit can refresh validation after data changes."""
    project_root = Path(project_root).resolve()
    manifest_path = project_root / "data" / MANIFEST_NAME
    if not manifest_path.is_file():
        return ("missing",)
    manifest_stat = manifest_path.stat()
    revision = [(str(manifest_path), manifest_stat.st_size, manifest_stat.st_mtime_ns)]
    try:
        frame_paths = pd.read_csv(manifest_path, usecols=["frame_geopackage"], dtype=str)["frame_geopackage"]
    except (OSError, ValueError, pd.errors.ParserError):
        return tuple(revision)
    for relative_path in sorted(set(frame_paths.dropna().astype(str).str.strip())):
        if not relative_path:
            continue
        frame_path = (project_root / relative_path).resolve()
        if frame_path.is_relative_to(project_root) and frame_path.is_file():
            frame_stat = frame_path.stat()
            revision.append((str(frame_path), frame_stat.st_size, frame_stat.st_mtime_ns))
        else:
            revision.append((str(frame_path), "missing"))
    return tuple(revision)
