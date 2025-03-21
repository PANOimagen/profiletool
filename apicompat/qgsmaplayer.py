# coding=utf-8

import qgis.core


# log('Monkeypatching QgsPointXY')
# hasGeometryType has been replaced by isSpatial in QGis 3.0 api
def isSpatial(self):
    # Will raise AttributeError when used with layers that are not
    # QgsVectorLayer, but that is the expected behaviour in Qgis 2.x
    return self.hasGeometryType()


qgis.core.QgsMapLayer.isSpatial = isSpatial
# MeshLayer is defined in QGis 3.x, should not appear in QGis 2.x
qgis.core.QgsMapLayer.MeshLayer = 3
