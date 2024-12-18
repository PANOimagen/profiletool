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
# with this progsram; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# ---------------------------------------------------------------------
import os
from math import sqrt

import numpy as np
from qgis.PyQt.QtCore import QSettings, Qt
from qgis.PyQt.QtWidgets import QFileDialog, QSizePolicy

from .. import pyqtgraph as pg
from ..dxfwrite import DXFEngine as dxf
from ..pyqtgraph import exporters

pg.setConfigOption("background", "w")


try:
    import matplotlib  # noqa:F401
    from matplotlib import rc  # noqa:F403,F401

    has_mpl = True
except ImportError:
    has_mpl = False


def getSaveFileName(parent, caption, directory, filter):
    """Qt4/Qt5 compatible getSaveFileName"""
    fileName = QFileDialog.getSaveFileName(
        parent=parent, caption=caption, directory=directory, filter=filter
    )
    if isinstance(fileName, tuple):  # pyqt5 case
        fileName = fileName[0]
    return fileName


class PlottingTool:
    """This class manages profile plotting.

    A call to changePlotWidget creates the widget where profiles will be
    plotted.
    Subsequent calls to functions on this class pass along the wdg object
    where profiles are to be plotted.
    Input data is the "profiles" vector, and the ["plot_x"] and ["plot_y"] values
    are used as the data series x and y values respectively.
    """

    def changePlotWidget(self, library, frame_for_plot):

        if library == "PyQtGraph":
            plotWdg = pg.PlotWidget()
            plotWdg.showGrid(True, True, 0.5)
            datavline = pg.InfiniteLine(
                0, angle=90, pen=pg.mkPen("r", width=1), name="cross_vertical"
            )
            datahline = pg.InfiniteLine(
                0, angle=0, pen=pg.mkPen("r", width=1), name="cross_horizontal"
            )
            plotWdg.addItem(datavline)
            plotWdg.addItem(datahline)
            # cursor
            xtextitem = pg.TextItem(
                "X : /",
                color=(0, 0, 0),
                border=pg.mkPen(color=(0, 0, 0), width=1),
                fill=pg.mkBrush("w"),
                anchor=(0, 1),
            )
            ytextitem = pg.TextItem(
                "Y : / ",
                color=(0, 0, 0),
                border=pg.mkPen(color=(0, 0, 0), width=1),
                fill=pg.mkBrush("w"),
                anchor=(0, 0),
            )
            plotWdg.addItem(xtextitem)
            plotWdg.addItem(ytextitem)

            plotWdg.getViewBox().autoRange(items=[])
            plotWdg.getViewBox().disableAutoRange()
            plotWdg.getViewBox().border = pg.mkPen(color=(0, 0, 0), width=1)

            return plotWdg

        elif library == "Matplotlib" and has_mpl:
            from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
            from matplotlib.figure import Figure

            fig = Figure(
                (1.0, 1.0),
                linewidth=0.0,
                subplotpars=matplotlib.figure.SubplotParams(
                    left=0, bottom=0, right=1, top=1, wspace=0, hspace=0
                ),
            )

            font = {"family": "arial", "weight": "normal", "size": 12}
            rc("font", **font)

            rect = fig.patch
            rect.set_facecolor((0.9, 0.9, 0.9))

            self.subplot = fig.add_axes((0.05, 0.15, 0.92, 0.82))
            self.subplot.set_xbound(0, 1000)
            self.subplot.set_ybound(0, 1000)
            self.manageMatplotlibAxe(self.subplot)
            canvas = FigureCanvasQTAgg(fig)
            sizePolicy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            sizePolicy.setHorizontalStretch(0)
            sizePolicy.setVerticalStretch(0)
            canvas.setSizePolicy(sizePolicy)
            return canvas

    def drawVertLine(self, wdg, pointstoDraw, library):
        if library == "PyQtGraph":
            pass
        elif library == "Matplotlib" and has_mpl:
            profileLen = 0
            for i in range(0, len(pointstoDraw) - 1):
                x1 = float(pointstoDraw[i][0])
                y1 = float(pointstoDraw[i][1])
                x2 = float(pointstoDraw[i + 1][0])
                y2 = float(pointstoDraw[i + 1][1])
                profileLen = sqrt(((x2 - x1) * (x2 - x1)) + ((y2 - y1) * (y2 - y1))) + profileLen
                wdg.plotWdg.figure.get_axes()[0].vlines(profileLen, 0, 1000, linewidth=1)
            profileLen = 0

    def attachCurves(self, wdg, profiles, model1, library):

        if library == "PyQtGraph":
            # cretae graph
            for i, profile in enumerate(profiles):
                tmp_name = ("%s#%d") % (profile["layer"].name(), profile["band"])
                # case line outside the raster
                y = np.array(profile["plot_y"], dtype=float)  # replace None value by np.nan
                x = np.array(profile["plot_x"])
                wdg.plotWdg.plot(
                    x,
                    y,
                    pen=pg.mkPen(model1.item(i, 1).data(Qt.ItemDataRole.BackgroundRole), width=2),
                    name=tmp_name,
                )
                # set it visible or not
                for item in wdg.plotWdg.getPlotItem().listDataItems():
                    if item.name() == tmp_name:
                        item.setVisible(model1.item(i, 0).data(Qt.ItemDataRole.CheckStateRole))

        elif library == "Matplotlib" and has_mpl:
            for i, profile in enumerate(profiles):
                tmp_name = ("%s#%d") % (profile["layer"].name(), profile["band"])
                if model1.item(i, 0).data(Qt.ItemDataRole.CheckStateRole):
                    wdg.plotWdg.figure.get_axes()[0].plot(
                        profile["plot_x"],
                        profile["plot_y"],
                        gid=tmp_name,
                        linewidth=3,
                        visible=True,
                    )
                else:
                    wdg.plotWdg.figure.get_axes()[0].plot(
                        profile["plot_x"],
                        profile["plot_y"],
                        gid=tmp_name,
                        linewidth=3,
                        visible=False,
                    )
                self.changeColor(
                    wdg,
                    "Matplotlib",
                    model1.item(i, 1).data(Qt.ItemDataRole.BackgroundRole),
                    tmp_name,
                )
            try:
                self.reScalePlot(wdg, profiles, library)
                wdg.plotWdg.figure.get_axes()[0].set_xbound(0, max(profiles[-1]["plot_x"]))
            except Exception:
                pass
            wdg.plotWdg.figure.get_axes()[0].redraw_in_frame()
            wdg.plotWdg.draw()

    def findMin(self, values):
        minVal = min(z for z in values if z is not None)
        return minVal

    def findMax(self, values):
        maxVal = max(z for z in values if z is not None)
        return maxVal

    def plotRangechanged(self, wdg, library):

        if library == "PyQtGraph":
            range = wdg.plotWdg.getViewBox().viewRange()
            wdg.disconnectYSpinbox()
            wdg.sbMaxVal.setValue(range[1][1])
            wdg.sbMinVal.setValue(range[1][0])
            wdg.connectYSpinbox()

    def reScalePlot(self, wdg, profiles, library, auto=False):  # called when spinbox value changed
        if profiles is None:
            return
        minimumValue = wdg.sbMinVal.value()
        maximumValue = wdg.sbMaxVal.value()

        y_vals = [p["plot_y"] for p in profiles]

        if minimumValue == maximumValue:
            # Automatic mode
            minimumValue = 1000000000
            maximumValue = -1000000000
            for i in range(0, len(y_vals)):
                if (
                    profiles[i]["layer"] is not None
                    and len([z for z in y_vals[i] if z is not None]) > 0
                ):
                    minimumValue = min(self.findMin(y_vals[i]), minimumValue)
                    maximumValue = max(self.findMax(y_vals[i]) + 1, maximumValue)
                    wdg.sbMaxVal.setValue(maximumValue)
                    wdg.sbMinVal.setValue(minimumValue)
                    wdg.sbMaxVal.setEnabled(True)
                    wdg.sbMinVal.setEnabled(True)

        if minimumValue < maximumValue:
            if library == "PyQtGraph":
                wdg.disconnectPlotRangechanged()
                if auto:
                    wdg.plotWdg.getViewBox().autoRange(
                        items=wdg.plotWdg.getPlotItem().listDataItems()
                    )
                    wdg.plotRangechanged()
                else:
                    wdg.plotWdg.getViewBox().setYRange(minimumValue, maximumValue, padding=0)
                wdg.connectPlotRangechanged()

            elif library == "Matplotlib" and has_mpl:
                if auto:
                    wdg.sbMaxVal.setValue(wdg.sbMinVal.value())
                    self.reScalePlot(wdg, profiles, library)
                else:
                    wdg.plotWdg.figure.get_axes()[0].set_ybound(minimumValue, maximumValue)
                    wdg.plotWdg.figure.get_axes()[0].redraw_in_frame()
                    wdg.plotWdg.draw()

    def clearData(self, wdg, profiles, library):  # erase one of profiles
        if not profiles:
            return

        if library == "PyQtGraph":
            pitems = wdg.plotWdg.getPlotItem().listDataItems()
            for item in pitems:
                wdg.plotWdg.removeItem(item)
            try:
                wdg.plotWdg.scene().sigMouseMoved.disconnect(self.mouseMoved)
            except Exception:
                pass

        elif library == "Matplotlib" and has_mpl:
            wdg.plotWdg.figure.get_axes()[0].cla()
            self.manageMatplotlibAxe(wdg.plotWdg.figure.get_axes()[0])
            # wdg.plotWdg.figure.get_axes()[0].redraw_in_frame()
            # wdg.plotWdg.draw()
        wdg.sbMaxVal.setEnabled(False)
        wdg.sbMinVal.setEnabled(False)
        wdg.sbMaxVal.setValue(0)
        wdg.sbMinVal.setValue(0)

    def changeColor(self, wdg, library, color1, name):  # Action when clicking the tableview - color

        if library == "PyQtGraph":
            pitems = wdg.plotWdg.getPlotItem()
            for i, item in enumerate(pitems.listDataItems()):
                if item.name() == name:
                    item.setPen(color1, width=2)

        elif library == "Matplotlib":
            temp1 = wdg.plotWdg.figure.get_axes()[0].get_lines()
            for i in range(len(temp1)):
                if name == str(temp1[i].get_gid()):
                    temp1[i].set_color(
                        (
                            color1.red() / 255.0,
                            color1.green() / 255.0,
                            color1.blue() / 255.0,
                            color1.alpha() / 255.0,
                        )
                    )
                    wdg.plotWdg.figure.get_axes()[0].redraw_in_frame()
                    wdg.plotWdg.figure.canvas.draw()
                    wdg.plotWdg.draw()
                    break

    def changeAttachCurve(
        self, wdg, library, bool, name
    ):  # Action when clicking the tableview - checkstate

        if library == "PyQtGraph":
            pitems = wdg.plotWdg.getPlotItem()
            for i, item in enumerate(pitems.listDataItems()):
                if item.name() == name:
                    if bool:
                        item.setVisible(True)
                    else:
                        item.setVisible(False)

        elif library == "Matplotlib":
            temp1 = wdg.plotWdg.figure.get_axes()[0].get_lines()
            for i in range(len(temp1)):
                if name == str(temp1[i].get_gid()):
                    if bool:
                        temp1[i].set_visible(True)
                    else:
                        temp1[i].set_visible(False)
                    wdg.plotWdg.figure.get_axes()[0].redraw_in_frame()
                    wdg.plotWdg.figure.canvas.draw()
                    wdg.plotWdg.draw()

                    break

    def manageMatplotlibAxe(self, axe1):
        axe1.grid()
        axe1.tick_params(
            axis="both",
            which="major",
            direction="out",
            length=10,
            width=1,
            bottom=True,
            top=False,
            left=True,
            right=False,
        )
        axe1.minorticks_on()
        axe1.tick_params(
            axis="both",
            which="minor",
            direction="out",
            length=5,
            width=1,
            bottom=True,
            top=False,
            left=True,
            right=False,
        )

    def outPrint(self, iface, wdg, mdl, library):
        # Postscript file rendering doesn't work properly yet.
        for i in range(0, mdl.rowCount()):
            if mdl.item(i, 0).data(Qt.ItemDataRole.CheckStateRole):
                name = str(mdl.item(i, 2).data(Qt.ItemDataRole.EditRole))
                # return
        fileName = getSaveFileName(
            iface.mainWindow(), "Save As", "Profile of " + name + ".ps", "PostScript Format (*.ps)"
        )
        if fileName:
            if library == "Matplotlib" and has_mpl:
                wdg.plotWdg.figure.savefig(str(fileName), bbox_inches="tight")

    def outPDF(self, iface, wdg, mdl, library):
        for i in range(0, mdl.rowCount()):
            if mdl.item(i, 0).data(Qt.ItemDataRole.CheckStateRole):
                name = str(mdl.item(i, 2).data(Qt.ItemDataRole.EditRole))
                break
        fileName = getSaveFileName(
            iface.mainWindow(),
            "Save As",
            "Profile of " + name + ".pdf",
            "Portable Document Format (*.pdf)",
        )
        if fileName:
            if library == "Matplotlib" and has_mpl:
                wdg.plotWdg.figure.savefig(str(fileName), bbox_inches="tight")

    def outSVG(self, iface, wdg, mdl, library):
        fileName = getSaveFileName(
            parent=iface.mainWindow(),
            caption="Save As",
            directory=wdg.profiletoolcore.loaddirectory,
            filter="Scalable Vector Graphics (*.svg)",
        )

        if fileName:
            wdg.profiletoolcore.loaddirectory = os.path.dirname(fileName)
            QSettings().setValue("profiletool/lastdirectory", wdg.profiletoolcore.loaddirectory)

            if library == "PyQtGraph":
                exporter = exporters.SVGExporter(wdg.plotWdg.getPlotItem().scene())
                # exporter =  pg.exporters.ImageExporter(wdg.plotWdg.getPlotItem()
                exporter.export(fileName=fileName)
            elif library == "Matplotlib" and has_mpl:
                wdg.plotWdg.figure.savefig(str(fileName), bbox_inches="tight")

    def outPNG(self, iface, wdg, mdl, library):
        fileName = getSaveFileName(
            parent=iface.mainWindow(),
            caption="Save As",
            directory=wdg.profiletoolcore.loaddirectory,
            # filter = "Profile of " + name + ".png",
            filter="Portable Network Graphics (*.png)",
        )

        if fileName:
            wdg.profiletoolcore.loaddirectory = os.path.dirname(fileName)
            QSettings().setValue("profiletool/lastdirectory", wdg.profiletoolcore.loaddirectory)

            if library == "PyQtGraph":
                exporter = exporters.ImageExporter(wdg.plotWdg.getPlotItem())
                exporter.export(fileName)
            elif library == "Matplotlib" and has_mpl:
                wdg.plotWdg.figure.savefig(str(fileName), bbox_inches="tight")

    def outDXF(self, iface, wdg, mdl, library, profiles, type="3D"):

        for i in range(0, mdl.rowCount()):
            if mdl.item(i, 0).data(Qt.ItemDataRole.CheckStateRole):
                name = str(mdl.item(i, 2).data(Qt.ItemDataRole.EditRole))
        fileName = getSaveFileName(
            parent=iface.mainWindow(),
            caption="Save As",
            directory=wdg.profiletoolcore.loaddirectory,
            # filter = "Profile of " + name + ".png",
            filter="dxf (*.dxf)",
        )
        if fileName:
            wdg.profiletoolcore.loaddirectory = os.path.dirname(fileName)
            QSettings().setValue("profiletool/lastdirectory", wdg.profiletoolcore.loaddirectory)

            drawing = dxf.drawing(fileName)
            for profile in profiles:
                name = profile["layer"].name()
                drawing.add_layer(name)
                if type == "2D":
                    points = [
                        (l, z, 0)
                        for l, z in zip(profile["l"], profile["z"])  # noqa: E74
                        if z is not None
                    ]
                else:
                    points = [
                        (x, y, z)
                        for x, y, z in zip(profile["x"], profile["y"], profile["z"])
                        if z is not None
                    ]
                drawing.add(dxf.polyline(points, color=7, layer=name))
            drawing.save()
