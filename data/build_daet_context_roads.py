"""Create a road-only 100 m context around the Daet–Basud boundary.

The administrative boundary is unchanged. The buffer only controls which OSM
road features are retained so roads that cross the boundary (including Daet
Bridge 1) can connect to the in-boundary candidate graph.
"""

from __future__ import annotations

from pathlib import Path

from qgis.core import (
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsFeature,
    QgsGeometry,
    QgsProject,
    QgsVectorFileWriter,
    QgsVectorLayer,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "raw" / "osm_camarines_norte_roads.gpkg"
BOUNDARY = ROOT / "data" / "daet_basud_boundary.gpkg"
BASE_ROADS = ROOT / "data" / "daet_basud_roads.gpkg"
OUTPUT = ROOT / "data" / "daet_basud_roads_context_100m.gpkg"
BUFFER_METERS = 100


def main() -> None:
    app = QgsApplication([], False)
    app.initQgis()
    project = QgsProject.instance()

    roads = QgsVectorLayer(f"{SOURCE}|layername=highway_camarines_norte", "regional roads", "ogr")
    boundary = QgsVectorLayer(f"{BOUNDARY}|layername=daet_basud_boundary", "Daet-Basud boundary", "ogr")
    base_roads = QgsVectorLayer(f"{BASE_ROADS}|layername=daet_basud_roads", "in-boundary roads", "ogr")
    if not roads.isValid() or not boundary.isValid() or not base_roads.isValid():
        raise RuntimeError("Could not open the regional roads, base roads, or Daet–Basud boundary GeoPackage")

    source_crs = roads.crs()
    metric_crs = QgsCoordinateReferenceSystem("EPSG:32651")
    to_metric = QgsCoordinateTransform(source_crs, metric_crs, project)
    to_source = QgsCoordinateTransform(metric_crs, source_crs, project)

    boundary_feature = next(boundary.getFeatures())
    buffer_geometry = QgsGeometry(boundary_feature.geometry())
    if buffer_geometry.transform(to_metric) != 0:
        raise RuntimeError("Could not project the Daet–Basud boundary")
    buffer_geometry = buffer_geometry.buffer(BUFFER_METERS, 12)

    memory = QgsVectorLayer("MultiLineString?crs=EPSG:4326", "daet_basud_roads_context_100m", "memory")
    provider = memory.dataProvider()
    attribute_indices = [index for index, field in enumerate(roads.fields()) if field.name().lower() != "fid"]
    provider.addAttributes([roads.fields()[index] for index in attribute_indices])
    memory.updateFields()

    # Keep all original clipped geometries byte-for-byte in coordinate space so
    # existing origin node IDs continue to resolve in the regenerated graph.
    base_by_osm_id: dict[str, list[QgsGeometry]] = {}
    base_count = 0
    for base_road in base_roads.getFeatures():
        feature = QgsFeature(memory.fields())
        geometry = QgsGeometry(base_road.geometry())
        geometry.convertToMultiType()
        feature.setGeometry(geometry)
        feature.setAttributes([base_road.attributes()[index] for index in attribute_indices])
        provider.addFeature(feature)
        osm_id = str(base_road["osm_id"])
        base_by_osm_id.setdefault(osm_id, []).append(QgsGeometry(base_road.geometry()))
        base_count += 1

    retained = 0
    for road in roads.getFeatures():
        geometry = QgsGeometry(road.geometry())
        if geometry.transform(to_metric) != 0:
            continue
        if not geometry.intersects(buffer_geometry):
            continue
        geometry = geometry.intersection(buffer_geometry)
        if geometry.isEmpty() or geometry.length() == 0:
            continue
        same_way_parts = base_by_osm_id.get(str(road["osm_id"]), [])
        if same_way_parts:
            existing = QgsGeometry.unaryUnion([QgsGeometry(part) for part in same_way_parts])
            if existing.transform(to_metric) != 0:
                continue
            geometry = geometry.difference(existing)
            if geometry.isEmpty() or geometry.length() == 0:
                continue
        if geometry.transform(to_source) != 0:
            continue
        geometry.convertToMultiType()
        feature = QgsFeature(memory.fields())
        feature.setGeometry(geometry)
        feature.setAttributes([road.attributes()[index] for index in attribute_indices])
        provider.addFeature(feature)
        retained += 1

    memory.updateExtents()
    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = "GPKG"
    options.layerName = "daet_basud_roads_context_100m"
    options.fileEncoding = "UTF-8"
    options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile
    result = QgsVectorFileWriter.writeAsVectorFormatV3(memory, str(OUTPUT), project.transformContext(), options)
    if result[0] != QgsVectorFileWriter.NoError:
        raise RuntimeError(f"Failed to write context roads: {result}")
    print(f"Preserved in-boundary features: {base_count}")
    print(f"Added outside-boundary road/path extensions: {retained}")
    print(f"Buffer: {BUFFER_METERS} m around unchanged Daet–Basud admin boundary")
    print(f"Output: {OUTPUT}")
    app.exitQgis()


if __name__ == "__main__":
    main()
