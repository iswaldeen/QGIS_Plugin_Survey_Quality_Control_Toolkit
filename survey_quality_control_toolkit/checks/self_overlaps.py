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

    gtype = QgsWkbTypes.geometryType(geom.wkbType())

    if gtype != QgsWkbTypes.PolygonGeometry:
        collection = geom.asGeometryCollection()

        return [
            g for g in collection
            if g
            and not g.isEmpty()
            and QgsWkbTypes.geometryType(g.wkbType())
            == QgsWkbTypes.PolygonGeometry
        ]

    if geom.isMultipart():
        collection = geom.asGeometryCollection()
        return [g for g in collection if g and not g.isEmpty()]

    return [geom]
 
def cleaned_polygon_geometry(geometry):
    """
    Return a valid polygon geometry, or None if the geometry is unusable.
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

def run(layer, min_overlap_area=0.0001):
    """
    Run self-overlap check against a polygon layer.

    Parameters
    ----------
    layer : QgsVectorLayer
        Polygon layer selected in plugin.

    min_overlap_area : float
        Ignore overlap polygons smaller than this value.
    """

    if layer is None or not layer.isValid():
        raise ValueError("No valid layer supplied.")

    if layer.geometryType() != QgsWkbTypes.PolygonGeometry:
        raise ValueError("Self-overlap check requires a polygon layer.")

    idx, geom_by_id = build_layer_spatial_index(
        layer
    )

    crs = layer.crs()
    crs_uri = (
        crs.authid()
        if crs.isValid() and crs.authid()
        else crs.toWkt()
    )

    out_layer = QgsVectorLayer(
        f"Polygon?crs={crs_uri}",
        f"{layer.name()}_self_overlaps",
        "memory"
    )

    provider = out_layer.dataProvider()

    fields = QgsFields()

    fields.append(QgsField("id_a", QVariant.Int))
    fields.append(QgsField("id_b", QVariant.Int))
    fields.append(QgsField("ov_area", QVariant.Double))

    provider.addAttributes(fields)

    out_layer.updateFields()

    out_features = []

    checked_pairs = set()

    for id_a, geom_a in geom_by_id.items():

        candidate_ids = idx.intersects(
            geom_a.boundingBox()
        )

        for id_b in candidate_ids:

            if id_b == id_a:
                continue

            pair = tuple(sorted((id_a, id_b)))

            if pair in checked_pairs:
                continue

            checked_pairs.add(pair)

            geom_b = geom_by_id.get(id_b)

            if geom_b is None:
                continue

            if not geom_a.intersects(geom_b):
                continue

            inter = geom_a.intersection(geom_b)

            if not inter or inter.isEmpty():
                continue

            if not inter.isGeosValid():
                inter = inter.makeValid()

            if not inter or inter.isEmpty():
                continue

            parts = extract_polygon_parts(inter)

            for part in parts:

                if not part or part.isEmpty():
                    continue

                if (
                    QgsWkbTypes.geometryType(part.wkbType())
                    != QgsWkbTypes.PolygonGeometry
                ):
                    continue

                area = part.area()

                if area < min_overlap_area:
                    continue

                new_feat = QgsFeature(
                    out_layer.fields()
                )

                new_feat.setGeometry(part)

                new_feat["id_a"] = id_a
                new_feat["id_b"] = id_b
                new_feat["ov_area"] = area

                out_features.append(new_feat)

    # Nothing found - do not create a layer.
    if not out_features:
        return 0

    provider.addFeatures(out_features)

    out_layer.updateExtents()

    finalise_output_layer(
        out_layer,
        layer.name(),
        "self_overlaps"
    )

    return len(out_features)
    
def build_layer_spatial_index(layer):
    """
    Build a spatial index and geometry cache for polygon features.
    """

    spatial_index = QgsSpatialIndex()
    geometries = {}

    for feature in layer.getFeatures():
        geometry = cleaned_polygon_geometry(
            feature.geometry()
        )

        if geometry is None:
            continue

        geometries[feature.id()] = geometry
        spatial_index.addFeature(feature)

    return spatial_index, geometries