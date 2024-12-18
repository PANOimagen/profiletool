# -*- coding: utf-8 -*-

import qgis.core


class QgsWkbTypes:

    Point = qgis.core.QGis.WKBPoint
    # 2- qgis.core.QGis.WKBPoint -> 3- qgis.core.QgsWkbTypes.Point
    LineString = qgis.core.QGis.WKBLineString
    # 2- qgis.core.QGis.WKBLineString -> 3- qgis.core.QgsWkbTypes.MultiLineString
    # qgis.core.QGis.WKBMultiLineString = qgis.core.QgsWkbTypes.MultiLineString
    MultiLineString = qgis.core.QGis.WKBMultiLineString
    # 2- qgis.core.QGis.WKBMultiLineString -> 3- qgis.core.QgsWkbTypes.MultiLineString
    # qgis.core.QGis.WKBPolygon = qgis.core.QgsWkbTypes.Polygon
    Polygon = qgis.core.QGis.WKBPolygon

    LineGeometry = qgis.core.QGis.Line
    PointGeometry = qgis.core.QGis.Point


qgis.core.QgsWkbTypes = QgsWkbTypes
