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
    """
    Extract polygon parts from any geometry.
    """

    if geom is None or geom.isEmpty():
        return []

    if QgsWkbTypes.geometryType(geom.wkbType()) != QgsWkbTypes.PolygonGeometry:
        return [
            g for g in geom.asGeometryCollection()
            if g
            and not g.isEmpty()
            and QgsWkbTypes.geometryType(g.wkbType())
            == QgsWkbTypes.PolygonGeometry
        ]

    if geom.isMultipart():
        return [
            g for g in geom.asGeometryCollection()
            if g and not g.isEmpty()
        ]

    return [geom]

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
    
def cleaned_polygon_geometry(geometry):
    """
    Return a valid polygon geometry, or None if unusable.
    """

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

    if (
        QgsWkbTypes.geometryType(cleaned.wkbType())
        != QgsWkbTypes.PolygonGeometry
    ):
        return None

    return cleaned

def run(
    input_layer,
    reference_layer,
    min_overlap_area=0.0001,
    tolerance=0.0,
    min_matches_required=2
):
    """
    Highlight areas where input polygons overlap multiple features
    within the selected reference layer.
    """

    if input_layer is None or not input_layer.isValid():
        raise ValueError("Input layer not supplied or invalid.")

    if reference_layer is None or not reference_layer.isValid():
        raise ValueError("Reference layer not supplied or invalid.")

    spatial_index, reference_geometries = build_reference_spatial_index(
        reference_layer
    )

    crs = input_layer.crs()
    crs_uri = (
        crs.authid()
        if crs.isValid() and crs.authid()
        else crs.toWkt()
    )

    output_layer = QgsVectorLayer(
        f"Polygon?crs={crs_uri}",
        (
            f"{input_layer.name()}_overlapping_multiple_"
            f"{reference_layer.name()}"
        ),
        "memory"
    )

    provider = output_layer.dataProvider()

    fields = QgsFields()
    fields.append(QgsField("src_id", QVariant.Int))
    fields.append(QgsField("ref_layer", QVariant.String))
    fields.append(QgsField("ref_id", QVariant.Int))
    fields.append(QgsField("ov_area", QVariant.Double))
    fields.append(QgsField("match_cnt", QVariant.Int))

    provider.addAttributes(fields)
    output_layer.updateFields()

    output_features = []

    for input_feature in input_layer.getFeatures():
        input_geometry = cleaned_polygon_geometry(
            input_feature.geometry()
        )

        if input_geometry is None:
            continue

        overlaps_for_input_feature = []
        matched_reference_ids = set()

        candidate_ids = spatial_index.intersects(
            input_geometry.boundingBox()
        )

        for candidate_id in candidate_ids:
            reference_geometry = reference_geometries.get(
                candidate_id
            )

            if reference_geometry is None:
                continue

            test_reference_geometry = (
                reference_geometry.buffer(tolerance, 8)
                if tolerance > 0
                else QgsGeometry(reference_geometry)
            )

            if not input_geometry.intersects(
                test_reference_geometry
            ):
                continue

            intersection = input_geometry.intersection(
                test_reference_geometry
            )

            if not intersection or intersection.isEmpty():
                continue

            if not intersection.isGeosValid():
                intersection = intersection.makeValid()

            if not intersection or intersection.isEmpty():
                continue

            valid_parts = []

            for part in extract_polygon_parts(intersection):
                if not part or part.isEmpty():
                    continue

                if (
                    QgsWkbTypes.geometryType(part.wkbType())
                    != QgsWkbTypes.PolygonGeometry
                ):
                    continue

                overlap_area = part.area()

                if overlap_area < min_overlap_area:
                    continue

                valid_parts.append(
                    {
                        "geometry": part,
                        "ref_id": candidate_id,
                        "ov_area": overlap_area,
                    }
                )

            if valid_parts:
                matched_reference_ids.add(candidate_id)
                overlaps_for_input_feature.extend(valid_parts)

        if len(matched_reference_ids) < min_matches_required:
            continue

        match_count = len(matched_reference_ids)

        for item in overlaps_for_input_feature:
            new_feature = QgsFeature(
                output_layer.fields()
            )

            new_feature.setGeometry(item["geometry"])
            new_feature["src_id"] = input_feature.id()
            new_feature["ref_layer"] = reference_layer.name()
            new_feature["ref_id"] = item["ref_id"]
            new_feature["ov_area"] = item["ov_area"]
            new_feature["match_cnt"] = match_count

            output_features.append(new_feature)

    if not output_features:
        return 0

    provider.addFeatures(output_features)
    output_layer.updateExtents()

    finalise_output_layer(
        output_layer,
        input_layer.name(),
        "multiple_reference_overlaps"
    )

    return len(output_features)