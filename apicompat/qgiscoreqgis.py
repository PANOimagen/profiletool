# coding=utf-8

import qgis.core

# QGis in QGIS version 2 was renamed to Qgis in QGIS version 3 
if not hasattr(qgis.core, 'Qgis'):
    qgis.core.Qgis = qgis.core.QGis