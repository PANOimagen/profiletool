# coding=utf-8
"""Monkey patching for QgsProject - QGis 3 compatibility in QGis 2.

From qgis2compat plugin by opengis.ch
"""
import qgis.core
import qgis.utils
from PyQt4.QtCore import QFileInfo

# from qgis2compat import log


# log('Monkeypatching QgsProject')


def visibilityPresetCollection(self):
    return self.visibilityPresetCollection()


qgis.core.QgsProject.mapThemeCollection = visibilityPresetCollection


def mapLayers(self):
    return qgis.core.QgsMapLayerRegistry.instance().mapLayers()


qgis.core.QgsProject.mapLayers = mapLayers


def mapLayersByName(self, layerName):
    return qgis.core.QgsMapLayerRegistry.instance().mapLayersByName(layerName)


qgis.core.QgsProject.mapLayersByName = mapLayersByName


def removeMapLayer(self, layer):
    return qgis.core.QgsMapLayerRegistry.instance().removeMapLayer(layer)


qgis.core.QgsProject.removeMapLayer = removeMapLayer


def addMapLayer(self, mapLayer, addToLegend=True, takeOwnership=True):
    return qgis.core.QgsMapLayerRegistry.instance().addMapLayer(mapLayer, addToLegend)


qgis.core.QgsProject.addMapLayer = addMapLayer


def mapLayer(self, layerId):
    return qgis.core.QgsMapLayerRegistry.instance().mapLayer(layerId)


qgis.core.QgsProject.mapLayer = mapLayer

original_QgsProject_write = qgis.core.QgsProject.write


def write(self, filename):
    return original_QgsProject_write(self, QFileInfo(filename))


qgis.core.QgsProject.write = write

original_QgsProject_read = qgis.core.QgsProject.read


def read(self, param=None):
    if param:
        try:
            return original_QgsProject_read(self, QFileInfo(param))
        except TypeError:
            return original_QgsProject_read(self, param)
    else:
        return original_QgsProject_read(self)


qgis.core.QgsProject.read = read
