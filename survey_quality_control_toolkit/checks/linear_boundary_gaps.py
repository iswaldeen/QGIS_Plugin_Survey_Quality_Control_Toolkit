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


def make_valid_geometry(geometry):
    """
    Return a valid geometry, or None if the geometry is unusable.
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

    return cleaned
    
def build_spatial_index(layer):
    """
    Build a spatial index and geometry cache.
    """

    index = QgsSpatialIndex()
    geometries = {}

    for feature in layer.getFeatures():
        geometry = make_valid_geometry(
            feature.geometry()
        )

        if geometry is None:
            continue

        geometries[feature.id()] = geometry
        index.addFeature(feature)

    return index, geometries

def count_neighbouring_features(
    gap_geometry,
    spatial_index,
    geometry_cache,
    tolerance
):
    """
    Count nearby source features using a spatial index.
    """

    if gap_geometry is None or gap_geometry.isEmpty():
        return 0

    test_geometry = gap_geometry.buffer(
        tolerance,
        8
    )

    count = 0

    for feature_id in spatial_index.intersects(
        test_geometry.boundingBox()
    ):
        geometry = geometry_cache.get(feature_id)

        if geometry is None:
            continue

        if test_geometry.intersects(geometry):
            count += 1

    return count
    
def extract_polygon_parts(geometry):
    """
    Return polygon parts only.

    Handles single polygons, multipolygons, and geometry collections.
    """

    if geometry is None or geometry.isEmpty():
        return []

    output_parts = []
    geometry_type = QgsWkbTypes.geometryType(
        geometry.wkbType()
    )

    if geometry_type == QgsWkbTypes.PolygonGeometry:

        if geometry.isMultipart():
            try:
                collection = geometry.asGeometryCollection()
            except Exception:
                return []

            for part in collection:
                if (
                    part
                    and not part.isEmpty()
                    and QgsWkbTypes.geometryType(part.wkbType())
                    == QgsWkbTypes.PolygonGeometry
                ):
                    output_parts.append(part)

        else:
            output_parts.append(geometry)

    else:
        try:
            collection = geometry.asGeometryCollection()
        except Exception:
            return []

        for part in collection:
            if not part or part.isEmpty():
                continue

            if (
                QgsWkbTypes.geometryType(part.wkbType())
                != QgsWkbTypes.PolygonGeometry
            ):
                continue

            if part.isMultipart():
                try:
                    subparts = part.asGeometryCollection()
                except Exception:
                    continue

                for subpart in subparts:
                    if (
                        subpart
                        and not subpart.isEmpty()
                        and QgsWkbTypes.geometryType(subpart.wkbType())
                        == QgsWkbTypes.PolygonGeometry
                    ):
                        output_parts.append(subpart)

            else:
                output_parts.append(part)

    return output_parts


def build_polygon_parts_from_layer(layer):
    """
    Extract valid polygon parts from all features in a layer.
    """

    polygon_parts = []

    for feature in layer.getFeatures():
        geometry = make_valid_geometry(
            feature.geometry()
        )

        if geometry is None:
            continue

        parts = extract_polygon_parts(
            geometry
        )

        for part in parts:
            cleaned_part = make_valid_geometry(
                part
            )

            if (
                cleaned_part is not None
                and not cleaned_part.isEmpty()
                and QgsWkbTypes.geometryType(cleaned_part.wkbType())
                == QgsWkbTypes.PolygonGeometry
            ):
                polygon_parts.append(cleaned_part)

    return polygon_parts


def calculate_thinness_ratio(geometry):
    """
    Return a sliver-style thinness ratio.

    Higher values indicate a longer, thinner polygon.
    """

    if geometry is None or geometry.isEmpty():
        return 0.0

    area = geometry.area()
    perimeter = geometry.length()

    if area <= 0:
        return 0.0

    return (perimeter * perimeter) / area


def calculate_bbox_ratio(geometry):
    """
    Return the ratio of long bounding-box side to short side.
    """

    if geometry is None or geometry.isEmpty():
        return 0.0

    bounding_box = geometry.boundingBox()
    width = bounding_box.width()
    height = bounding_box.height()

    if width <= 0 or height <= 0:
        return 0.0

    long_side = max(width, height)
    short_side = min(width, height)

    if short_side == 0:
        return 0.0

    return long_side / short_side

def dissolve_all_parts(polygon_parts):
    """
    Dissolve all polygon parts into a single geometry.
    """

    if not polygon_parts:
        return None

    try:
        dissolved = QgsGeometry.unaryUnion(
            polygon_parts
        )
    except Exception:
        return None

    return make_valid_geometry(
        dissolved
    )

def run(
    layer,
    gap_close_dist=0.005,
    min_gap_area=0.000000001,
    max_gap_area=0.02,
    min_thinness_ratio=12.0,
    min_bbox_ratio=3.0,
    required_neighbour_count=2,
    buffer_segments=8
):
    """
    Find narrow linear gaps between parallel polygon boundaries.

    Parameters
    ----------
    layer : QgsVectorLayer
        Polygon layer selected in the plugin.

    gap_close_dist : float
        Buffer distance used to close small gaps. Units are layer CRS units.

    min_gap_area : float
        Ignore gap polygons smaller than this area.

    max_gap_area : float
        Ignore gap polygons larger than this area.

    min_thinness_ratio : float
        Minimum thinness ratio required for a gap polygon.

    min_bbox_ratio : float
        Minimum bounding-box elongation ratio required.

    required_neighbour_count : int
        Number of nearby source features expected around a real boundary gap.

    buffer_segments : int
        Number of segments used when buffering.

    Returns
    -------
    int
        Number of linear boundary gap polygons found.
    """

    if layer is None or not layer.isValid():
        raise ValueError("No valid layer supplied.")

    if layer.geometryType() != QgsWkbTypes.PolygonGeometry:
        raise ValueError("Linear boundary gap check requires a polygon layer.")

    polygon_parts = build_polygon_parts_from_layer(
        layer
    )

    if not polygon_parts:
        raise ValueError(
            "No valid polygon geometries could be extracted from the layer."
        )

    original_union = dissolve_all_parts(
        polygon_parts
    )

    if original_union is None or original_union.isEmpty():
        raise ValueError(
            "Could not build dissolved geometry from the layer."
        )

    spatial_index, geometry_cache = build_spatial_index(
        layer
    )

    # Morphological closing:
    # buffer out, then back in. Small linear gaps become closed.
    expanded = original_union.buffer(
        gap_close_dist,
        buffer_segments
    )
    expanded = make_valid_geometry(
        expanded
    )

    if expanded is None or expanded.isEmpty():
        raise ValueError("Expanded geometry is empty.")

    closed = expanded.buffer(
        -gap_close_dist,
        buffer_segments
    )
    closed = make_valid_geometry(
        closed
    )

    if closed is None or closed.isEmpty():
        raise ValueError("Closed geometry is empty.")

    gap_candidates = closed.difference(
        original_union
    )
    gap_candidates = make_valid_geometry(
        gap_candidates
    )

    if gap_candidates is None or gap_candidates.isEmpty():
        return 0

    crs = layer.crs()
    crs_uri = (
        crs.authid()
        if crs.isValid() and crs.authid()
        else crs.toWkt()
    )

    output_layer = QgsVectorLayer(
        f"Polygon?crs={crs_uri}",
        f"{layer.name()}_linear_boundary_gaps",
        "memory"
    )

    provider = output_layer.dataProvider()

    fields = QgsFields()
    fields.append(QgsField("gap_area", QVariant.Double))
    fields.append(QgsField("gap_perim", QVariant.Double))
    fields.append(QgsField("thin_rat", QVariant.Double))
    fields.append(QgsField("bbox_rat", QVariant.Double))
    fields.append(QgsField("near_cnt", QVariant.Int))

    provider.addAttributes(fields)
    output_layer.updateFields()

    output_features = []

    for part in extract_polygon_parts(gap_candidates):

        if part is None or part.isEmpty():
            continue

        area = part.area()

        if area < min_gap_area:
            continue

        if area > max_gap_area:
            continue

        perimeter = part.length()
        thinness_ratio = calculate_thinness_ratio(
            part
        )
        bbox_ratio = calculate_bbox_ratio(
            part
        )

        # Keep only long, thin sliver-like polygons.
        if thinness_ratio < min_thinness_ratio:
            continue

        if bbox_ratio < min_bbox_ratio:
            continue

        nearby_count = count_neighbouring_features(
            part,
            spatial_index,
            geometry_cache,
            gap_close_dist * 2.0
        )

        # A typical linear boundary gap should sit between two features.
        if nearby_count != required_neighbour_count:
            continue

        new_feature = QgsFeature(
            output_layer.fields()
        )

        new_feature.setGeometry(part)
        new_feature["gap_area"] = area
        new_feature["gap_perim"] = perimeter
        new_feature["thin_rat"] = thinness_ratio
        new_feature["bbox_rat"] = bbox_ratio
        new_feature["near_cnt"] = nearby_count

        output_features.append(
            new_feature
        )

    if not output_features:
        return 0

    provider.addFeatures(
        output_features
    )
    output_layer.updateExtents()

    finalise_output_layer(
        output_layer,
        layer.name(),
        "linear_boundary_gaps"
    )

    return len(output_features)
