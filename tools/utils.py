# -*- coding: utf-8 -*-
# -----------------------------------------------------------
#
# Profile
# Copyright (C) 2013  Peter Wells
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

from qgis.core import QgsWkbTypes


def isProfilable(layer):
    """Returns True if layer can be profiled, else returns False"""
    return (
        (layer.type() == layer.RasterLayer)
        or (layer.type() == layer.MeshLayer)
        or (layer.type() == layer.PluginLayer and layer.LAYER_TYPE == "selafin_viewer")
        or (layer.type() == layer.VectorLayer and layer.geometryType() == QgsWkbTypes.PointGeometry)
    )
