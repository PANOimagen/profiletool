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
from qgis.PyQt.QtCore import QModelIndex, QObject, Qt, pyqtSignal
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import QColorDialog, QInputDialog, QMessageBox

# plugin import
from .plottingtool import PlottingTool
from .utils import isProfilable


class TableViewTool(QObject):

    layerAddedOrRemoved = pyqtSignal()  # Emitted when a new layer is added

    def addLayer(self, iface, mdl, layer1=None):
        if layer1 is None:
            templist = []
            j = 0
            # Ask the layer by a input dialog
            for i in range(0, iface.mapCanvas().layerCount()):
                donothing = False
                layer = iface.mapCanvas().layer(i)
                if isProfilable(layer):
                    for j in range(0, mdl.rowCount()):
                        if str(mdl.item(j, 2).data(Qt.UserRole.EditRole)) == str(layer.name()):
                            donothing = True
                else:
                    donothing = True

                if donothing is False:
                    templist += [[layer, layer.name()]]

            if len(templist) == 0:
                QMessageBox.warning(iface.mainWindow(), "Profile tool", "No raster to add")
                return
            else:
                testqt, ok = QInputDialog.getItem(
                    iface.mainWindow(),
                    "Layer selector",
                    "Choose layer",
                    [templist[k][1] for k in range(len(templist))],
                    False,
                )
                if ok:
                    for i in range(0, len(templist)):
                        if templist[i][1] == testqt:
                            layer2 = templist[i][0]
                else:
                    return
        else:
            if isProfilable(layer1):
                layer2 = layer1
            else:
                text = "Active layer is not a profilable layer."
                if layer1.type() == layer1.MeshLayer:
                    text += "\n(MeshLayer support requires QGis version 3.6 or newer.)"
                QMessageBox.warning(iface.mainWindow(), "Profile tool", text)
                return

        # Ask the Band by a input dialog
        # First, if isProfilable, considerate the real band number (instead of band + 1 for raster)
        if (
            layer2.type() == layer2.PluginLayer
            and isProfilable(layer2)
            or layer2.type() == layer2.MeshLayer
        ):
            self.bandoffset = 0
            typename = "parameter"
        elif layer2.type() == layer2.RasterLayer:
            self.bandoffset = 1
            typename = "band"
        elif layer2.type() == layer2.VectorLayer:
            self.bandoffset = 0
            typename = "field"

        if layer2.type() == layer2.RasterLayer and layer2.bandCount() != 1:
            listband = []
            for i in range(0, layer2.bandCount()):
                listband.append(str(i + self.bandoffset))
            testqt, ok = QInputDialog.getItem(
                iface.mainWindow(),
                typename.capitalize() + " selector",
                "Choose the " + typename,
                listband,
                False,
            )
            if ok:
                choosenBand = int(testqt) - self.bandoffset
            else:
                return 2
        elif layer2.type() == layer2.VectorLayer:
            fieldstemp = [field.name() for field in layer2.fields()]
            fields = [field.name() for field in layer2.fields() if field.isNumeric()]
            if len(fields) == 0:
                QMessageBox.warning(
                    iface.mainWindow(), "Profile tool", "Active layer is not a profilable layer"
                )
                return
            elif len(fields) == 1:
                choosenBand = fieldstemp.index(fields[0])

            else:
                try:
                    defaultfield = fieldstemp.index("z")
                except ValueError:
                    defaultfield = 2
                testqt, ok = QInputDialog.getItem(
                    iface.mainWindow(),
                    typename.capitalize() + " selector",
                    "Choose the " + typename,
                    fields,
                    defaultfield,
                )
                if ok:
                    choosenBand = fieldstemp.index(testqt)
                else:
                    return defaultfield
        elif (
            layer2.type() == layer2.PluginLayer
            and isProfilable(layer2)
            and layer2.LAYER_TYPE == "selafin_viewer"
        ):
            listparameterband = []
            listparametername = []
            for i in range(0, layer2.bandCount()):
                listparameterband.append(layer2.hydrauparser.parametres[i][0])
                listparametername.append(layer2.hydrauparser.parametres[i][1])
            defaultparam = 3
            testqt, ok = QInputDialog.getItem(
                iface.mainWindow(),
                typename.capitalize() + " selector",
                "Choose the " + typename,
                listparametername,
                defaultparam,
            )
            if ok:
                choosenBand = listparameterband[listparametername.index(testqt)]
            else:
                return defaultparam

        else:
            choosenBand = 0

        # Complete the tableview
        row = mdl.rowCount()
        mdl.insertRow(row)
        mdl.setData(mdl.index(row, 0, QModelIndex()), True, Qt.ItemDataRole.CheckStateRole)
        mdl.item(row, 0).setFlags(Qt.ItemFlag.ItemIsSelectable)
        lineColour = Qt.GlobalColor.red
        # QGis2
        if (
            (layer2.type() == layer2.PluginLayer and layer2.LAYER_TYPE == "crayfish_viewer")
            or (layer2.type() == layer2.PluginLayer and layer2.LAYER_TYPE == "selafin_viewer")
            or layer2.type() == layer2.MeshLayer
        ):
            lineColour = Qt.blue
        mdl.setData(
            mdl.index(row, 1, QModelIndex()), QColor(lineColour), Qt.ItemDataRole.BackgroundRole
        )
        mdl.item(row, 1).setFlags(Qt.ItemFlag.NoItemFlags)
        mdl.setData(mdl.index(row, 2, QModelIndex()), layer2.name())
        mdl.item(row, 2).setFlags(Qt.ItemFlag.NoItemFlags)
        if layer2.type() == layer2.PluginLayer and layer2.LAYER_TYPE == "selafin_viewer":
            mdl.setData(mdl.index(row, 3, QModelIndex()), choosenBand + self.bandoffset)
        else:
            mdl.setData(mdl.index(row, 3, QModelIndex()), choosenBand + self.bandoffset)
            mdl.item(row, 3).setFlags(Qt.ItemFlag.NoItemFlags)

        if layer2.type() == layer2.VectorLayer:
            mdl.setData(mdl.index(row, 4, QModelIndex()), 100.0)
        else:
            mdl.setData(mdl.index(row, 4, QModelIndex()), "")
            mdl.item(row, 4).setFlags(Qt.ItemFlag.NoItemFlags)

        mdl.setData(mdl.index(row, 5, QModelIndex()), layer2)
        mdl.item(row, 5).setFlags(Qt.ItemFlag.NoItemFlags)
        self.layerAddedOrRemoved.emit()

    def removeLayer(self, mdl, index):
        try:
            mdl.removeRow(index)
            self.layerAddedOrRemoved.emit()
        except Exception:
            return

    def chooseLayerForRemoval(self, iface, mdl):
        if mdl.rowCount() < 2:
            if mdl.rowCount() == 1:
                return 0
            return None

        list1 = []
        for i in range(0, mdl.rowCount()):
            list1.append(str(i + 1) + " : " + mdl.item(i, 2).data(Qt.ItemDataRole.EditRole))
        testqt, ok = QInputDialog.getItem(
            iface.mainWindow(), "Layer selector", "Choose the Layer", list1, False
        )
        if ok:
            for i in range(0, mdl.rowCount()):
                if testqt == (str(i + 1) + " : " + mdl.item(i, 2).data(Qt.ItemDataRole.EditRole)):
                    return i
        return None

    def onClick(self, iface, wdg, mdl, plotlibrary, index1):  # action when clicking the tableview
        temp = mdl.itemFromIndex(index1)
        if index1.column() == 1:  # modifying color
            name = ("%s#%d") % (
                mdl.item(index1.row(), 2).data(Qt.ItemDataRole.EditRole),
                mdl.item(index1.row(), 3).data(Qt.ItemDataRole.EditRole),
            )
            color = QColorDialog().getColor(temp.data(Qt.BackgroundRole))
            mdl.setData(
                mdl.index(temp.row(), 1, QModelIndex()), color, Qt.ItemDataRole.BackgroundRole
            )
            PlottingTool().changeColor(wdg, plotlibrary, color, name)
        elif index1.column() == 0:  # modifying checkbox
            # name = mdl.item(index1.row(),2).data(Qt.ItemDataRole.EditRole)
            name = ("%s#%d") % (
                mdl.item(index1.row(), 2).data(Qt.ItemDataRole.EditRole),
                mdl.item(index1.row(), 3).data(Qt.ItemDataRole.EditRole),
            )
            booltemp = temp.data(Qt.CheckStateRole)
            if booltemp is True:
                booltemp = False
            else:
                booltemp = True
            mdl.setData(
                mdl.index(temp.row(), 0, QModelIndex()), booltemp, Qt.ItemDataRole.CheckStateRole
            )
            PlottingTool().changeAttachCurve(wdg, plotlibrary, booltemp, name)
        elif (
            index1.column() == 3
            and mdl.item(index1.row(), 5).data(Qt.ItemDataRole.EditRole).type()
            == mdl.item(index1.row(), 5).data(Qt.ItemDataRole.EditRole).PluginLayer
            and mdl.item(index1.row(), 5).data(Qt.ItemDataRole.EditRole).LAYER_TYPE
            == "selafin_viewer"
        ):  # modifying selafin_viewer parameter
            layer = mdl.item(index1.row(), 5).data(Qt.ItemDataRole.EditRole)
            listparameterband = []
            listparametername = []
            for i in range(0, layer.bandCount()):
                listparameterband.append(layer.hydrauparser.parametres[i][0])
                listparametername.append(layer.hydrauparser.parametres[i][1])
            previousparam = int(mdl.item(index1.row(), 3).data(Qt.ItemDataRole.EditRole))
            testqt, ok = QInputDialog.getItem(
                iface.mainWindow(),
                "Parameter selector",
                "Choose the parameter",
                listparametername,
                previousparam,
            )
            if ok:
                choosenBand = listparameterband[listparametername.index(testqt)]
            else:
                choosenBand = previousparam
            mdl.setData(mdl.index(temp.row(), 3, QModelIndex()), choosenBand)
            self.layerAddedOrRemoved.emit()

        elif False and index1.column() == 4:
            # name = mdl.item(index1.row(),2).data(Qt.ItemDataRole.EditRole)
            name = mdl.item(index1.row(), 4).data(Qt.ItemDataRole.EditRole)
            print(name)

        else:
            return
