import qgis.core

# fromPoint() was renamed to fromPointXY() in QGis3
if not hasattr(qgis.core.QgsGeometry, 'fromPointXY'):
    qgis.core.QgsGeometry.fromPointXY = qgis.core.QgsGeometry.fromPoint
    
if not hasattr(qgis.core.QgsGeometry, 'fromPolylineXY'):
    qgis.core.QgsGeometry.fromPolylineXY = qgis.core.QgsGeometry.fromPolyline
