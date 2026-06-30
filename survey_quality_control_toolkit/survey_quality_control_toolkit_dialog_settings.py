# -*- coding: utf-8 -*-
"""
Settings dialog for the Survey Quality Control Toolkit plugin.
"""

import os

from qgis.PyQt import uic
from qgis.PyQt import QtWidgets
from qgis.PyQt.QtCore import QSettings


SETTINGS_PREFIX = "SurveyQualityControlToolkit"

DEFAULT_GEOMETRY_TOLERANCE = 0.0
DEFAULT_MINIMUM_OVERLAP_AREA = 0.0001
DEFAULT_MINIMUM_DIFFERENCE_AREA = 0.01
DEFAULT_GAP_CLOSE_DISTANCE = 0.005


FORM_CLASS, _ = uic.loadUiType(
    os.path.join(
        os.path.dirname(__file__),
        "survey_quality_control_toolkit_dialog_settings_base.ui"
    )
)


class SurveyQualityControlToolkitSettingsDialog(
    QtWidgets.QDialog,
    FORM_CLASS
):
    """
    Settings dialog for Survey Quality Control Toolkit.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setupUi(self)
        self.load_settings()
        self.connect_signals()

    def load_settings(self):
        """
        Load saved settings into the dialog widgets.
        """

        settings = QSettings()

        self.outlineWidthSpinBox.setValue(
            settings.value(
                f"{SETTINGS_PREFIX}/output_outline_width",
                1.5,
                type=float
            )
        )

        self.randomColourCheckBox.setChecked(
            settings.value(
                f"{SETTINGS_PREFIX}/use_random_bright_colours",
                True,
                type=bool
            )
        )

        self.messageDurationSpinBox.setValue(
            settings.value(
                f"{SETTINGS_PREFIX}/message_duration",
                10,
                type=int
            )
        )
        
        self.saveOutputsCheckBox.setChecked(
            settings.value(
                f"{SETTINGS_PREFIX}/save_outputs_as_permanent_layers",
                False,
                type=bool
            )
        )
        
        self.geometryToleranceSpinBox.setValue(
            settings.value(
                f"{SETTINGS_PREFIX}/geometry_tolerance",
                0.0,
                type=float
            )
        )
        
        self.minimumOverlapAreaSpinBox.setValue(
            settings.value(
                f"{SETTINGS_PREFIX}/minimum_overlap_area",
                0.0001,
                type=float
            )
        )

        self.minimumDifferenceAreaSpinBox.setValue(
            settings.value(
                f"{SETTINGS_PREFIX}/minimum_difference_area",
                0.01,
                type=float
            )
        )

        self.gapCloseDistanceSpinBox.setValue(
            settings.value(
                f"{SETTINGS_PREFIX}/gap_close_distance",
                0.005,
                type=float
            )
        )

    def save_settings(self):
        """
        Save dialog widget values to QGIS/QT settings.
        """

        settings = QSettings()

        settings.setValue(
            f"{SETTINGS_PREFIX}/output_outline_width",
            self.outlineWidthSpinBox.value()
        )

        settings.setValue(
            f"{SETTINGS_PREFIX}/use_random_bright_colours",
            self.randomColourCheckBox.isChecked()
        )

        settings.setValue(
            f"{SETTINGS_PREFIX}/message_duration",
            self.messageDurationSpinBox.value()
        )
        
        settings.setValue(
            f"{SETTINGS_PREFIX}/save_outputs_as_permanent_layers",
            self.saveOutputsCheckBox.isChecked()
        )
        
        settings.setValue(
            f"{SETTINGS_PREFIX}/geometry_tolerance",
            self.geometryToleranceSpinBox.value()
        )
        
        settings.setValue(
            f"{SETTINGS_PREFIX}/minimum_overlap_area",
            self.minimumOverlapAreaSpinBox.value()
        )

        settings.setValue(
            f"{SETTINGS_PREFIX}/minimum_difference_area",
            self.minimumDifferenceAreaSpinBox.value()
        )

        settings.setValue(
            f"{SETTINGS_PREFIX}/gap_close_distance",
            self.gapCloseDistanceSpinBox.value()
        )
    
    def connect_signals(self):
        """
        Connect settings dialog signals.
        """

        self.restoreGeometryDefaultsButton.clicked.connect(
            self.restore_geometry_defaults
        )


    def restore_geometry_defaults(self):
        """
        Restore geometry settings to the plugin defaults.
        """

        self.geometryToleranceSpinBox.setValue(
            DEFAULT_GEOMETRY_TOLERANCE
        )

        self.minimumOverlapAreaSpinBox.setValue(
            DEFAULT_MINIMUM_OVERLAP_AREA
        )

        self.minimumDifferenceAreaSpinBox.setValue(
            DEFAULT_MINIMUM_DIFFERENCE_AREA
        )

        self.gapCloseDistanceSpinBox.setValue(
            DEFAULT_GAP_CLOSE_DISTANCE
        )

    def accept(self):
        """
        Save settings when the user clicks OK.
        """

        self.save_settings()
        super().accept()