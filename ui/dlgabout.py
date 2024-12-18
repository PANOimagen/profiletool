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
import platform

from qgis.PyQt import uic
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import QDialog

uiFilePath = os.path.abspath(os.path.join(os.path.dirname(__file__), "about.ui"))
FormClass = uic.loadUiType(uiFilePath)[0]


class DlgAbout(QDialog, FormClass):
    def __init__(self, parent=None):
        QDialog.__init__(self, parent)
        self.setupUi(self)

        fp = os.path.join(
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..")), "metadata.txt"
        )

        iniText = QSettings(fp, QSettings.IniFormat)
        verno = iniText.value("version")
        name = iniText.value("name")
        description = iniText.value("description")

        self.title.setText(name)
        self.description.setText(description + " - " + verno)
