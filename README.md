# QGIS_Plugin_Survey_quality_control_toolkit
Survey quality control toolkit is a QGIS plugin for running automated quality-control checks on polygon vectorial data.

<img src="survey_quality_control_toolkit/icons/sqc_toolkit_icon.png" width="100" height="100">

## Features

* Run automated geometry quality-control checks on polygon layers.
* Detect overlapping polygons within the same layer.
* Identify polygons overlapping multiple reference features.
* Find areas in an input layer not covered by reference layers.
* Detect narrow gaps and slivers between adjacent polygons.
* Support multiple reference layers for comparison checks.
* Save results as temporary layers or permanently to a GeoPackage.
* Automatically style output layers for clear visual review.
* Organise results in a dedicated **Survey Quality Checks** layer group.

## Compatibility

Survey quality control toolkit is actively developed and tested for:

* QGIS 3.28+
* PyQt5 / Qt5

## License

All content is licensed under the <a href="https://creativecommons.org/licenses/by-sa/3.0/">Creative Commons Attribution-ShareAlike 3.0 licence (CC BY-SA)</a>.