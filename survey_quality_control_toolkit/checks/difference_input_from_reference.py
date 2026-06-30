from qgis.PyQt.QtCore import QVariant

from qgis.core import (
    QgsFeature,
    QgsGeometry,
    QgsSpatialIndex,
    QgsVectorLayer,
    QgsField,
    QgsFields,
    QgsWkbTypes
)
from ..helpers.output_helpers import (
    finalise_output_layer
)

def extract_polygon_parts(geom):
    if geom is None or geom.isEmpty():
        return []
    geom_type = QgsWkbTypes.geometryType(geom.wkbType())
    if geom_type != QgsWkbTypes.PolygonGeometry:
        collection = geom.asGeometryCollection()
        return [g for g in collection if g and not g.isEmpty()
                and QgsWkbTypes.geometryType(g.wkbType()) == QgsWkbTypes.PolygonGeometry]
    if geom.isMultipart():
        collection = geom.asGeometryCollection()
        return [g for g in collection if g and not g.isEmpty()]
    return [geom]


def cleaned_polygon_geometry(geometry):
    if geometry is None or geometry.isEmpty():
        return None
    cleaned = QgsGeometry(geometry)
    try:
        if not cleaned.isGeosValid():
            cleaned = cleaned.makeValid()
    except Exception:
        return None
    if cleaned is None or cleaned.isEmpty():
        return None
    if QgsWkbTypes.geometryType(cleaned.wkbType()) != QgsWkbTypes.PolygonGeometry:
        return None
    return cleaned

def run(input_layer, reference_layer, min_piece_area=0.01, tolerance=0.0):
    if input_layer is None or not input_layer.isValid():
        raise ValueError("Input layer not supplied or invalid.")
    if reference_layer is None or not reference_layer.isValid():
        raise ValueError("Reference layer not supplied or invalid.")

    spatial_index, reference_geometries = build_reference_spatial_index(
        reference_layer
    )

    crs = input_layer.crs()
    crs_uri = crs.authid() if crs.isValid() and crs.authid() else crs.toWkt()

    output_layer = QgsVectorLayer(
        f"Polygon?crs={crs_uri}",
        f"{input_layer.name()}_minus_{reference_layer.name()}",
        "memory"
    )

    provider = output_layer.dataProvider()
    fields = QgsFields()
    fields.append(QgsField("src_id", QVariant.Int))
    fields.append(QgsField("area", QVariant.Double))
    fields.append(QgsField("ref_layer", QVariant.String))
    provider.addAttributes(fields)
    output_layer.updateFields()

    output_features = []

    for input_feature in input_layer.getFeatures():
        input_geometry = cleaned_polygon_geometry(input_feature.geometry())
        if input_geometry is None:
            continue

        union_reference = None

        for candidate_id in spatial_index.intersects(input_geometry.boundingBox()):
            reference_geometry = reference_geometries.get(candidate_id)
            if reference_geometry is None:
                continue

            test_geometry = (
                reference_geometry.buffer(tolerance, 8)
                if tolerance > 0
                else QgsGeometry(reference_geometry)
            )

            if not input_geometry.intersects(test_geometry):
                continue

            if union_reference is None:
                union_reference = QgsGeometry(test_geometry)
            else:
                union_reference = union_reference.combine(test_geometry)

        difference_geometry = (
            QgsGeometry(input_geometry)
            if union_reference is None or union_reference.isEmpty()
            else input_geometry.difference(union_reference)
        )

        if not difference_geometry or difference_geometry.isEmpty():
            continue

        for part in extract_polygon_parts(difference_geometry):
            if not part or part.isEmpty():
                continue

            area = part.area()
            if area < min_piece_area:
                continue

            feat = QgsFeature(output_layer.fields())
            feat.setGeometry(part)
            feat["src_id"] = input_feature.id()
            feat["area"] = area
            feat["ref_layer"] = reference_layer.name()
            output_features.append(feat)

    if not output_features:
        return 0

    provider.addFeatures(output_features)
    output_layer.updateExtents()

    finalise_output_layer(
        output_layer,
        input_layer.name(),
        "difference_input_from_reference"
    )

    return len(output_features)

def build_reference_spatial_index(reference_layer):
    """
    Build a spatial index and geometry cache for reference polygons.
    """

    spatial_index = QgsSpatialIndex()
    reference_geometries = {}

    for feature in reference_layer.getFeatures():
        geometry = cleaned_polygon_geometry(
            feature.geometry()
        )

        if geometry is None:
            continue

        reference_geometries[feature.id()] = geometry
        spatial_index.addFeature(feature)

    return spatial_index, reference_geometries