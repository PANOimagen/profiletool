# -*- coding: utf-8 -*-
# -----------------------------------------------------------
#
# Profile
# Copyright (C) 2008  Borys Jurgiel
# Copyright (C) 2012  Patrice Verchere
# -----------------------------------------------------------
#
# licensed under the terms of GNU GPL 2
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, print to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# ---------------------------------------------------------------------
from qgis.core import QgsPointXY, QgsWkbTypes
from qgis.gui import QgsMapTool, QgsRubberBand, QgsVertexMarker
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import QColor, QCursor

from .selectlinetool import SelectLineTool


class ProfiletoolMapToolRenderer:
    def __init__(self, profiletool):
        self.profiletool = profiletool
        self.iface = self.profiletool.iface
        self.canvas = self.profiletool.iface.mapCanvas()
        self.tool = ProfiletoolMapTool(
            self.canvas, self.profiletool.plugincore.action
        )  # the mouselistener
        self.pointstoDraw = []  # Polyline being drawn in freehand mode
        self.dblclktemp = None  # enable disctinction between leftclick and doubleclick
        self.isPlotting = False
        # the rubberband
        self.rubberband = QgsRubberBand(
            self.iface.mapCanvas(), QgsWkbTypes.GeometryType.LineGeometry
        )
        self.rubberband.setWidth(2)
        self.rubberband.setColor(QColor(Qt.GlobalColor.red))

        self.rubberbandpoint = QgsVertexMarker(self.iface.mapCanvas())
        self.rubberbandpoint.setColor(QColor(Qt.GlobalColor.red))
        self.rubberbandpoint.setIconSize(5)
        self.rubberbandpoint.setIconType(QgsVertexMarker.ICON_BOX)  # or ICON_CROSS, ICON_X
        self.rubberbandpoint.setPenWidth(3)

        self.rubberbandbuf = QgsRubberBand(self.iface.mapCanvas())
        self.rubberbandbuf.setWidth(1)
        self.rubberbandbuf.setColor(QColor(Qt.GlobalColor.blue))

        self.textquit0 = "Left click for polyline and right click to end (Right click to clear)"
        self.textquit1 = "Select the polyline feature in a vector layer (Right click to quit)"
        self.textquit2 = "Select the polyline vector layer (Right click to quit)"

        self.setSelectionMethod(0)

    def resetRubberBand(self):
        self.rubberband.reset(QgsWkbTypes.GeometryType.LineGeometry)

    def updateRubberBand(self):
        self.resetRubberBand()
        for i in range(0, len(self.pointstoDraw)):
            self.rubberband.addPoint(QgsPointXY(self.pointstoDraw[i][0], self.pointstoDraw[i][1]))

    def moved(self, position):  # draw the polyline on the temp layer (rubberband)
        if self.selectionmethod == 0:
            if len(self.pointstoDraw) > 0:
                # Get mouse coords
                mapPos = self.canvas.getCoordinateTransform().toMapCoordinates(
                    position["x"], position["y"]
                )
                # Draw on temp layer
                self.updateRubberBand()
                self.rubberband.addPoint(QgsPointXY(mapPos.x(), mapPos.y()))
        if self.selectionmethod in (1, 2):
            return

    def rightClicked(self, position):  # used to quit the current action
        if self.selectionmethod == 0:
            if self.isPlotting:
                self.updateRubberBand()
                self.isPlotting = False
                # launch analyses
                self.iface.mainWindow().statusBar().showMessage(str(self.pointstoDraw))
                self.profiletool.updateProfil(self.pointstoDraw)
                # Reset
                self.pointstoDraw = []
            else:
                self.profiletool.clearProfil()
                self.cleaning()
        if self.selectionmethod in (1, 2):
            return

    def leftClicked(self, position):  # Add point to analyse
        mapPos = self.canvas.getCoordinateTransform().toMapCoordinates(position["x"], position["y"])
        newPoints = [[mapPos.x(), mapPos.y()]]
        if self.profiletool.doTracking:
            self.rubberbandpoint.hide()

        if self.selectionmethod == 0:
            if not self.isPlotting:
                self.profiletool.clearProfil()
                self.cleaning()
                self.isPlotting = True
            self.pointstoDraw += newPoints
            if self.profiletool.liveUpdate:
                self.profiletool.updateProfil(self.pointstoDraw)
            self.iface.mainWindow().statusBar().showMessage(self.textquit0)
        if self.selectionmethod in (1, 2):
            if self.selectionmethod == 1:
                method = "feature"
                message = self.textquit1
            else:
                method = "layer"
                message = self.textquit2
            result = SelectLineTool(selectionMethod=method).getPointTableFromSelectedLine(
                self.iface, self.tool, newPoints
            )
            self.profiletool.updateProfilFromFeatures(result[0], result[1])

            self.iface.mainWindow().statusBar().showMessage(message)

    def currentLayerChanged(self, layer):
        if self.selectionmethod == 2:
            if SelectLineTool.checkIsLineLayer(layer) or SelectLineTool.checkIsPointLayer(layer):
                self.profiletool.updateProfilFromFeatures(
                    layer, SelectLineTool.select_layer_features(None, layer, None)
                )
            else:
                self.profiletool.clearProfil()

    def setSelectionMethod(self, method):
        self.cleaning()
        self.selectionmethod = method
        if method == 0:
            self.tool.setCursor(Qt.CursorShape.CrossCursor)
            self.iface.mainWindow().statusBar().showMessage(self.textquit0)
        elif method == 1:
            self.tool.setCursor(Qt.CursorShape.PointingHandCursor)
            self.iface.mainWindow().statusBar().showMessage(self.textquit1)
        elif method == 2:
            self.tool.setCursor(Qt.CursorShape.PointingHandCursor)
            self.iface.mainWindow().statusBar().showMessage(self.textquit2)
        self.currentLayerChanged(self.iface.activeLayer())

    def setBufferGeometry(self, geoms):
        self.rubberbandbuf.reset()
        for g in geoms:
            self.rubberbandbuf.addGeometry(g, None)

    def cleaning(self):  # used on right click
        self.pointstoDraw = []
        self.rubberbandpoint.hide()
        self.resetRubberBand()
        self.rubberbandbuf.reset()
        self.iface.mainWindow().statusBar().showMessage("")

    def connectTool(self):
        self.tool.moved.connect(self.moved)
        self.tool.rightClicked.connect(self.rightClicked)
        self.tool.leftClicked.connect(self.leftClicked)
        self.tool.desactivate.connect(self.deactivate)
        self.iface.currentLayerChanged.connect(self.currentLayerChanged)

    def deactivate(self):  # enable clean exit of the plugin
        self.cleaning()
        self.tool.moved.disconnect(self.moved)
        self.tool.rightClicked.disconnect(self.rightClicked)
        self.tool.leftClicked.disconnect(self.leftClicked)
        self.tool.desactivate.disconnect(self.deactivate)
        self.iface.currentLayerChanged.disconnect(self.currentLayerChanged)
        self.canvas.unsetMapTool(self.tool)
        self.canvas.setMapTool(self.profiletool.saveTool)


