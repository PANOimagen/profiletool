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

from contextlib import suppress

import numpy as np

# qgis import
from qgis.core import QgsGeometry, QgsMapLayer, QgsPoint, QgsPointXY, QgsProject
from qgis.core import QgsVectorLayer, QgsFeature, QgsWkbTypes

# from qgis.gui import *
from qgis.PyQt.QtCore import QSettings, Qt

# from qgis.PyQt.QtGui import QColor
# from qgis.PyQt.QtSvg import *  # required in some distros
from qgis.PyQt.QtWidgets import QWidget

from ..ui.ptdockwidget import PTDockWidget
from . import profilers

# plugin import
from .dataReaderTool import DataReaderTool
from .plottingtool import PlottingTool
from .ptmaptool import ProfiletoolMapToolRenderer
from .selectlinetool import SelectLineTool


class ProfileToolCore(QWidget):
    def __init__(self, iface, plugincore, parent=None):
        QWidget.__init__(self, parent)
        self.iface = iface
        self.plugincore = plugincore
        self.instance = QgsProject.instance()

        # remimber repository for saving
        if QSettings().value("profiletool/lastdirectory") != "":
            self.loaddirectory = QSettings().value("profiletool/lastdirectory")
        else:
            self.loaddirectory = ""

        # mouse tracking
        self.doTracking = False
        self.liveUpdate = True
        # the datas / results
        # dictionary where is saved the plotting data {"l":[l],"z":[z], "layer":layer1, "curve":curve1}  # noqa: E501
        self.profiles = None
        # The line information
        self.pointstoDraw = []
        # he renderer for temporary polyline
        # self.toolrenderer = ProfiletoolMapToolRenderer(self)
        self.toolrenderer = None
        # the maptool previously loaded
        self.saveTool = None  # Save the standard mapttool for restoring it at the end
        # Used to remove highlighting from previously active layer.
        self.previousLayerId = None
        self.x_cursor = None  # Keep track of last x position of cursor
        # the dockwidget
        self.dockwidget = PTDockWidget(self.iface, self)
        # Initialize the dockwidget combo box with the list of available profiles.
        # (Use sorted list to be sure that Height is always on top and
        # the combobox order is consistent)
        for profile in sorted(profilers.PLOT_PROFILERS):
            self.dockwidget.plotComboBox.addItem(profile)
        self.dockwidget.plotComboBox.setCurrentIndex(0)
        self.dockwidget.plotComboBox.currentIndexChanged.connect(lambda index: self.plotProfil())
        # dockwidget graph zone
        self.dockwidget.changePlotLibrary(self.dockwidget.cboLibrary.currentIndex())

    def activateProfileMapTool(self):
        self.saveTool = (
            self.iface.mapCanvas().mapTool()
        )  # Save the standard mapttool for restoring it at the end
        # Listeners of mouse
        self.toolrenderer = ProfiletoolMapToolRenderer(self)
        self.toolrenderer.connectTool()
        self.toolrenderer.setSelectionMethod(self.dockwidget.comboBox.currentIndex())
        # init the mouse listener comportement and save the classic to restore it on quit
        self.iface.mapCanvas().setMapTool(self.toolrenderer.tool)
        self.instance.layersRemoved.connect(lambda: self.removeClosedLayers(self.dockwidget.mdl))

    # ******************************************************************************************
    # **************************** function part *************************************************
    # ******************************************************************************************

    def clearProfil(self):
        self.updateProfilFromFeatures(None, [])

    def updateProfilFromFeatures(self, layer, features, plotProfil=True):
        """Updates self.profiles from given feature list.

        This function extracts the list of coordinates from the given
        feature set and calls updateProfil.
        This function also manages selection/deselection of features in the
        active layer to highlight the feature being profiled.
        """
        pointstoDraw = []

        # Remove selection from previous layer if it still exists
        previousLayer = QgsProject.instance().mapLayer(self.previousLayerId)
        if previousLayer:
            previousLayer.removeSelection()

        if layer:
            self.previousLayerId = layer.id()
        else:
            self.previousLayerId = None

        if layer:
            is_point_layer = SelectLineTool.checkIsPointLayer(layer)
            layer.removeSelection()
            layer.select([f.id() for f in features])
            first_segment = True
            for feature in features:
                if first_segment or is_point_layer:
                    # Point layers have one vertex at 0 for each feature,
                    # Line layers vertex at 0 after first segment is
                    # the same as last vertex from previous segment.
                    k = 0
                    first_segment = False
                else:
                    k = 1
                while not feature.geometry().vertexAt(k) == QgsPoint():
                    point2 = self.toolrenderer.tool.toMapCoordinates(
                        layer, QgsPointXY(feature.geometry().vertexAt(k))
                    )
                    pointstoDraw += [[point2.x(), point2.y()]]
                    k += 1
        self.updateProfil(pointstoDraw, False, plotProfil)

    def updateProfil(self, points1, removeSelection=True, plotProfil=True):
        """Updates self.profiles from values in points1.

        This function can be called from updateProfilFromFeatures or from
        ProfiletoolMapToolRenderer (with a list of points from rubberband).
        """
        if removeSelection:
            # Be sure that we unselect anything in the previous layer.
            previousLayer = QgsProject.instance().mapLayer(self.previousLayerId)
            if previousLayer:
                previousLayer.removeSelection()
        # replicate last point (bug #6680)
        # if points1:
        #    points1 = points1 + [points1[-1]]
        self.pointstoDraw = points1
        self.profiles = []
        self.distancesPicked = []

        # calculate profiles
        for i in range(0, self.dockwidget.mdl.rowCount()):
            self.profiles.append(
                {"layer": self.dockwidget.mdl.item(i, 5).data(Qt.ItemDataRole.EditRole)}
            )
            self.profiles[i]["band"] = self.dockwidget.mdl.item(i, 3).data(Qt.ItemDataRole.EditRole)

            if (
                self.dockwidget.mdl.item(i, 5).data(Qt.ItemDataRole.EditRole).type()
                == QgsMapLayer.VectorLayer
            ):
                self.profiles[i], _, _ = DataReaderTool().dataVectorReaderTool(
                    self.iface,
                    self.toolrenderer.tool,
                    self.profiles[i],
                    self.pointstoDraw,
                    float(self.dockwidget.mdl.item(i, 4).data(Qt.ItemDataRole.EditRole)),
                )
            else:
                if self.dockwidget.profileInterpolationCheckBox.isChecked():
                    if self.dockwidget.fullResolutionCheckBox.isChecked():
                        resolution_mode = "full"
                    else:
                        resolution_mode = "limited"
                else:
                    resolution_mode = "samples"

                self.profiles[i] = DataReaderTool().dataRasterReaderTool(
                    self.iface,
                    self.toolrenderer.tool,
                    self.profiles[i],
                    self.pointstoDraw,
                    resolution_mode,
                )
            # Plotting coordinate values are initialized on plotProfil
            self.profiles[i]["plot_x"] = []
            self.profiles[i]["plot_y"] = []

        if plotProfil:
            self.plotProfil()

    def plotProfil(self, vertline=True):
        self.disableMouseCoordonates()

        self.removeClosedLayers(self.dockwidget.mdl)
        PlottingTool().clearData(self.dockwidget, self.profiles, self.dockwidget.plotlibrary)

        if vertline:  # Plotting vertical lines at the node of polyline draw
            PlottingTool().drawVertLine(
                self.dockwidget, self.pointstoDraw, self.dockwidget.plotlibrary
            )

        # calculate buffer geometries if search buffer is set in mdt layer
        geoms = []
        for i in range(0, self.dockwidget.mdl.rowCount()):
            if (
                self.dockwidget.mdl.item(i, 5).data(Qt.ItemDataRole.EditRole).type()
                == QgsMapLayer.VectorLayer
            ):
                _, buffer, multipoly = DataReaderTool().dataVectorReaderTool(
                    self.iface,
                    self.toolrenderer.tool,
                    self.profiles[i],
                    self.pointstoDraw,
                    float(self.dockwidget.mdl.item(i, 4).data(Qt.ItemDataRole.EditRole)),
                )
                geoms.append(buffer)
                geoms.append(multipoly)
        self.toolrenderer.setBufferGeometry(geoms)

        # Update coordinates to use in plot (height, slope %...)
        profile_func = profilers.PLOT_PROFILERS[self.dockwidget.plotComboBox.currentText()]

        for profile in self.profiles:
            profile["plot_x"], profile["plot_y"] = profile_func(profile)

        # plot profiles
        PlottingTool().attachCurves(
            self.dockwidget, self.profiles, self.dockwidget.mdl, self.dockwidget.plotlibrary
        )
        PlottingTool().reScalePlot(self.dockwidget, self.profiles, self.dockwidget.plotlibrary)
        # create tab with profile xy
        self.dockwidget.updateCoordinateTab()
        # Mouse tracking

        self.updateCursorOnMap(self.x_cursor)
        self.enableMouseCoordonates(self.dockwidget.plotlibrary)

    def setPointOnMap(self, x, y):
        self.x_cursor = x
        if self.pointstoDraw and self.doTracking:
            if x is not None:
                points = [QgsPointXY(*p) for p in self.pointstoDraw]
                geom = QgsGeometry.fromPolylineXY(points)
                try:
                    if len(points) > 1:
                        pointprojected = geom.interpolate(x).asPoint()
                    else:
                        pointprojected = points[0]
                except (IndexError, AttributeError, ValueError):
                    pointprojected = None

                if pointprojected:
                    try:
                        # test if self.pointLayer does not exist or layer was deleted
                        if not self.pointLayer:
                            pass
                    except:
                        self.pointLayer = None
                        layers = QgsProject.instance().mapLayersByName('profile_points')
                        if layers:
                            layer = layers[0]
                            hasFields = all(v in [f.name() for f in layer.fields()] for v in ['d','z'])
                            if hasFields and layer.type() == QgsMapLayer.VectorLayer and layer.geometryType() == QgsWkbTypes.PointGeometry:
                                self.pointLayer = layer
                            
                    if not self.pointLayer:
                        # create temporary profile point layer (horizontal distance=d, raster band value=z)
                        self.pointLayer = QgsVectorLayer("Point?field=z:double&field=d:double&index=yes&crs="+QgsProject.instance().crs().authid(),"profile_points","memory")
                        QgsProject.instance().addMapLayer(self.pointLayer)

                    print('D: '+str(x)+',Z: '+str(y)+', '+str(pointprojected))
                    provider = self.pointLayer.dataProvider()
                    feat = QgsFeature(self.pointLayer.fields())
                    feat.setGeometry(QgsGeometry.fromPointXY(pointprojected))
                    feat['z'] = y.item()
                    feat['d'] = x.item()
                    provider.addFeatures([feat])
                    self.pointLayer.updateExtents()
                    self.pointLayer.triggerRepaint()

    def updateCursorOnMap(self, x):
        self.x_cursor = x
        if self.pointstoDraw and self.doTracking:
            if x is not None:
                points = [QgsPointXY(*p) for p in self.pointstoDraw]
                geom = QgsGeometry.fromPolylineXY(points)
                try:
                    if len(points) > 1:
                        pointprojected = geom.interpolate(x).asPoint()
                    else:
                        pointprojected = points[0]
                except (IndexError, AttributeError, ValueError):
                    pointprojected = None

                if pointprojected:
                    self.toolrenderer.rubberbandpoint.setCenter(pointprojected)
            self.toolrenderer.rubberbandpoint.show()
        else:
            self.toolrenderer.rubberbandpoint.hide()

    # remove layers which were removed from QGIS
    def removeClosedLayers(self, model1):
        qgisLayerNames = [layer.name() for layer in self.instance.mapLayers().values()]

        for i in range(0, model1.rowCount()):
            layerName = model1.item(i, 2).data(Qt.ItemDataRole.EditRole)
            if layerName not in qgisLayerNames:
                self.dockwidget.removeLayer(i)
                self.removeClosedLayers(model1)
                break

    def cleaning(self):
        self.clearProfil()
        if self.toolrenderer:
            self.toolrenderer.cleaning()
        with suppress(AttributeError, RuntimeError, TypeError):
            self.instance.layersRemoved.disconnect()

    # ******************************************************************************************
    # **************************** mouse interaction *******************************************
    # ******************************************************************************************

    def activateMouseTracking(self, int1):
        if self.dockwidget.TYPE == "PyQtGraph":

            if int1 == 2:
                self.doTracking = True
            elif int1 == 0:
                self.doTracking = False

        elif self.dockwidget.TYPE == "Matplotlib":
            if int1 == 2:
                self.doTracking = True
                self.cid = self.dockwidget.plotWdg.mpl_connect(
                    "motion_notify_event", self.mouseevent_mpl
                )
            elif int1 == 0:
                self.doTracking = False
                with suppress(AttributeError, RuntimeError, TypeError):
                    self.dockwidget.plotWdg.mpl_disconnect(self.cid)
                try:
                    if self.vline:
                        self.dockwidget.plotWdg.figure.get_axes()[0].lines.remove(self.vline)
                        self.dockwidget.plotWdg.draw()
                except Exception as e:
                    print(str(e))

    def mouseevent_mpl(self, event):
        """
        case matplotlib library
        """
        if event.xdata:
            try:
                if self.vline:
                    self.dockwidget.plotWdg.figure.get_axes()[0].lines.remove(self.vline)
            except Exception:
                pass
            xdata = float(event.xdata)
            self.vline = self.dockwidget.plotWdg.figure.get_axes()[0].axvline(
                xdata, linewidth=2, color="k"
            )
            self.dockwidget.plotWdg.draw()
            self.updateCursorOnMap(xdata)

    def enableMouseCoordonates(self, library):
        if library == "PyQtGraph":
            self.dockwidget.plotWdg.scene().sigMouseMoved.connect(self.mouseMovedPyQtGraph)
            self.dockwidget.plotWdg.scene().sigMouseClicked.connect(self.mouseClickedPyQtGraph)
            self.dockwidget.plotWdg.getViewBox().autoRange(
                items=self.dockwidget.plotWdg.getPlotItem().listDataItems()
            )
            # self.dockwidget.plotWdg.getViewBox().sigRangeChanged.connect(self.dockwidget.plotRangechanged)
            self.dockwidget.connectPlotRangechanged()

    def mouseClickedPyQtGraph(self, event):
       pos = event.scenePos()
       if self.dockwidget.plotWdg.sceneBoundingRect().contains(pos) and self.dockwidget.showcursor:
            range = self.dockwidget.plotWdg.getViewBox().viewRange()
            # récupère le point souris à partir ViewBox
            mousePoint = self.dockwidget.plotWdg.getViewBox().mapSceneToView(pos)

            datas = []
            pitems = self.dockwidget.plotWdg.getPlotItem()
            ytoplot = None
            xtoplot = None

            if len(pitems.listDataItems()) > 0:
                # get data and nearest xy from cursor
                compt = 0
                try:
                    for item in pitems.listDataItems():
                        if item.isVisible():
                            x, y = item.getData()
                            nearestindex = np.argmin(abs(np.array(x, dtype=float) - mousePoint.x()))
                            if compt == 0:
                                xtoplot = np.array(x, dtype=float)[nearestindex]
                                ytoplot = np.array(y)[nearestindex]
                            else:
                                if abs(np.array(y)[nearestindex] - mousePoint.y()) < abs(ytoplot - mousePoint.y()):
                                    ytoplot = np.array(y)[nearestindex]
                                    xtoplot = np.array(x)[nearestindex]
                            compt += 1
                except (IndexError, ValueError):
                    ytoplot = None
                    xtoplot = None

                xtoplot = round(xtoplot,2)
                ytoplot = round(ytoplot,2)
                if not xtoplot in self.distancesPicked:
                    self.setPointOnMap(xtoplot,ytoplot)
                    self.distancesPicked.append(xtoplot)

    def disableMouseCoordonates(self):
        with suppress(AttributeError, RuntimeError, TypeError):
            self.dockwidget.plotWdg.scene().sigMouseMoved.disconnect(self.mouseMovedPyQtGraph)

        self.dockwidget.disconnectPlotRangechanged()

    def mouseMovedPyQtGraph(self, pos):
        # si connexion directe du signal "mouseMoved" : la fonction reçoit le point courant
        # si le point est dans la zone courante
        if self.dockwidget.plotWdg.sceneBoundingRect().contains(pos) and self.dockwidget.showcursor:
            range = self.dockwidget.plotWdg.getViewBox().viewRange()
            # récupère le point souris à partir ViewBox
            mousePoint = self.dockwidget.plotWdg.getViewBox().mapSceneToView(pos)

            pitems = self.dockwidget.plotWdg.getPlotItem()
            ytoplot = None
            xtoplot = None

            if len(pitems.listDataItems()) > 0:
                # get data and nearest xy from cursor
                compt = 0
                try:
                    for item in pitems.listDataItems():
                        if item.isVisible():
                            x, y = item.getData()
                            nearestindex = np.argmin(abs(np.array(x, dtype=float) - mousePoint.x()))
                            if compt == 0:
                                xtoplot = np.array(x, dtype=float)[nearestindex]
                                ytoplot = np.array(y)[nearestindex]
                            else:
                                if abs(np.array(y)[nearestindex] - mousePoint.y()) < abs(
                                    ytoplot - mousePoint.y()
                                ):
                                    ytoplot = np.array(y)[nearestindex]
                                    xtoplot = np.array(x)[nearestindex]
                            compt += 1
                except (IndexError, ValueError):
                    ytoplot = None
                    xtoplot = None
                # plot xy label and cursor
                if xtoplot is not None and ytoplot is not None:
                    for item in self.dockwidget.plotWdg.allChildItems():
                        if (
                            str(type(item))
                            == "<class 'profiletool.pyqtgraph.graphicsItems.InfiniteLine.InfiniteLine'>"  # noqa: E501
                        ):
                            if item.name() == "cross_vertical":
                                item.show()
                                item.setPos(xtoplot)
                            elif item.name() == "cross_horizontal":
                                item.show()
                                item.setPos(ytoplot)
                        elif (
                            str(type(item))
                            == "<class 'profiletool.pyqtgraph.graphicsItems.TextItem.TextItem'>"
                        ):
                            if item.textItem.toPlainText()[0] == "X":
                                item.show()
                                item.setText("X : " + str(round(xtoplot, 3)))
                                item.setPos(xtoplot, range[1][0])
                            elif item.textItem.toPlainText()[0] == "Y":
                                item.show()
                                item.setText("Y : " + str(round(ytoplot, 3)))
                                item.setPos(range[0][0], ytoplot)
            # tracking part
            self.updateCursorOnMap(xtoplot)
