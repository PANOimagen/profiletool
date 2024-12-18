# -*- coding: utf-8 -*-
# -----------------------------------------------------------
#
# Profilers
# Copyright (C) 2017  Javier Becerra
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

import numpy as np


def height(p):
    """Return the height profile for given track p.

    Returns the x (distance from origin) and y (height)
    coordinates for the plot.
    """
    return p["l"], p["z"]


def slopes_pct(p):
    """Return a profile's slope in percentage.

    Returns the x (distance from origin) and y (slope in percentage)
    coordinates for the plot.
    """
    x = np.array(p["l"], dtype=float)
    y = np.array(p["z"], dtype=float)
    slope_pct = 100.0 * (y[1:] - y[:-1]) / (x[1:] - x[:-1])
    slope_pct = np.concatenate(
        (slope_pct[0:1], 0.5 * (slope_pct[1:] + slope_pct[:-1]), slope_pct[-1:])
    )
    slope_pct[np.isnan(slope_pct)] = 0
    slope_pct[np.isinf(slope_pct)] = 0
    return x, slope_pct


def slopes_deg(p):
    """Return a profile's slope in degrees.

    Returns the x (distance from origin) and y (slope in degrees)
    coordinates for the plot.
    """
    x, slope_pct = slopes_pct(p)
    slope_deg = np.degrees(np.arctan(slope_pct / 100.0))
    return x, slope_deg


PLOT_PROFILERS = {"Height": height, "Slope (%)": slopes_pct, "Slope (°)": slopes_deg}
