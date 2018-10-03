# coding=utf-8

import qgis.core

# log('Monkeypatching QgsPointXY')
# QgsPoint has been renamed to QgsPoint in QGis 3.0 api
if not hasattr(qgis.core, 'QgsPointXY'):
    qgis.core.QgsPointXY = qgis.core.QgsPoint
