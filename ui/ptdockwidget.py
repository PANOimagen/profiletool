# -*- coding: utf-8 -*-
# -----------------------------------------------------------
#
# Profile
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

import os
from contextlib import suppress

from qgis.core import (
    QgsFeature,
    QgsField,
    QgsGeometry,
    QgsMapLayer,
    QgsPointXY,
    QgsProject,
    QgsVectorLayer,
)

# from qgis.gui import *
# from qgis.PyQt import QtCore, QtGui, uic
from qgis.PyQt import uic
from qgis.PyQt.QtCore import QModelIndex, Qt, QVariant, pyqtSignal
from qgis.PyQt.QtGui import QStandardItemModel
from qgis.PyQt.QtWidgets import (
    QApplication,
    QDockWidget,
    QGroupBox,
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
    QTableView,
    QVBoxLayout,
)

# plugin import
from ..tools.plottingtool import PlottingTool
from ..tools.tableviewtool import TableViewTool

try:
    import matplotlib  # noqa:F401
    from matplotlib import *  # noqa:F403,F401

    matplotlib_loaded = True
except ImportError:
    matplotlib_loaded = False


uiFilePath = os.path.abspath(os.path.join(os.path.dirname(__file__), "profiletool.ui"))
FormClass = uic.loadUiType(uiFilePath)[0]


