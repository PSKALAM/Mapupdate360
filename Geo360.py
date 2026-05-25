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

from qgis.gui import QgsMapToolIdentify
from qgis.PyQt.QtCore import Qt, QSettings, QThread
from qgis.PyQt.QtGui import QIcon, QCursor, QPixmap
from qgis.PyQt.QtWidgets import QAction

from Mapupdate360.Geo360Dialog import Geo360Dialog
from Mapupdate360.photo_layer_creator import PhotoLayerCreator
from Mapupdate360.privacy_processor import HideCameraBottomLayerTool
import Mapupdate360.config as config
from Mapupdate360.utils.log import log
from Mapupdate360.utils.qgsutils import qgsutils
from qgis.core import QgsApplication, QgsMapLayer, QgsWkbTypes
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
import os
import time

""" Server Handelr """


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass


class Geo360:

    """QGIS Plugin Implementation."""

    def __init__(self, iface):

        self.iface = iface
        self.canvas = self.iface.mapCanvas()
        threadcount = QThread.idealThreadCount()
        # use all available cores and parallel rendering
        QgsApplication.setMaxThreads(threadcount)
        QSettings().setValue("/qgis/parallel_rendering", True)
        # OpenCL acceleration
        QSettings().setValue("/core/OpenClEnabled", True)
        self.orbitalViewer = None
        self.server = None
        self.make_server()

    def initGui(self):
        """Add Geo360 tool"""
        log.initLogging()
        plugin_dir = os.path.dirname(os.path.realpath(__file__))
        main_icon = QIcon(os.path.join(plugin_dir, "images", "icon.png"))
        self.action = QAction(
            main_icon,
            u"Mapupdate360",
            self.iface.mainWindow(),
        )
        self.action.triggered.connect(self.run)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu(u"&Mapupdate360", self.action)

        create_icon = QIcon(
            os.path.join(
                plugin_dir,
                "images",
                "create_photo_layer.svg",
            )
        )
        self.create_layer_action = QAction(
            create_icon,
            u"Create Photo Point Layer",
            self.iface.mainWindow(),
        )
        self.create_layer_action.triggered.connect(self.createPhotoPointLayer)
        self.iface.addToolBarIcon(self.create_layer_action)
        self.iface.addPluginToMenu(u"&Mapupdate360", self.create_layer_action)

        privacy_icon = QIcon(
            os.path.join(
                plugin_dir,
                "images",
                "privacy_mask.svg",
            )
        )
        if privacy_icon.isNull():
            privacy_icon = create_icon
        self.privacy_action = QAction(
            privacy_icon,
            u"Hide/Blur Camera Bottom",
            self.iface.mainWindow(),
        )
        self.privacy_action.triggered.connect(self.hideCameraBottomLayer)
        self.iface.addToolBarIcon(self.privacy_action)
        self.iface.addPluginToMenu(u"&Mapupdate360", self.privacy_action)

    def unload(self):
        """Unload Geo360 tool"""
        self.iface.removePluginMenu(u"&Mapupdate360", self.action)
        self.iface.removePluginMenu(u"&Mapupdate360", self.create_layer_action)
        self.iface.removePluginMenu(u"&Mapupdate360", self.privacy_action)
        self.iface.removeToolBarIcon(self.action)
        self.iface.removeToolBarIcon(self.create_layer_action)
        self.iface.removeToolBarIcon(self.privacy_action)
        # Close server
        self.close_server()

    # def is_running(self):
    #     return self.server_thread and self.server_thread.is_alive()

    def close_server(self):
        """Close Local server"""
        # Close server
        if self.server is not None:
            self.server.shutdown()
            time.sleep(1)
            self.server.server_close()
            while self.server_thread.is_alive():
                self.server_thread.join()
            self.server = None

    def make_server(self):
        """Create Local server"""
        # Close server
        self.close_server()
        # Create Server
        directory = os.path.join(
            os.path.dirname(os.path.realpath(__file__)), "viewer"
        )
        try:
            self.server = ThreadingHTTPServer(
                (config.IP, config.PORT),
                partial(QuietHandler, directory=directory),
            )
            self.server_thread = Thread(
                target=self.server.serve_forever, name="http_server"
            )
            self.server_thread.daemon = True
            print("Serving at port: %s" % self.server.server_address[1])
            time.sleep(1)
            self.server_thread.start()
        except Exception:
            print("Server Error")

    def run(self):
        """Run click feature"""
        layer = self.photoLayer()
        if layer is None:
            qgsutils.showUserAndLogMessage(
                u"Information: ",
                u"Select a point layer with an image path field, or use Create Photo Point Layer.",
            )
            return

        self.iface.setActiveLayer(layer)
        self.mapTool = SelectTool(self.iface, parent=self, layer=layer)
        self.iface.mapCanvas().setMapTool(self.mapTool)

    def photoLayer(self):
        """Return the active photo point layer, or another usable layer."""
        active_layer = self.iface.activeLayer()
        if self.isPhotoLayer(active_layer):
            return active_layer

        for layer in self.canvas.layers():
            if self.isPhotoLayer(layer):
                return layer
        return None

    def isPhotoLayer(self, layer):
        """Check whether a layer can be used by the viewer."""
        if layer is None:
            return False
        if layer.type() != QgsMapLayer.VectorLayer:
            return False
        if layer.geometryType() != QgsWkbTypes.PointGeometry:
            return False
        return (
            qgsutils.findFieldName(layer, config.image_field_candidates) is not None
        )

    def createPhotoPointLayer(self):
        """Create a point shapefile from geotagged photos."""
        creator = PhotoLayerCreator(self.iface)
        layer = creator.run()
        if layer is not None:
            self.iface.setActiveLayer(layer)

    def hideCameraBottomLayer(self):
        """Create camera-bottom-hidden image copies and a new photo layer."""
        tool = HideCameraBottomLayerTool(self.iface, self.photoLayer)
        layer = tool.run()
        if layer is not None:
            self.iface.setActiveLayer(layer)


    def ShowViewer(self, featuresId=None, layer=None):
        """Run dialog Geo360"""
        self.featuresId = featuresId
        self.layer = layer

        if self.orbitalViewer is None:
            self.orbitalViewer = Geo360Dialog(
                self.iface, parent=self, featuresId=featuresId, layer=self.layer
            )
            self.iface.addDockWidget(Qt.BottomDockWidgetArea, self.orbitalViewer)
        else:
            self.orbitalViewer.ReloadView(self.featuresId)


