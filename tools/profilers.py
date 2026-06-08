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


# Default smoothing window (metres) when the UI doesn't supply one. The window
# tames the noise from a dense GPS track (elevation jitter + uneven spacing):
# 0 = raw, ~1 km reads as a clean line, ~2 km is very smooth.
DEFAULT_WINDOW_M = 1000.0


def _windowed_mean(x, y, window):
    """Distance-windowed moving average of y over +/- window/2, O(n)."""
    if window <= 0 or len(x) < 2:
        return y
    half = window / 2.0
    sy = np.concatenate(([0.0], np.cumsum(y)))
    lo = np.searchsorted(x, x - half, side="left")
    hi = np.searchsorted(x, x + half, side="right")
    return (sy[hi] - sy[lo]) / (hi - lo)


def height(p, window=0.0):
    """Elevation vs distance, optionally smoothed over a ``window``-metre
    moving average. Returns (x = distance, y = elevation)."""
    x = np.array(p["l"], dtype=float)
    y = np.array(p["z"], dtype=float)
    return x, _windowed_mean(x, y, window)


def slopes_pct(p, window=0.0):
    """Slope in percent vs distance.

    With ``window`` > 0 the slope at each point is the least-squares gradient of
    elevation vs distance over that distance window (O(n) via prefix sums) --
    necessary because adjacent-point slope on a dense GPS track is dominated by
    elevation jitter and tiny spacing. With ``window`` <= 0 it's the raw
    adjacent-point slope.
    """
    x = np.array(p["l"], dtype=float)
    y = np.array(p["z"], dtype=float)
    slope_pct = np.zeros_like(x)
    if len(x) < 2:
        return x, slope_pct

    if window <= 0:
        seg = 100.0 * (y[1:] - y[:-1]) / (x[1:] - x[:-1])
        slope_pct = np.concatenate((seg[0:1], 0.5 * (seg[1:] + seg[:-1]), seg[-1:]))
        slope_pct[~np.isfinite(slope_pct)] = 0
        return x, slope_pct

    half = window / 2.0
    sx = np.concatenate(([0.0], np.cumsum(x)))
    sy = np.concatenate(([0.0], np.cumsum(y)))
    sxx = np.concatenate(([0.0], np.cumsum(x * x)))
    sxy = np.concatenate(([0.0], np.cumsum(x * y)))
    # half-open window [lo, hi) of points within +/- half of each point
    lo = np.searchsorted(x, x - half, side="left")
    hi = np.searchsorted(x, x + half, side="right")
    cnt = hi - lo
    wx = sx[hi] - sx[lo]
    wy = sy[hi] - sy[lo]
    wxx = sxx[hi] - sxx[lo]
    wxy = sxy[hi] - sxy[lo]
    denom = cnt * wxx - wx * wx  # 0 when the window spans a single distance
    good = denom != 0
    slope_pct[good] = 100.0 * (cnt[good] * wxy[good] - wx[good] * wy[good]) / denom[good]
    return x, slope_pct


def slopes_deg(p, window=0.0):
    """Slope in degrees vs distance (derived from slopes_pct)."""
    x, slope_pct = slopes_pct(p, window)
    return x, np.degrees(np.arctan(slope_pct / 100.0))


PLOT_PROFILERS = {"Height": height, "Slope (%)": slopes_pct, "Slope (°)": slopes_deg}

# y-axis (label, unit) per profiler. unit is the SI unit for pyqtgraph's
# auto-scaling; None means "no SI scaling" -- the unit is baked into the label
# text instead (so "%"/"°" don't get nonsensical SI prefixes like "k%").
PLOT_PROFILERS_YAXIS = {
    "Height": ("Elevation", "m"),
    "Slope (%)": ("Slope (%)", None),
    "Slope (°)": ("Slope (°)", None),
}