class PTDockWidget(QDockWidget, FormClass):

    TITLE = "ProfileTool"
    TYPE = None

    closed = pyqtSignal()

    def __init__(self, iface1, profiletoolcore, parent=None):
        QDockWidget.__init__(self, parent)
        self.setupUi(self)
        self.profiletoolcore = profiletoolcore
        self.iface = iface1
        # Apperance
        self.location = Qt.DockWidgetArea.BottomDockWidgetArea
        minsize = self.minimumSize()
        maxsize = self.maximumSize()
        self.setMinimumSize(minsize)
        self.setMaximumSize(maxsize)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        # init scale widgets
        self.sbMaxVal.setValue(0)
        self.sbMinVal.setValue(0)
        self.sbMaxVal.setEnabled(False)
        self.sbMinVal.setEnabled(False)
        self.connectYSpinbox()

        # model
        self.mdl = QStandardItemModel(
            0, 6
        )  # the model whitch in are saved layers analysed caracteristics
        self.tableView.setModel(self.mdl)
        self.tableView.setColumnWidth(0, 20)
        self.tableView.setColumnWidth(1, 20)
        # self.tableView.setColumnWidth(2, 150)
        hh = self.tableView.horizontalHeader()
        hh.setStretchLastSection(True)
        self.tableView.setColumnHidden(5, True)
        self.mdl.setHorizontalHeaderLabels(
            ["", "", self.tr("Layer"), self.tr("Band/Field"), self.tr("Search buffer")]
        )
        self.tableViewTool = TableViewTool()

        # other
        self.addOptionComboboxItems()
        self.selectionmethod = 0
        self.plotlibrary = None  # The plotting library to use
        self.showcursor = True

        # Signals
        self.butSaveAs.clicked.connect(self.saveAs)
        self.tableView.clicked.connect(self._onClick)
        self.mdl.itemChanged.connect(self._onChange)
        self.pushButton_2.clicked.connect(self.addLayer)
        self.pushButton.clicked.connect(self.removeLayer)
        self.comboBox.currentIndexChanged.connect(self.selectionMethod)
        self.cboLibrary.currentIndexChanged.connect(self.changePlotLibrary)
        self.tableViewTool.layerAddedOrRemoved.connect(self.refreshPlot)
        self.pushButton_reinitview.clicked.connect(self.reScalePlot)
        self.checkBox_showcursor.stateChanged.connect(self.showCursor)
        self.fullResolutionCheckBox.stateChanged.connect(self.refreshPlot)
        self.profileInterpolationCheckBox.stateChanged.connect(self.refreshPlot)

        self.cbSameAxisScale.stateChanged.connect(self._onSameAxisScaleStateChanged)

    # ********************************************************************************
    # init things ****************************************************************
    # ********************************************************************************

    def addOptionComboboxItems(self):
        self.cboLibrary.addItem("PyQtGraph")
        if matplotlib_loaded:
            self.cboLibrary.addItem("Matplotlib")

    def selectionMethod(self, item):
        self.profiletoolcore.toolrenderer.setSelectionMethod(item)

        if self.iface.mapCanvas().mapTool() == self.profiletoolcore.toolrenderer.tool:
            self.iface.mapCanvas().setMapTool(self.profiletoolcore.toolrenderer.tool)
            self.profiletoolcore.toolrenderer.connectTool()

    def changePlotLibrary(self, item):
        self.plotlibrary = self.cboLibrary.itemText(item)
        self.addPlotWidget(self.plotlibrary)

        if self.plotlibrary == "PyQtGraph":
            self.checkBox_mpl_tracking.setEnabled(True)
            self.checkBox_showcursor.setEnabled(True)
            self.checkBox_mpl_tracking.setCheckState(Qt.CheckState.Checked)
            self.profiletoolcore.activateMouseTracking(2)
            self.checkBox_mpl_tracking.stateChanged.connect(
                self.profiletoolcore.activateMouseTracking
            )
            self._onSameAxisScaleStateChanged(self.cbSameAxisScale.checkState())

        elif self.plotlibrary == "Matplotlib":
            self.checkBox_mpl_tracking.setEnabled(True)
            self.checkBox_showcursor.setEnabled(False)
            self.checkBox_mpl_tracking.setCheckState(Qt.CheckState.Checked)
            self.profiletoolcore.activateMouseTracking(2)
            self.checkBox_mpl_tracking.stateChanged.connect(
                self.profiletoolcore.activateMouseTracking
            )
            self.cbSameAxisScale.setCheckState(Qt.CheckState.Unchecked)

        else:
            self.checkBox_mpl_tracking.setCheckState(0)
            self.checkBox_mpl_tracking.setEnabled(False)
            self.cbSameAxisScale.setCheckState(Qt.CheckState.Unchecked)

        self.cbSameAxisScale.setEnabled(self.plotlibrary == "PyQtGraph")

    def addPlotWidget(self, library):
        layout = self.frame_for_plot.layout()

        while layout.count():
            child = layout.takeAt(0)
            child.widget().deleteLater()

        if library == "PyQtGraph":
            self.stackedWidget.setCurrentIndex(0)
            self.plotWdg = PlottingTool().changePlotWidget("PyQtGraph", self.frame_for_plot)
            layout.addWidget(self.plotWdg)
            self.TYPE = "PyQtGraph"
            self.cbxSaveAs.clear()
            self.cbxSaveAs.addItems(
                ["Graph - PNG", "Graph - SVG", "3D line - DXF", "2D Profile - DXF"]
            )

        elif library == "Matplotlib":
            self.stackedWidget.setCurrentIndex(0)
            # self.widget_save_buttons.setVisible( False )
            self.plotWdg = PlottingTool().changePlotWidget("Matplotlib", self.frame_for_plot)
            layout.addWidget(self.plotWdg)
            self.TYPE = "Matplotlib"
            self.cbxSaveAs.clear()
            self.cbxSaveAs.addItems(
                [
                    "Graph - PDF",
                    "Graph - PNG",
                    "Graph - SVG",
                    "Graph - print (PS)",
                    "3D line - DXF",
                    "2D Profile - DXF",
                ]
            )

    # ********************************************************************************
    # graph things ****************************************************************
    # ********************************************************************************

    def connectYSpinbox(self):
        self.sbMinVal.valueChanged.connect(self.reScalePlot)
        self.sbMaxVal.valueChanged.connect(self.reScalePlot)

    def disconnectYSpinbox(self):
        with suppress(AttributeError, RuntimeError, TypeError):
            self.sbMinVal.valueChanged.disconnect(self.reScalePlot)
            self.sbMaxVal.valueChanged.disconnect(self.reScalePlot)

    def connectPlotRangechanged(self):
        self.plotWdg.getViewBox().sigRangeChanged.connect(self.plotRangechanged)

    def disconnectPlotRangechanged(self):
        with suppress(AttributeError, RuntimeError, TypeError):
            self.plotWdg.getViewBox().sigRangeChanged.disconnect(self.plotRangechanged)

    def plotRangechanged(self, param=None):  # called when pyqtgraph view changed
        PlottingTool().plotRangechanged(self, self.cboLibrary.currentText())

    def reScalePlot(self, param):  # called when a spinbox value changed
        if isinstance(param, bool):  # comes from button
            PlottingTool().reScalePlot(
                self, self.profiletoolcore.profiles, self.cboLibrary.currentText(), True
            )

        else:  # spinboxchanged
            if self.sbMinVal.value() == self.sbMaxVal.value() == 0:
                # don't execute it on init
                pass
            else:
                PlottingTool().reScalePlot(
                    self, self.profiletoolcore.profiles, self.cboLibrary.currentText()
                )

    def showCursor(self, int1):
        # For pyqtgraph mode
        if self.plotlibrary == "PyQtGraph":
            if int1 == 2:
                self.showcursor = True
                self.profiletoolcore.doTracking = bool(self.checkBox_mpl_tracking.checkState())
                self.checkBox_mpl_tracking.setEnabled(True)
                for item in self.plotWdg.allChildItems():
                    if (
                        str(type(item))
                        == "<class 'profiletool.pyqtgraph.graphicsItems.InfiniteLine.InfiniteLine'>"
                    ):
                        if item.name() == "cross_vertical":
                            item.show()
                        elif item.name() == "cross_horizontal":
                            item.show()
                    elif (
                        str(type(item))
                        == "<class 'profiletool.pyqtgraph.graphicsItems.TextItem.TextItem'>"
                    ):
                        if item.textItem.toPlainText()[0] == "X":
                            item.show()
                        elif item.textItem.toPlainText()[0] == "Y":
                            item.show()
            elif int1 == 0:
                self.showcursor = False
                self.profiletoolcore.doTracking = False
                self.checkBox_mpl_tracking.setEnabled(False)

                for item in self.plotWdg.allChildItems():
                    if (
                        str(type(item))
                        == "<class 'profiletool.pyqtgraph.graphicsItems.InfiniteLine.InfiniteLine'>"
                    ):
                        if item.name() == "cross_vertical":
                            item.hide()
                        elif item.name() == "cross_horizontal":
                            item.hide()
                    elif (
                        str(type(item))
                        == "<class 'profiletool.pyqtgraph.graphicsItems.TextItem.TextItem'>"
                    ):
                        if item.textItem.toPlainText()[0] == "X":
                            item.hide()
                        elif item.textItem.toPlainText()[0] == "Y":
                            item.hide()
            self.profiletoolcore.plotProfil()

    # ********************************************************************************
    # tablebiew things ****************************************************************
    # ********************************************************************************

    def addLayer(self, layer1=None):
        if isinstance(layer1, bool):  # comes from click
            layer1 = self.iface.activeLayer()

        self.tableViewTool.addLayer(self.iface, self.mdl, layer1)
        self.profiletoolcore.updateProfil(self.profiletoolcore.pointstoDraw, False)
        layer1.dataChanged.connect(self.refreshPlot)

    def removeLayer(self, index=None):
        if isinstance(index, bool):  # come from button
            index = self.tableViewTool.chooseLayerForRemoval(self.iface, self.mdl)

        if index is not None:
            layer = self.mdl.index(index, 4).data()
            with suppress(AttributeError, RuntimeError, TypeError):
                layer.dataChanged.disconnect(self.refreshPlot)
            self.tableViewTool.removeLayer(self.mdl, index)
        self.profiletoolcore.updateProfil(self.profiletoolcore.pointstoDraw, False, True)

    def refreshPlot(self):
        #
        #    Refreshes/updates the plot without requiring the user to
        #    redraw the plot line (rubberband)
        #
        self.profiletoolcore.updateProfil(self.profiletoolcore.pointstoDraw, False, True)

    def _onClick(self, index1):  # action when clicking the tableview
        self.tableViewTool.onClick(self.iface, self, self.mdl, self.plotlibrary, index1)

    def _onChange(self, item):
        if (
            not self.mdl.item(item.row(), 5) is None
            and item.column() == 4
            and self.mdl.item(item.row(), 5).data(Qt.EditRole).type()
            == QgsMapLayer.LayerType.VectorLayer
        ):

            self.profiletoolcore.plotProfil()

    def _onSameAxisScaleStateChanged(self, state):
        """
        Called whenever the checkbox button for same scale axis status has changed
        if checked, plot will always keep same scale on both axis (aspect ratio of 1)

        Only supported with PyQtGraph
        """

        if self.plotlibrary == "PyQtGraph":
            self.plotWdg.getViewBox().setAspectLocked(state == Qt.CheckState.Checked)

    # ********************************************************************************
    # coordinate tab ****************************************************************
    # ********************************************************************************
    @staticmethod
    def _profile_name(profile):
        groupTitle = profile["layer"].name()
        band = profile["band"]
        if band is not None and band > -1:
            groupTitle += "_band_{}".format(band)
        return groupTitle.replace(" ", "_")

    def updateCoordinateTab(self):

        try:  # Reinitializing the table tab
            self.VLayout = self.scrollAreaWidgetContents.layout()
            while 1:
                child = self.VLayout.takeAt(0)
                if not child:
                    break
                child.widget().deleteLater()
        except Exception:
            self.VLayout = QVBoxLayout(self.scrollAreaWidgetContents)
            self.VLayout.setContentsMargins(9, -1, -1, -1)
        # Setup the table tab
        self.groupBox = []
        self.profilePushButton = []
        self.coordsPushButton = []
        self.tolayerPushButton = []
        self.tableView = []
        self.verticalLayout = []
        if self.mdl.rowCount() != self.profiletoolcore.profiles:
            # keep the number of profiles and the model in sync.
            self.profiletoolcore.updateProfil(self.profiletoolcore.pointstoDraw, False, False)
        for i in range(0, self.mdl.rowCount()):
            self.groupBox.append(QGroupBox(self.scrollAreaWidgetContents))
            sizePolicy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self.groupBox[i].setSizePolicy(sizePolicy)
            profileTitle = self._profile_name(self.profiletoolcore.profiles[i])

            self.groupBox[i].setTitle(
                QApplication.translate("GroupBox" + str(i), profileTitle, None)
            )
            self.groupBox[i].setObjectName("groupBox" + str(i))

            self.verticalLayout.append(QVBoxLayout(self.groupBox[i]))
            self.verticalLayout[i].setObjectName("verticalLayout")
            # The table
            self.tableView.append(QTableView(self.groupBox[i]))
            sizePolicy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self.tableView[i].setSizePolicy(sizePolicy)
            self.tableView[i].setObjectName("tableView" + str(i))
            # font = QFont("Arial", 8)
            column = len(self.profiletoolcore.profiles[i]["l"])
            self.mdl2 = QStandardItemModel(2, column)
            for j in range(len(self.profiletoolcore.profiles[i]["l"])):
                self.mdl2.setData(
                    self.mdl2.index(0, j, QModelIndex()), self.profiletoolcore.profiles[i]["l"][j]
                )
                # self.mdl2.setData(self.mdl2.index(0, j, QModelIndex())  ,font ,QtCore.Qt.FontRole)
                self.mdl2.setData(
                    self.mdl2.index(1, j, QModelIndex()), self.profiletoolcore.profiles[i]["z"][j]
                )
                # self.mdl2.setData(self.mdl2.index(1, j, QModelIndex())  ,font ,QtCore.Qt.FontRole)
            self.tableView[i].verticalHeader().setDefaultSectionSize(18)
            self.tableView[i].horizontalHeader().setDefaultSectionSize(60)
            self.tableView[i].setModel(self.mdl2)
            # 2 * header (1 header + 1 horz slider) + nrows + a small margin
            minTableHeight = (
                2 * self.tableView[i].horizontalHeader().height()
                + sum(
                    self.tableView[i].rowHeight(j)
                    for j in range(self.tableView[i].model().rowCount())
                )
                + 6
            )  # extra safety margin
            self.tableView[i].setMinimumHeight(minTableHeight)

            self.verticalLayout[i].addWidget(self.tableView[i])

            self.horizontalLayout = QHBoxLayout()

            # the copy to clipboard button
            self.profilePushButton.append(QPushButton(self.groupBox[i]))
            sizePolicy = QSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding
            )
            self.profilePushButton[i].setSizePolicy(sizePolicy)
            self.profilePushButton[i].setText(
                QApplication.translate("GroupBox", "Copy to clipboard", None)
            )
            self.profilePushButton[i].setObjectName(str(i))
            self.horizontalLayout.addWidget(self.profilePushButton[i])

            # button to copy to clipboard with coordinates
            self.coordsPushButton.append(QPushButton(self.groupBox[i]))
            sizePolicy = QSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding
            )
            self.coordsPushButton[i].setSizePolicy(sizePolicy)
            self.coordsPushButton[i].setText(
                QApplication.translate("GroupBox", "Copy to clipboard (with coordinates)", None)
            )

            # button to copy to clipboard with coordinates
            self.tolayerPushButton.append(QPushButton(self.groupBox[i]))
            sizePolicy = QSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding
            )
            self.tolayerPushButton[i].setSizePolicy(sizePolicy)
            self.tolayerPushButton[i].setText(
                QApplication.translate("GroupBox", "Create Temporary layer", None)
            )

            self.coordsPushButton[i].setObjectName(str(i))
            self.horizontalLayout.addWidget(self.coordsPushButton[i])

            self.tolayerPushButton[i].setObjectName(str(i))
            self.horizontalLayout.addWidget(self.tolayerPushButton[i])

            self.horizontalLayout.addStretch(0)
            self.verticalLayout[i].addLayout(self.horizontalLayout)

            self.VLayout.addWidget(self.groupBox[i])

            self.profilePushButton[i].clicked.connect(self.copyTable)
            self.coordsPushButton[i].clicked.connect(self.copyTableAndCoords)
            self.tolayerPushButton[i].clicked.connect(self.createTemporaryLayer)

    def copyTable(self):  # Writing the table to clipboard in excel form
        nr = int(self.sender().objectName())
        self.clipboard = QApplication.clipboard()
        text = ""
        for i in range(len(self.profiletoolcore.profiles[nr]["l"])):
            text += (
                str(self.profiletoolcore.profiles[nr]["l"][i])
                + "\t"
                + str(self.profiletoolcore.profiles[nr]["z"][i])
                + "\n"
            )
        self.clipboard.setText(text)

    def copyTableAndCoords(self):  # Writing the table with coordinates to clipboard in excel form
        nr = int(self.sender().objectName())
        self.clipboard = QApplication.clipboard()
        text = ""
        for i in range(len(self.profiletoolcore.profiles[nr]["l"])):
            text += (
                str(self.profiletoolcore.profiles[nr]["l"][i])
                + "\t"
                + str(self.profiletoolcore.profiles[nr]["x"][i])
                + "\t"
                + str(self.profiletoolcore.profiles[nr]["y"][i])
                + "\t"
                + str(self.profiletoolcore.profiles[nr]["z"][i])
                + "\n"
            )
        self.clipboard.setText(text)

    def createTemporaryLayer(self):
        nr = int(self.sender().objectName())
        type = "Point?crs=" + str(self.profiletoolcore.profiles[nr]["layer"].crs().authid())
        name = "ProfileTool_{}".format(self._profile_name(self.profiletoolcore.profiles[nr]))
        vl = QgsVectorLayer(type, name, "memory")
        pr = vl.dataProvider()
        vl.startEditing()
        # add fields
        pr.addAttributes([QgsField("Value", QVariant.Double)])
        vl.updateFields()
        # Add features to layer
        for i in range(len(self.profiletoolcore.profiles[nr]["l"])):
            fet = QgsFeature(vl.fields())
            # set geometry
            fet.setGeometry(
                QgsGeometry.fromPointXY(
                    QgsPointXY(
                        self.profiletoolcore.profiles[nr]["x"][i],
                        self.profiletoolcore.profiles[nr]["y"][i],
                    )
                )
            )
            # set attributes
            fet.setAttributes([self.profiletoolcore.profiles[nr]["z"][i]])
            pr.addFeatures([fet])
        vl.commitChanges()
        # labeling/enabled
        if False:
            labelsettings = vl.labeling().settings()
            labelsettings.enabled = True

        # vl.setCustomProperty("labeling/enabled", "true")
        # show layer
        QgsProject.instance().addMapLayer(vl)

    # ********************************************************************************
    # other things ****************************************************************
    # ********************************************************************************

    def closeEvent(self, event):
        self.closed.emit()
        self.profiletoolcore.cleaning()
        # self.butSaveAs.clicked.disconnect(self.saveAs)
        # return QDockWidget.closeEvent(self, event)

    # generic save as button
    def saveAs(self):
        idx = self.cbxSaveAs.currentText()
        if idx == "Graph - PDF":
            self.outPDF()
        elif idx == "Graph - PNG":
            self.outPNG()
        elif idx == "Graph - SVG":
            self.outSVG()
        elif idx == "Graph - print (PS)":
            self.outPrint()
        elif idx == "3D line - DXF":
            self.outDXF("3D")
        elif idx == "2D Profile - DXF":
            self.outDXF("2D")
        else:
            print("plottingtool: invalid index " + str(idx))

    def outPrint(self):  # Postscript file rendering doesn't work properly yet.
        PlottingTool().outPrint(self.iface, self, self.mdl, self.cboLibrary.currentText())

    def outPDF(self):
        PlottingTool().outPDF(self.iface, self, self.mdl, self.cboLibrary.currentText())

    def outSVG(self):
        PlottingTool().outSVG(self.iface, self, self.mdl, self.cboLibrary.currentText())

    def outPNG(self):
        PlottingTool().outPNG(self.iface, self, self.mdl, self.cboLibrary.currentText())

    def outDXF(self, type):
        PlottingTool().outDXF(
            self.iface,
            self,
            self.mdl,
            self.cboLibrary.currentText(),
            self.profiletoolcore.profiles,
            type,
        )
