# -*- coding: utf-8 -*-
#-----------------------------------------------------------
#
# Profile
# Copyright (C) 2008  Borys Jurgiel
# Copyright (C) 2012  Patrice Verchere
#-----------------------------------------------------------
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
#---------------------------------------------------------------------
from qgis.core import *
import qgis
import numpy as np

import platform
from math import sqrt
from .utils import isProfilable
from qgis.PyQt.QtCore import QCoreApplication

class DataReaderTool:

    """def __init__(self):
        self.profiles = None"""

    def dataRasterReaderTool(self, iface1,tool1, profile1, pointstoDraw1, resolution_mode):
        """
        Return a dictionnary : {"layer" : layer read,
                                "band" : band read,
                                "l" : array of computed lenght,
                                "z" : array of computed z
        """
        #init
        self.tool = tool1                        #needed to transform point coordinates
        self.profiles = profile1                #profile with layer and band to compute
        self.pointstoDraw = pointstoDraw1        #the polyline to compute
        self.iface = iface1                        #QGis interface to show messages in status bar

        distance = qgis.core.QgsDistanceArea()

        #Get the values on the lines
        l = []
        z = []
        x = []
        y = []
        lbefore = 0
        # First create the list of x and y coordinates along the path
        # Also store distance projected on map.
         # work for each segment of polyline
        first_segment = True
        for p_start, p_end in zip(self.pointstoDraw[:-1],
                                  self.pointstoDraw[1:]):

            # for each polylines, set points x,y with map crs (%D) and layer crs (%C)
            pointstoCal1 = self.tool.toLayerCoordinates(self.profiles["layer"] , QgsPointXY(*p_start))
            pointstoCal2 = self.tool.toLayerCoordinates(self.profiles["layer"] , QgsPointXY(*p_end))
            x1D = float(p_start[0])
            y1D = float(p_start[1])
            x2D = float(p_end[0])
            y2D = float(p_end[1])
            x1C = float(pointstoCal1.x())
            y1C = float(pointstoCal1.y())
            x2C = float(pointstoCal2.x())
            y2C = float(pointstoCal2.y())
            #lenght between (x1,y1) and (x2,y2)
            tlC = sqrt (((x2C-x1C)*(x2C-x1C)) + ((y2C-y1C)*(y2C-y1C)))
            #Set the res of calcul
            try:
                res = min(self.profiles["layer"].rasterUnitsPerPixelX(),self.profiles["layer"].rasterUnitsPerPixelY()) * tlC / max(abs(x2C-x1C), abs(y2C-y1C))    # res depend on the angle of ligne with normal
            except ZeroDivisionError:
                res = min(self.profiles["layer"].rasterUnitsPerPixelX(),self.profiles["layer"].rasterUnitsPerPixelY()) * 1.2
            except AttributeError:
                # MeshLayers have no rasterUnitsPerPixelX/Y attribute
                res = 1
            #enventually use bigger step, wether full res is selected or not
            if resolution_mode == "samples":
                """Only take values at sample points, no intermediate values."""
                steps = 1
            else:
                if res != 0:
                    """Use the map's resolution."""
                    steps = int(tlC/res)
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
            dlD = sqrt ((dxD*dxD) + (dyD*dyD))
            dxC = (x2C - x1C) / steps
            dyC = (y2C - y1C) / steps
            #dlC = sqrt ((dxC*dxC) + (dyC*dyC))
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

        #End of polyline analysis
        #filling the main data dictionary "profiles"
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
            progress = "Creating profile: " + "|" * (advancement_pct//10)
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
                    attr = float(ident[1].values()[choosenBand])
                except:
                    attr = 0
                z.append(attr)
                self._status_update( (100*n) // (len(x) - 1) )
        elif layer.type() == layer.MeshLayer:
            identifier = qgis.gui.QgsMapToolIdentify(qgis.utils.iface.mapCanvas())
            meshFld = QCoreApplication.translate('QgsMapToolIdentify','Scalar Value')
            for n, coords in enumerate(zip(x, y)):
                ident = identifier.identify(
                    QgsGeometry.fromPointXY(QgsPointXY(*coords)),
                    qgis.gui.QgsMapToolIdentify.DefaultQgsSetting,
                    [layer], 
                    qgis.gui.QgsMapToolIdentify.MeshLayer)[0]
                
                try:
                    attr = float(ident.mAttributes[meshFld])
                except (AttributeError, ValueError):
                    attr = 0
                z.append(attr)
                self._status_update( (100*n) // (len(x) - 1) )
        else: #RASTER LAYERS
            for n, coords in enumerate(zip(x, y)):
                # this code adapted from valuetool plugin
                ident = layer.dataProvider().identify(
                    QgsPointXY(*coords), QgsRaster.IdentifyFormatValue )
                #if ident is not None and ident.has_key(choosenBand+1):
                if ident is not None and (choosenBand in ident.results()):
                    attr = ident.results()[choosenBand]
                else:
                    attr = 0
                z.append(attr)
                self._status_update( (100*n) // (len(x) - 1) )
        return z


    def dataVectorReaderTool(self, iface1,tool1, profile1, pointstoDraw1, valbuf1):
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

        projectedpoints = []
        buffergeom = None

        sourceCrs = QgsCoordinateReferenceSystem( qgis.utils.iface.mapCanvas().mapSettings().destinationCrs() )
        destCrs = QgsCoordinateReferenceSystem(profile1["layer"].crs())
        if qgis.core.Qgis.QGIS_VERSION[0] > '2':
            # In QGIS 3 QgsCoordinateTransform needs a QgsCoordinateTransformContext
            xform = QgsCoordinateTransform(sourceCrs, destCrs, QgsProject.instance())
            xformrev = QgsCoordinateTransform(destCrs, sourceCrs, QgsProject.instance())
        else:
            xform = QgsCoordinateTransform(sourceCrs, destCrs)
            xformrev = QgsCoordinateTransform(destCrs, sourceCrs)

        geom =  qgis.core.QgsGeometry.fromPolylineXY([QgsPointXY(point[0], point[1]) for point in pointstoDraw1])

        geominlayercrs = qgis.core.QgsGeometry(geom)
        tempresult = geominlayercrs.transform(xform)


        buffergeom = geom.buffer(valbuffer,12)
        buffergeominlayercrs = qgis.core.QgsGeometry(buffergeom)
        tempresult = buffergeominlayercrs.transform(xform)


        featsPnt = profile1["layer"].getFeatures(QgsFeatureRequest().setFilterRect(buffergeominlayercrs.boundingBox()))

        for featPnt in featsPnt:
            #iterate preselected point features and perform exact check with current polygon
            point3 = featPnt.geometry()
            distpoint = geominlayercrs.distance(point3)
            if distpoint <= valbuffer :
                distline = geominlayercrs.lineLocatePoint(point3)
                pointprojected = geominlayercrs.interpolate(distline)
                if profile1["band"] >-1 :
                    try:
                        interptemp = float(featPnt[profile1["band"]])
                    except:
                        continue
                else:
                    interptemp = None

                try:
                    projectedpoints.append([distline,
                                            pointprojected.asPoint().x(),
                                            pointprojected.asPoint().y(),
                                            distpoint, 0, interptemp,
                                            featPnt.geometry().asPoint().x(),
                                            featPnt.geometry().asPoint().y(),
                                            featPnt])
                except ValueError:
                    print

        projectedpoints = np.array(projectedpoints)


        #perform postprocess computation

        if len(projectedpoints)>0:
            #remove duplicates
            projectedpoints = self.removeDuplicateLenght(projectedpoints)
            #interpolate value at nodes of polyline
            projectedpoints = self.interpolateNodeofPolyline(geominlayercrs,projectedpoints)



        #preparing return value
        profile={}
        profile["layer"] = profile1["layer"]
        profile["band"] = profile1["band"]
        profile['l'] = [projectedpoint[0] for projectedpoint in projectedpoints]
        profile['z'] = [projectedpoint[5] for projectedpoint in projectedpoints]
        profile['x'] = [projectedpoint[1] for projectedpoint in projectedpoints]
        profile['y'] = [projectedpoint[2] for projectedpoint in projectedpoints]

        multipoly = qgis.core.QgsGeometry.fromMultiPolylineXY(
            [[xform.transform(QgsPointXY(projectedpoint[1], projectedpoint[2]),
                qgis.core.QgsCoordinateTransform.ReverseTransform) ,
              xform.transform(QgsPointXY(projectedpoint[6], projectedpoint[7]),
                qgis.core.QgsCoordinateTransform.ReverseTransform)]
             for projectedpoint in projectedpoints])

        return profile, buffergeom, multipoly




    def removeDuplicateLenght(self,projectedpoints):

        projectedpointsfinal = []
        duplicate = []
        leninterp = len(projectedpoints)
        PRECISION = 0.01

        for i in range(len(projectedpoints)):
            pointtoinsert = None
            if i in duplicate:
                continue
            else:
                mindist = np.absolute(projectedpoints[:,0] - projectedpoints[i,0])
                mindeltaalti = np.absolute(projectedpoints[:,5] - projectedpoints[i,5])
                mindistindex = np.where(mindist < PRECISION)

                if False:
                    minalitindex = np.where(mindeltaalti < PRECISION )
                    minindex = np.intersect1d(mindistindex[0],minalitindex[0])
                    #duplicate lenght with same alti : keep only one
                    if len(minindex) <= 1 :
                        projectedpointsfinal.append(projectedpoints[i])
                    else:
                        duplicate += minindex.tolist()
                        projectedpointsfinal.append(projectedpoints[i])

                    #duplicate lenght with different alti : keep the closest
                    mindistindex = np.setdiff1d(mindistindex[0],minindex,assume_unique=True)
                else:
                    #insert closest point
                    closestindex = np.argmin(projectedpoints[mindistindex[0],3])
                    projectedpointsfinal.append(projectedpoints[mindistindex[0][closestindex]])
                    duplicate += mindistindex[0].tolist()

        projectedpoints = np.array(projectedpointsfinal)
        projectedpoints = projectedpoints[projectedpoints[:,0].argsort()]
        return projectedpoints


    #def interpolateNodeofPolyline(self,geom):
    def interpolateNodeofPolyline(self,geom,projectedpoints):
        """
        projectedpoints : array [[lenght, xprojected ,yprojected ,dist from origignal point, segment of polyline on witch it's projected, atribute (z), xoriginal point, yoriginal point ,original point feature], ... ]
        """
        PRECISION = 0.01
        polyline = geom.asPolyline()
        projectedpoints = projectedpoints[projectedpoints[:,0].argsort()]

        lenpoly = 0

        #Write fist and last element if no value
        if projectedpoints[0][0] != 0:
            projectedpoints = np.append(projectedpoints,[[0,polyline[0].x(), polyline[0].y(), -1,0,projectedpoints[0][5],polyline[0].x(), polyline[0].y(),projectedpoints[0][8] ]], axis = 0)
            projectedpoints = projectedpoints[projectedpoints[:,0].argsort()]
        if projectedpoints[-1][0] != geom.length():
            projectedpoints = np.append(projectedpoints,[[geom.length(),polyline[-1].x(), polyline[-1].y(), -1,len(polyline)-2,projectedpoints[-1][5],polyline[-1].x(), polyline[-1].y(),projectedpoints[0][8] ]], axis = 0)
            projectedpoints = projectedpoints[projectedpoints[:,0].argsort()]

        projectedpointsinterp = []

        for i,point in enumerate(polyline):
            if i == 0:
                continue
            elif i == len(polyline) -1 :
                break
            else:
                vertexpoint_xy = QgsPointXY(geom.vertexAt(i))
                # vertexpoint_xy = QgsPointXY(vertexpoint.x(), vertexpoint.y())
                lenpoly = geom.lineLocatePoint(
                    qgis.core.QgsGeometry.fromPointXY(vertexpoint_xy))

                if min(abs(projectedpoints[:,0] - lenpoly)) < PRECISION :
                    continue
                else:
                    temp1 = self.interpolatePoint(
                        vertexpoint_xy, geom, projectedpoints)
                    if temp1 != None :
                        projectedpointsinterp.append( temp1 )


        temp = projectedpoints.tolist() + projectedpointsinterp
        projectedpoints = np.array(temp)

        projectedpoints = projectedpoints[projectedpoints[:,0].argsort()]

        return projectedpoints


    def interpolatePoint(self, vertexpoint, geom, projectedpoints):

        lenpoly = geom.lineLocatePoint(qgis.core.QgsGeometry.fromPointXY(vertexpoint))

        previouspointindex = np.max(np.where(projectedpoints[:,0]<=lenpoly)[0])
        nextpointindex = np.min(np.where(projectedpoints[:,0]>=lenpoly)[0])

        lentot = projectedpoints[nextpointindex][0] - projectedpoints[previouspointindex][0]
        if lentot>0:
            lentemp = lenpoly  - projectedpoints[previouspointindex][0]
            z = projectedpoints[previouspointindex][5] + ( projectedpoints[nextpointindex][5] - projectedpoints[previouspointindex][5] )/ lentot * lentemp
            #return [lenpoly, point[0], point[1], -1, None ,z,point[0], point[1], None ]
            return [lenpoly, vertexpoint.x(), vertexpoint.y(), -1, None ,z,vertexpoint.x(), vertexpoint.y(), None ]
        else :
            return None
