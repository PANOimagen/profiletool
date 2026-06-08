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
import platform
from math import sqrt

import numpy as np
import qgis
from qgis.core import *
from qgis.PyQt.QtCore import QCoreApplication

from .utils import isProfilable


# --- Vector profile memo ---------------------------------------------------
# One user action recomputes the same profile several times (updateProfil is
# re-entered with identical inputs). Memoize per layer, dropped on data change.
_VECTOR_PROFILE_CACHE = {}  # layer_id -> (signature, (profile, buffergeom, multipoly))
_VECTOR_CACHE_WIRED = set()  # layer_ids whose invalidation signals are connected


def _invalidateVectorCache(layer_id):
    _VECTOR_PROFILE_CACHE.pop(layer_id, None)


def _wireProfileCacheInvalidation(layer):
    """Drop the memoized profile whenever the layer's data changes."""
    lid = layer.id()
    if lid in _VECTOR_CACHE_WIRED:
        return
    for signal in (
        layer.dataChanged,
        layer.attributeValueChanged,
        layer.geometryChanged,
        layer.featureAdded,
        layer.featuresDeleted,
    ):
        signal.connect(lambda *a, lid=lid: _invalidateVectorCache(lid))
    layer.willBeDeleted.connect(
        lambda lid=lid: (
            _invalidateVectorCache(lid),
            _VECTOR_CACHE_WIRED.discard(lid),
        )
    )
    _VECTOR_CACHE_WIRED.add(lid)


def _pointXY(feat):
    geom = feat.geometry()
    if geom.isEmpty():
        return (float("nan"), float("nan"))
    p = geom.asPoint()
    return (p.x(), p.y())


def readPointFeatures(layer):
    """Read all point features and their layer-CRS coordinates.

    Returns (features, xs, ys) where xs/ys are numpy arrays, used for a
    vectorized bounding-box prefilter and to build the projection points
    without constructing a QgsGeometry per candidate. Null-geometry features
    get NaN coordinates so they fall out of any bbox test.
    """
    feats = list(layer.getFeatures())
    coords = [_pointXY(f) for f in feats]
    xs = np.array([c[0] for c in coords], dtype=float)
    ys = np.array([c[1] for c in coords], dtype=float)
    return feats, xs, ys


def lineSegmentDistances(lx, ly, layer_crs):
    """Per-segment and cumulative ellipsoidal ground distance (metres) along a
    polyline given as layer-CRS coordinate arrays.

    Measuring on the ellipsoid makes the profile x-axis a true ground distance
    regardless of the layer CRS, rather than raw CRS units -- e.g. degrees for a
    geographic CRS like EPSG:4326, where Euclidean coordinate distance is
    meaningless.
    """
    da = QgsDistanceArea()
    da.setSourceCrs(layer_crs, QgsProject.instance().transformContext())
    ellipsoid = QgsProject.instance().ellipsoid()
    da.setEllipsoid(ellipsoid if ellipsoid and ellipsoid != "NONE" else "WGS84")

    n = len(lx)
    seg_len = np.empty(max(n - 1, 0), dtype=float)
    for i in range(n - 1):
        seg_len[i] = da.measureLine(
            QgsPointXY(lx[i], ly[i]), QgsPointXY(lx[i + 1], ly[i + 1])
        )
    return seg_len, np.concatenate(([0.0], np.cumsum(seg_len)))