class SelectTool(QgsMapToolIdentify):
    """Select Photo on map"""

    def __init__(self, iface, parent=None, layer=None):
        QgsMapToolIdentify.__init__(self, iface.mapCanvas())
        self.canvas = iface.mapCanvas()
        self.iface = iface
        self.layer = layer
        self.parent = parent

        self.cursor = QCursor(
            QPixmap(
                [
                    "16 16 3 1",
                    "      c None",
                    ".     c #FF0000",
                    "+     c #FFFFFF",
                    "                ",
                    "       +.+      ",
                    "      ++.++     ",
                    "     +.....+    ",
                    "    +.     .+   ",
                    "   +.   .   .+  ",
                    "  +.    .    .+ ",
                    " ++.    .    .++",
                    " ... ...+... ...",
                    " ++.    .    .++",
                    "  +.    .    .+ ",
                    "   +.   .   .+  ",
                    "   ++.     .+   ",
                    "    ++.....+    ",
                    "      ++.++     ",
                    "       +.+      ",
                ]
            )
        )

    def activate(self):
        self.canvas.setCursor(self.cursor)

    def canvasReleaseEvent(self, event):
        found_features = self.identify(
            event.x(), event.y(), [self.layer], self.TopDownAll
        )

        if len(found_features) > 0:

            layer = found_features[0].mLayer
            feature = found_features[0].mFeature
            # Zoom To Feature
            qgsutils.zoomToFeature(self.canvas, layer, feature.id())
            self.parent.ShowViewer(featuresId=feature.id(), layer=layer)
