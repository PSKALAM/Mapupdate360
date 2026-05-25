"""
/***************************************************************************
 Mapupdate360
                                 A QGIS plugin
 Use local 360/equirectangular images for map update workflows.
                             -------------------
        begin                : 2017-02-17
        original copyright   : (C) 2016 All4Gis.
        original author      : Francisco Raga / All4GIS
        enhancements         : Pankaj Singh Kalam
 ***************************************************************************/
/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 #   any later version.                                                    *
 *                                                                         *
 ***************************************************************************/
"""


def classFactory(iface):
    from .Geo360 import Geo360

    return Geo360(iface)