class DataReaderTool:
    """def __init__(self):
    self.profiles = None"""

    def dataRasterReaderTool(self, iface1, tool1, profile1, pointstoDraw1, resolution_mode):
        """
        Return a dictionnary : {"layer" : layer read,
                                "band" : band read,
                                "l" : array of computed lenght,
                                "z" : array of computed z
        """
        # init
        self.tool = tool1  # needed to transform point coordinates
        self.profiles = profile1  # profile with layer and band to compute
        self.pointstoDraw = pointstoDraw1  # the polyline to compute
        self.iface = iface1  # QGis interface to show messages in status bar

        distance = qgis.core.QgsDistanceArea()

        # Get the values on the lines
        l = []
        z = []
        x = []
        y = []
        lbefore = 0
        # First create the list of x and y coordinates along the path
        # Also store distance projected on map.
        # work for each segment of polyline
        first_segment = True
        for p_start, p_end in zip(self.pointstoDraw[:-1], self.pointstoDraw[1:]):

            # for each polylines, set points x,y with map crs (%D) and layer crs (%C)
            pointstoCal1 = self.tool.toLayerCoordinates(
                self.profiles["layer"], QgsPointXY(*p_start)
            )
            pointstoCal2 = self.tool.toLayerCoordinates(self.profiles["layer"], QgsPointXY(*p_end))
            x1D = float(p_start[0])
            y1D = float(p_start[1])
            x2D = float(p_end[0])
            y2D = float(p_end[1])
            x1C = float(pointstoCal1.x())
            y1C = float(pointstoCal1.y())
            x2C = float(pointstoCal2.x())
            y2C = float(pointstoCal2.y())
            # lenght between (x1,y1) and (x2,y2)
            tlC = sqrt(((x2C - x1C) * (x2C - x1C)) + ((y2C - y1C) * (y2C - y1C)))
            # Set the res of calcul
            try:
                res = (
                    min(
                        self.profiles["layer"].rasterUnitsPerPixelX(),
                        self.profiles["layer"].rasterUnitsPerPixelY(),
                    )
                    * tlC
                    / max(abs(x2C - x1C), abs(y2C - y1C))
                )  # res depend on the angle of ligne with normal
            except ZeroDivisionError:
                res = (
                    min(
                        self.profiles["layer"].rasterUnitsPerPixelX(),
                        self.profiles["layer"].rasterUnitsPerPixelY(),
                    )
                    * 1.2
                )
            except AttributeError:
                # MeshLayers have no rasterUnitsPerPixelX/Y attribute
                res = 1
            # enventually use bigger step, wether full res is selected or not
            if resolution_mode == "samples":
                """Only take values at sample points, no intermediate values."""
                steps = 1
            else:
                if res != 0:
                    """Use the map's resolution."""
                    steps = int(tlC / res)
                    if resolution_mode == "limited":
                        """Hard coded limit to 1000 points per segment."""
                        steps = min(steps, 1000)
                else:
                    steps = 1000

            if steps < 1:
                steps = 1
            # calculate dx, dy and dl for one step
            dxD = (x2D - x1D) / steps
            dyD = (y2D - y1D) / steps
            dlD = sqrt((dxD * dxD) + (dyD * dyD))
            dxC = (x2C - x1C) / steps
            dyC = (y2C - y1C) / steps
            # dlC = sqrt ((dxC*dxC) + (dyC*dyC))
            # reading data
            if first_segment:
                debut = 0
                first_segment = False
            else:
                debut = 1
            for n in range(debut, steps + 1):
                xC = x1C + dxC * n
                yC = y1C + dyC * n
                lD = dlD * n + lbefore
                x.append(xC)
                y.append(yC)
                l.append(lD)
            lbefore = l[-1]
        # Extract the profile for the whole path
        z = self._extractZValues(x, y)

        # End of polyline analysis
        # filling the main data dictionary "profiles"
        self.profiles["l"] = l
        self.profiles["z"] = z
        self.profiles["x"] = x
        self.profiles["y"] = y
        self.iface.mainWindow().statusBar().showMessage("")

        return self.profiles

    def _status_update(self, advancement_pct):
        """Send a progress message to status bar.

        advancement_pct is the advancemente in percentage (from 0 to 100).
        """
        if advancement_pct % 10 == 0:
            progress = "Creating profile: " + "|" * (advancement_pct // 10)
            self.iface.mainWindow().statusBar().showMessage(progress)

    def _extractZValues(self, x, y):
        # Initialize message bar...

        layer = self.profiles["layer"]
        choosenBand = self.profiles["band"]

        z = []
        if layer.type() == layer.PluginLayer and isProfilable(layer):
            for n, coords in enumerate(zip(x, y)):
                ident = layer.identify(QgsPointXY(*coords))
                try:
                    attr = float(list(ident[1].values())[choosenBand])
                except:
                    attr = 0
                z.append(attr)
                self._status_update((100 * n) // (len(x) - 1))
        elif layer.type() == layer.MeshLayer:
            identifier = qgis.gui.QgsMapToolIdentify(qgis.utils.iface.mapCanvas())
            meshFld = QCoreApplication.translate("QgsMapToolIdentify", "Scalar Value")
            for n, coords in enumerate(zip(x, y)):
                ident = identifier.identify(
                    QgsGeometry.fromPointXY(QgsPointXY(*coords)),
                    qgis.gui.QgsMapToolIdentify.DefaultQgsSetting,
                    [layer],
                    qgis.gui.QgsMapToolIdentify.MeshLayer,
                )[0]

                try:
                    attr = float(ident.mAttributes[meshFld])
                except (AttributeError, ValueError):
                    attr = 0
                z.append(attr)
                self._status_update((100 * n) // (len(x) - 1))
        else:  # RASTER LAYERS
            for n, coords in enumerate(zip(x, y)):
                # this code adapted from valuetool plugin
                ident = layer.dataProvider().identify(
                    QgsPointXY(*coords), QgsRaster.IdentifyFormat.IdentifyFormatValue
                )
                # if ident is not None and ident.has_key(choosenBand+1):
                if ident is not None and (choosenBand in ident.results()):
                    attr = ident.results()[choosenBand]
                else:
                    attr = 0
                z.append(attr)
                self._status_update((100 * n) // (len(x) - 1))
        return z

    def dataVectorReaderTool(self, iface1, tool1, profile1, pointstoDraw1, valbuf1):
        """
        compute the projected points
        return :
            self.buffergeom : the qgsgeometry of the buffer
            self.projectedpoints : [..., [(point caracteristics : )
                                          #index : descripion
                                          #0 : the pk of the projected point relative to line
                                          #1 : the x coordinate of the projected point
                                          #2 : the y coordinate of the projected point
                                          #3 : the lenght between original point and projected point else -1 if interpolated
                                          #4 : the segment of the polyline on which the point is projected
                                          #5 : the interp value if interpfield>-1, else None
                                          #6 : the x coordinate of the original point if the point is not interpolated, else None
                                          #6 : the y coordinate of the original point if the point is not interpolated, else None
                                          #6 : the feature the original point if the point is not interpolated, else None],
                                           ...]
        Return a dictionnary : {"layer" : layer read,
                                "band" : band read,
                                "l" : array of computed lenght,
                                "z" : array of computed z


        """
        layercrs = profile1["layer"].crs()
        mapcanvascrs = qgis.utils.iface.mapCanvas().mapSettings().destinationCrs()

        valbuffer = valbuf1

        # Result memo (see module top): return the cached result for identical
        # (drawn line, band, buffer) inputs instead of recomputing.
        _lid = profile1["layer"].id()
        _sig = (tuple(map(tuple, pointstoDraw1)), profile1["band"], valbuffer)
        _cached = _VECTOR_PROFILE_CACHE.get(_lid)
        if _cached is not None and _cached[0] == _sig:
            _prof, _buf, _multi = _cached[1]
            return dict(_prof), _buf, _multi

        projectedpoints = []
        buffergeom = None

        sourceCrs = QgsCoordinateReferenceSystem(
            qgis.utils.iface.mapCanvas().mapSettings().destinationCrs()
        )
        destCrs = QgsCoordinateReferenceSystem(profile1["layer"].crs())
        if qgis.core.Qgis.QGIS_VERSION[0] > "2":
            # In QGIS 3 QgsCoordinateTransform needs a QgsCoordinateTransformContext
            xform = QgsCoordinateTransform(sourceCrs, destCrs, QgsProject.instance())
            xformrev = QgsCoordinateTransform(destCrs, sourceCrs, QgsProject.instance())
        else:
            xform = QgsCoordinateTransform(sourceCrs, destCrs)
            xformrev = QgsCoordinateTransform(destCrs, sourceCrs)

        geom = qgis.core.QgsGeometry.fromPolylineXY(
            [QgsPointXY(point[0], point[1]) for point in pointstoDraw1]
        )

        geominlayercrs = qgis.core.QgsGeometry(geom)
        tempresult = geominlayercrs.transform(xform)

        buffergeom = geom.buffer(valbuffer, 12)
        buffergeominlayercrs = qgis.core.QgsGeometry(buffergeom)
        tempresult = buffergeominlayercrs.transform(xform)

        feats, xs, ys = readPointFeatures(profile1["layer"])

        # Vectorized bounding-box prefilter on the cached coordinates.
        bbox = buffergeominlayercrs.boundingBox()
        mask = (
            (xs >= bbox.xMinimum())
            & (xs <= bbox.xMaximum())
            & (ys >= bbox.yMinimum())
            & (ys <= bbox.yMaximum())
        )
        candidates = np.nonzero(mask)[0]

        # Precompute the profile line's segments once for a vectorized
        # point-to-polyline projection. The drawn line can carry thousands of
        # vertices, so a per-point GEOS distance/lineLocatePoint/interpolate is
        # prohibitive; numpy over the segment arrays does it in one pass.
        poly = geominlayercrs.asPolyline()
        lx = np.array([p.x() for p in poly])
        ly = np.array([p.y() for p in poly])
        seg_ax = lx[:-1]
        seg_ay = ly[:-1]
        seg_dx = lx[1:] - seg_ax
        seg_dy = ly[1:] - seg_ay
        seg_len2 = seg_dx * seg_dx + seg_dy * seg_dy
        seg_len2_safe = np.where(seg_len2 == 0.0, 1.0, seg_len2)  # avoid /0 on dupes
        # Along-line distance in metres (ellipsoidal): the projection below finds
        # the nearest point in coordinate space, but distance-along-line (the
        # x-axis) is measured on the ellipsoid so it's a true ground distance,
        # not raw CRS units (e.g. degrees for EPSG:4326).
        seg_len, seg_cum = lineSegmentDistances(lx, ly, profile1["layer"].crs())

        for _idx in candidates:
            px = xs[_idx]
            py = ys[_idx]
            # Project onto every segment (clamped), pick the nearest: gives
            # distance-to-line, distance-along-line and the foot point at once.
            t = np.clip(
                ((px - seg_ax) * seg_dx + (py - seg_ay) * seg_dy) / seg_len2_safe, 0.0, 1.0
            )
            footx = seg_ax + t * seg_dx
            footy = seg_ay + t * seg_dy
            d2 = (px - footx) ** 2 + (py - footy) ** 2
            j = int(np.argmin(d2))
            distpoint = float(np.sqrt(d2[j]))
            if distpoint <= valbuffer:
                distline = float(seg_cum[j] + t[j] * seg_len[j])
                featPnt = feats[_idx]
                if profile1["band"] > -1:
                    try:
                        interptemp = float(featPnt[profile1["band"]])
                    except:
                        continue
                else:
                    interptemp = None

                try:
                    projectedpoints.append(
                        [
                            distline,
                            float(footx[j]),
                            float(footy[j]),
                            distpoint,
                            0,
                            interptemp,
                            px,
                            py,
                            featPnt,
                        ]
                    )
                except ValueError:
                    print

        # Keep every projected point, sorted by distance along the line. (The
        # old removeDuplicateLenght() collapsed points within a hardcoded 0.01
        # CRS-unit window -- ~1 km in a geographic CRS -- which silently
        # decimated the profile and was order/floating-point unstable.)
        projectedpoints = np.array(projectedpoints)
        if len(projectedpoints) > 0:
            projectedpoints = projectedpoints[projectedpoints[:, 0].argsort()]

        # preparing return value
        profile = {}
        profile["layer"] = profile1["layer"]
        profile["band"] = profile1["band"]
        profile["l"] = [projectedpoint[0] for projectedpoint in projectedpoints]
        profile["z"] = [projectedpoint[5] for projectedpoint in projectedpoints]
        profile["x"] = [projectedpoint[1] for projectedpoint in projectedpoints]
        profile["y"] = [projectedpoint[2] for projectedpoint in projectedpoints]

        multipoly = qgis.core.QgsGeometry.fromMultiPolylineXY(
            [
                [
                    xform.transform(
                        QgsPointXY(projectedpoint[1], projectedpoint[2]),
                        qgis.core.QgsCoordinateTransform.ReverseTransform,
                    ),
                    xform.transform(
                        QgsPointXY(projectedpoint[6], projectedpoint[7]),
                        qgis.core.QgsCoordinateTransform.ReverseTransform,
                    ),
                ]
                for projectedpoint in projectedpoints
            ]
        )

        _VECTOR_PROFILE_CACHE[_lid] = (_sig, (dict(profile), buffergeom, multipoly))
        _wireProfileCacheInvalidation(profile1["layer"])
        return profile, buffergeom, multipoly
