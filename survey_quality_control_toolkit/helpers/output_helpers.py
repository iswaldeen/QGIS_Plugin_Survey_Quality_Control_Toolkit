from datetime import datetime
import os
import random
import re

from qgis.PyQt.QtCore import QSettings
from qgis.PyQt.QtGui import QColor
from qgis.core import (
    QgsFillSymbol,
    QgsProject,
    QgsVectorFileWriter,
    QgsVectorLayer
)


SETTINGS_PREFIX = "SurveyQualityControlToolkit"


def safe_layer_name(value):
    """
    Convert a layer/check name into a safe GeoPackage layer name.
    """

    value = re.sub(r"[^A-Za-z0-9_]+", "_", value)
    value = re.sub(r"_+", "_", value)

    return value.strip("_")

def build_output_layer_name(source_layer_name, check_name):
    """
    Build a timestamped output layer name.
    """

    timestamp = datetime.now().strftime(
        "%d%m%y_%H%M%S"
    )

    return safe_layer_name(
        f"{source_layer_name}_{check_name}_{timestamp}"
    )


def apply_output_style(layer):
    """
    Apply the configured output style to a polygon result layer.
    """

    settings = QSettings()

    outline_width = settings.value(
        f"{SETTINGS_PREFIX}/output_outline_width",
        1.5,
        type=float
    )

    use_random_colours = settings.value(
        f"{SETTINGS_PREFIX}/use_random_bright_colours",
        True,
        type=bool
    )

    colours = [
        QColor("#ff0000"),
        QColor("#ff7f00"),
        QColor("#ffff00"),
        QColor("#00d4ff"),
        QColor("#00ff66"),
        QColor("#b000ff"),
        QColor("#ff1493"),
    ]

    colour = (
        random.choice(colours)
        if use_random_colours
        else QColor("#ff0000")
    )

    symbol = QgsFillSymbol.createSimple({
        "style": "no",
        "outline_style": "solid",
        "outline_color": colour.name(),
        "outline_width": str(outline_width),
        "outline_width_unit": "MM"
    })

    renderer = layer.renderer()

    if renderer is not None:
        renderer.setSymbol(symbol)

    layer.triggerRepaint()


def get_project_output_folder():
    """
    Return the project Geopackages folder, creating it if needed.
    """

    project = QgsProject.instance()
    project_folder = project.homePath()

    if not project_folder:
        raise ValueError(
            "Project folder could not be found. Please save the QGIS project first."
        )

    lowercase_folder = os.path.join(
        project_folder,
        "geopackages"
    )

    uppercase_folder = os.path.join(
        project_folder,
        "Geopackages"
    )

    if os.path.isdir(lowercase_folder):
        return lowercase_folder

    if os.path.isdir(uppercase_folder):
        return uppercase_folder

    os.makedirs(
        uppercase_folder,
        exist_ok=True
    )

    return uppercase_folder


def add_layer_to_quality_group(layer):
    """
    Add a layer to the Survey Quality Checks group.
    """

    project = QgsProject.instance()
    root = project.layerTreeRoot()

    group = root.findGroup(
        "Survey Quality Checks"
    )

    if group is None:
        group = root.insertGroup(
            0,
            "Survey Quality Checks"
        )

    project.addMapLayer(
        layer,
        False
    )

    group.addLayer(layer)


def save_output_layer_to_geopackage(
    layer,
    source_layer_name,
    check_name
):
    """
    Save an output layer into the project Geopackages folder.
    """

    output_folder = get_project_output_folder()

    gpkg_path = os.path.join(
        output_folder,
        "survey_quality_checks.gpkg"
    )

    gpkg_layer_name = build_output_layer_name(
        source_layer_name,
        check_name
    )

    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = "GPKG"
    options.layerName = gpkg_layer_name
    
    if os.path.exists(gpkg_path):
        options.actionOnExistingFile = (
            QgsVectorFileWriter.CreateOrOverwriteLayer
        )
    else:
        options.actionOnExistingFile = (
            QgsVectorFileWriter.CreateOrOverwriteFile
        )

    write_result = QgsVectorFileWriter.writeAsVectorFormatV3(
        layer,
        gpkg_path,
        QgsProject.instance().transformContext(),
        options
    )

    result = write_result[0]
    error_message = write_result[1] if len(write_result) > 1 else ""

    if result != QgsVectorFileWriter.NoError:
        raise ValueError(
            f"Could not save output layer to GeoPackage: {error_message}"
        )

    saved_layer = QgsVectorLayer(
        f"{gpkg_path}|layername={gpkg_layer_name}",
        gpkg_layer_name,
        "ogr"
    )

    if not saved_layer.isValid():
        raise ValueError(
            "The output layer was saved, but could not be loaded back into QGIS."
        )

    return saved_layer


def finalise_output_layer(
    layer,
    source_layer_name,
    check_name
):
    """
    Style and add an output layer.

    Depending on user settings, the layer is either:
    - kept as a temporary memory layer, or
    - saved into survey_quality_checks.gpkg and loaded from disk.
    """
    output_layer_name = build_output_layer_name(
        source_layer_name,
        check_name
    )

    layer.setName(
        output_layer_name
    )
    apply_output_style(layer)

    settings = QSettings()

    save_outputs = settings.value(
        f"{SETTINGS_PREFIX}/save_outputs_as_permanent_layers",
        False,
        type=bool
    )

    if save_outputs:
        layer = save_output_layer_to_geopackage(
            layer,
            source_layer_name,
            check_name
        )

        apply_output_style(layer)

    add_layer_to_quality_group(layer)

    return layer