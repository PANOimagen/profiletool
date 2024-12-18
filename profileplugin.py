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
# with this progsram; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# ---------------------------------------------------------------------

from contextlib import suppress
from os import path

from qgis.core import QgsSettings
from qgis.PyQt.QtCore import QCoreApplication, QTranslator
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

from .tools.profiletool_core import ProfileToolCore


class ProfilePlugin:
    def __init__(self, iface):
        self.iface = iface
        self.canvas = iface.mapCanvas()

        # translation
        # initialize plugin directory
        self.plugin_dir = path.dirname(__file__)
        # initialize locale
        locale = QgsSettings().value("locale/userLocale", "en_US")[0:2]
        locale_path = path.join(self.plugin_dir, "i18n", f"profiletool_{locale}.qm")

        if path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        self.profiletool = None
        self.dockOpened = False  # remember for not reopening dock if there's already one opened
        self.canvas.mapToolSet.connect(self.mapToolChanged)

    def initGui(self):
        # create action
        self.action = QAction(
            QIcon(path.join(self.plugin_dir, "icons/profileIcon.png")),
            self.tr("Terrain profile"),
            self.iface.mainWindow(),
        )
        self.action.setWhatsThis(self.tr("Plots terrain profiles"))
        self.action.triggered.connect(self.run)
        self.aboutAction = QAction("About", self.iface.mainWindow())
        self.aboutAction.triggered.connect(self.about)
        # add toolbar button and menu item
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu("&Profile Tool", self.action)
        self.iface.addPluginToMenu("&Profile Tool", self.aboutAction)

    def unload(self):
        with suppress(AttributeError, RuntimeError, TypeError):
            self.profiletool.dockwidget.close()
            self.canvas.mapToolSet.disconnect(self.mapToolChanged)

        self.iface.removeToolBarIcon(self.action)
        self.iface.removePluginMenu("&Profile Tool", self.action)
        self.iface.removePluginMenu("&Profile Tool", self.aboutAction)

    def tr(self, message):
        return QCoreApplication.translate("ProfilePlugin", message)

    def run(self):

        if not self.dockOpened:
            # if self.profiletool is None:
            self.profiletool = ProfileToolCore(self.iface, self)
            self.iface.addDockWidget(
                self.profiletool.dockwidget.location, self.profiletool.dockwidget
            )
            self.profiletool.dockwidget.closed.connect(self.cleaning)
            self.dockOpened = True
            self.profiletool.activateProfileMapTool()
        else:
            self.profiletool.activateProfileMapTool()

    def cleaning(self):
        self.dockOpened = False
        self.profiletool.cleaning()
        if self.profiletool.toolrenderer:
            self.canvas.unsetMapTool(self.profiletool.toolrenderer.tool)
        self.canvas.setMapTool(self.profiletool.saveTool)
        self.iface.mainWindow().statusBar().showMessage("")

    def mapToolChanged(self, newtool, oldtool=None):
        pass
        # print('maptoolchanged',newtool,oldtool)

    def about(self):
        from .ui.dlgabout import DlgAbout

        DlgAbout(self.iface.mainWindow()).exec()
