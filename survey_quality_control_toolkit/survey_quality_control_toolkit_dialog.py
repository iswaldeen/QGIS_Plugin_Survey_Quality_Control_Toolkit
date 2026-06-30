# -*- coding: utf-8 -*-
"""
/***************************************************************************
 SurveyQualityControlToolkitDialog
                                 A QGIS plugin
 A plugin to run geometry checks on vectorial polygon layers
 ***************************************************************************/
"""

import os
import webbrowser

from qgis.PyQt import uic
from qgis.PyQt import QtWidgets
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon
from qgis.core import (
    QgsMapLayerProxyModel,
    QgsProject,
    QgsVectorLayer,
    QgsWkbTypes
)


FORM_CLASS, _ = uic.loadUiType(
    os.path.join(
        os.path.dirname(__file__),
        "survey_quality_control_toolkit_dialog_base.ui"
    )
)


class SurveyQualityControlToolkitDialog(QtWidgets.QDialog, FORM_CLASS):

    CHECK_SELF_OVERLAPS = "Self Overlaps"
    CHECK_MULTI_REFERENCE_OVERLAPS = "Multiple Reference Overlaps"
    CHECK_DIFFERENCE_INPUT_FROM_REFERENCE = "Difference Input From Reference"
    CHECK_LINEAR_BOUNDARY_GAPS = "Linear Boundary Gaps"
    
    try:
        USER_ROLE = Qt.ItemDataRole.UserRole
        CHECKED = Qt.CheckState.Checked
        UNCHECKED = Qt.CheckState.Unchecked
        ITEM_IS_USER_CHECKABLE = Qt.ItemFlag.ItemIsUserCheckable
    except AttributeError:
        USER_ROLE = Qt.UserRole
        CHECKED = Qt.Checked
        UNCHECKED = Qt.Unchecked
        ITEM_IS_USER_CHECKABLE = Qt.ItemIsUserCheckable

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setupUi(self)
        self.configure_help_button()
        self.configure_layer_combos()
        self.populate_geometry_checks()
        self.connect_signals()
        self.update_widget_states()

    def configure_help_button(self):
        """
        Configure the help button using a theme-appropriate icon.
        """

        icon_name = (
            "question_mark_darkmode.png"
            if self.palette().window().color().lightness() < 128
            else "question_mark.png"
        )

        icon_path = os.path.join(
            os.path.dirname(__file__),
            "icons",
            icon_name
        )

        self.helpButton.setIcon(
            QIcon(icon_path)
        )

        self.helpButton.clicked.connect(
            self.open_help
        )

    def open_help(self):
        """
        Open the plugin help page.
        """

        help_path = os.path.join(
            os.path.dirname(__file__),
            "help",
            "help.html"
        )

        webbrowser.open(
            "file:///" + help_path.replace("\\", "/")
        )

    def configure_layer_combos(self):
        """
        Configure input layer combo and reference layer checklist.
        """

        self.layerComboBox.setFilters(
            QgsMapLayerProxyModel.PolygonLayer
        )

        self.layerComboBox.setAllowEmptyLayer(True)
        self.layerComboBox.setCurrentIndex(-1)

        self.populate_reference_layer_list()

        self.referenceLayerLabel.setEnabled(False)
        self.referenceLayerListWidget.setEnabled(False)
        self.referenceHelpLabel.setEnabled(False)

    def populate_geometry_checks(self):
        """
        Populate available geometry checks.
        """

        self.checkComboBox.clear()

        self.checkComboBox.addItems([
            self.CHECK_SELF_OVERLAPS,
            self.CHECK_MULTI_REFERENCE_OVERLAPS,
            self.CHECK_DIFFERENCE_INPUT_FROM_REFERENCE,
            self.CHECK_LINEAR_BOUNDARY_GAPS
        ])

        self.checkComboBox.setCurrentIndex(-1)

    def connect_signals(self):
        """
        Connect UI signals used to control widget availability.
        """

        self.layerComboBox.layerChanged.connect(
            self.update_widget_states
        )

        self.referenceLayerListWidget.itemChanged.connect(
            self.update_widget_states
        )

        self.checkComboBox.currentIndexChanged.connect(
            self.update_widget_states
        )

        QgsProject.instance().layersAdded.connect(
            self.refresh_reference_layer_list
        )

        QgsProject.instance().layersRemoved.connect(
            self.refresh_reference_layer_list
        )

    def has_polygon_layers(self):
        """
        Return True if the project contains at least one polygon vector layer.
        """

        for layer in QgsProject.instance().mapLayers().values():
            if (
                isinstance(layer, QgsVectorLayer)
                and layer.geometryType() == QgsWkbTypes.PolygonGeometry
            ):
                return True

        return False

    def polygon_layers(self):
        """
        Return all valid polygon vector layers in the current project.
        """

        layers = []

        for layer in QgsProject.instance().mapLayers().values():
            if (
                isinstance(layer, QgsVectorLayer)
                and layer.isValid()
                and layer.geometryType() == QgsWkbTypes.PolygonGeometry
            ):
                layers.append(layer)

        return sorted(
            layers,
            key=lambda layer: layer.name().lower()
        )

    def populate_reference_layer_list(self):
        """
        Populate the reference layer checklist with polygon layers.
        """

        checked_layer_ids = {
            self.referenceLayerListWidget.item(row).data(self.USER_ROLE)
            for row in range(self.referenceLayerListWidget.count())
            if (
                self.referenceLayerListWidget.item(row).checkState()
                == self.CHECKED
            )
        }

        self.referenceLayerListWidget.blockSignals(True)
        self.referenceLayerListWidget.clear()

        for layer in self.polygon_layers():
            item = QtWidgets.QListWidgetItem(
                layer.name()
            )

            item.setData(
                self.USER_ROLE,
                layer.id()
            )

            item.setFlags(
                item.flags()
                | self.ITEM_IS_USER_CHECKABLE
            )

            item.setCheckState(
                self.CHECKED
                if layer.id() in checked_layer_ids
                else self.UNCHECKED
            )

            self.referenceLayerListWidget.addItem(
                item
            )

        self.referenceLayerListWidget.blockSignals(False)

    def refresh_reference_layer_list(self):
        """
        Refresh reference layers after project layers change.
        """

        self.populate_reference_layer_list()
        self.update_widget_states()

    def selected_reference_layers(self):
        """
        Return checked reference polygon layers.
        """

        selected_layers = []
        project = QgsProject.instance()

        for row in range(self.referenceLayerListWidget.count()):
            item = self.referenceLayerListWidget.item(row)

            if item.checkState() != self.CHECKED:
                continue

            layer_id = item.data(self.USER_ROLE)
            layer = project.mapLayer(layer_id)

            if (
                isinstance(layer, QgsVectorLayer)
                and layer.isValid()
                and layer.geometryType() == QgsWkbTypes.PolygonGeometry
            ):
                selected_layers.append(layer)

        return selected_layers

    def update_widget_states(self):
        """
        Update widget enabled states.
        """

        has_polygon_layers = self.has_polygon_layers()
        selected_layer = self.layerComboBox.currentLayer()

        has_selected_layer = (
            selected_layer is not None
            and selected_layer.isValid()
        )

        self.layerComboBox.setEnabled(
            has_polygon_layers
        )

        self.checkComboBox.setEnabled(
            has_selected_layer
        )

        selected_check = (
            self.checkComboBox.currentIndex() >= 0
        )

        requires_reference_layer = (
            self.checkComboBox.currentText()
            in {
                self.CHECK_MULTI_REFERENCE_OVERLAPS,
                self.CHECK_DIFFERENCE_INPUT_FROM_REFERENCE
            }
        )

        self.referenceLayerLabel.setEnabled(
            requires_reference_layer
        )

        self.referenceLayerListWidget.setEnabled(
            requires_reference_layer
        )

        self.referenceHelpLabel.setEnabled(
            requires_reference_layer
        )

        has_reference_layers = (
            len(self.selected_reference_layers()) > 0
        )

        try:
            ok_button_enum = (
                QtWidgets.QDialogButtonBox.StandardButton.Ok
            )
        except AttributeError:
            ok_button_enum = (
                QtWidgets.QDialogButtonBox.Ok
            )

        ok_button = self.button_box.button(
            ok_button_enum
        )

        if requires_reference_layer:
            ok_button.setEnabled(
                has_selected_layer
                and selected_check
                and has_reference_layers
            )
        else:
            ok_button.setEnabled(
                has_selected_layer
                and selected_check
            )

    def reset_dialog_state(self):
        """
        Reset the dialog to its default state ready for the next use.
        """

        self.layerComboBox.setCurrentIndex(-1)
        self.checkComboBox.setCurrentIndex(-1)

        self.referenceLayerListWidget.blockSignals(True)

        for row in range(self.referenceLayerListWidget.count()):
            self.referenceLayerListWidget.item(row).setCheckState(
                self.UNCHECKED
            )

        self.referenceLayerListWidget.blockSignals(False)

        self.referenceLayerLabel.setEnabled(False)
        self.referenceLayerListWidget.setEnabled(False)
        self.referenceHelpLabel.setEnabled(False)

        self.update_widget_states()

    def closeEvent(self, event):
        """
        Handle dialog close event.

        Project layer signals remain connected because the dialog instance is reused
        for the lifetime of the plugin.
        """

        super().closeEvent(event)