class ProfiletoolMapTool(QgsMapTool):

    moved = pyqtSignal(dict)
    rightClicked = pyqtSignal(dict)
    leftClicked = pyqtSignal(dict)
    doubleClicked = pyqtSignal(dict)
    desactivate = pyqtSignal()

    def __init__(self, canvas, button):
        QgsMapTool.__init__(self, canvas)
        self.canvas = canvas
        self.cursor = QCursor(Qt.CursorShape.CrossCursor)
        self.button = button

    def canvasMoveEvent(self, event):
        self.moved.emit({"x": event.pos().x(), "y": event.pos().y()})

    def canvasReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.rightClicked.emit({"x": event.pos().x(), "y": event.pos().y()})
        else:
            self.leftClicked.emit({"x": event.pos().x(), "y": event.pos().y()})

    def canvasDoubleClickEvent(self, event):
        self.doubleClicked.emit({"x": event.pos().x(), "y": event.pos().y()})

    def activate(self):
        QgsMapTool.activate(self)
        self.canvas.setCursor(self.cursor)
        self.button.setCheckable(True)
        self.button.setChecked(True)

    def deactivate(self):
        self.desactivate.emit()
        self.button.setCheckable(False)
        QgsMapTool.deactivate(self)

    def isZoomTool(self):
        return False

    def setCursor(self, cursor):
        self.cursor = QCursor(cursor)
