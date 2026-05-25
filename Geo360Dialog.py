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

import math
import os
import shutil
from qgis.core import (
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsVectorLayer,
    QgsWkbTypes,
)
from qgis.gui import QgsRubberBand

from qgis.PyQt.QtCore import (
    QObject,
    QUrl,
    Qt,
    pyqtSignal,
)
from qgis.PyQt.QtWidgets import QDialog, QWidget, QDockWidget
from qgis.PyQt.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSlider
from qgis.PyQt.QtGui import QColor, QIcon, QImage, QWindow
import Mapupdate360.config as config
from Mapupdate360.geom.transformgeom import transformGeometry
from Mapupdate360.gui.ui_orbitalDialog import Ui_orbitalDialog
from Mapupdate360.utils.qgsutils import qgsutils
from qgis.PyQt.QtWebKitWidgets import QWebView, QWebPage
from qgis.PyQt.QtWebKit import QWebSettings


class _ViewerPage(QWebPage):
    obj = []  # synchronous
    newData = pyqtSignal(list)  # asynchronous

    def javaScriptConsoleMessage(self, msg, line, source):
        l = msg.split(",")
        self.obj = l
        self.newData.emit(l)


class Geo360Dialog(QDockWidget, Ui_orbitalDialog):

    """Geo360 Dialog Class"""

    def __init__(self, iface, parent=None, featuresId=None, layer=None):

        QDockWidget.__init__(self)

        self.setupUi(self)
        self.filter_sliders = {}
        self.filter_value_labels = {}
        self.CreateEnhancementControls()

        self.DEFAULT_URL = (
            "http://" + config.IP + ":" + str(config.PORT) + "/viewer.html"
        )
        self.DEFAULT_EMPTY = (
            "http://" + config.IP + ":" + str(config.PORT) + "/none.html"
        )
        self.DEFAULT_BLANK = (
            "http://" + config.IP + ":" + str(config.PORT) + "/blank.html"
        )

        # Create Viewer
        self.CreateViewer()

        self.plugin_path = os.path.dirname(os.path.realpath(__file__))
        self.setWindowIcon(QIcon(os.path.join(self.plugin_path, "images", "icon.png")))
        self.iface = iface
        self.canvas = self.iface.mapCanvas()
        self.parent = parent

        # Orientation from image
        self.yaw = math.pi
        self.bearing = 0.0
        self.current_fov = 70.0

        self.layer = layer
        self.featuresId = featuresId
        self.image_field = qgsutils.findFieldName(
            self.layer, config.image_field_candidates
        )
        self.yaw_field = qgsutils.findFieldName(self.layer, config.yaw_field_candidates)
        self.order_field = qgsutils.findFieldName(
            self.layer, config.order_field_candidates
        )

        self.actualPointDx = None
        self.actualPointSx = None
        self.actualPointOrientation = None
        self.actualPointFrustum = None

        self.selected_features = qgsutils.getToFeature(self.layer, self.featuresId)

        # Get image path
        self.current_image = self.GetImage()

        # Check if image exist
        if not self.current_image or os.path.exists(self.current_image) is False:
            qgsutils.showUserAndLogMessage(
                u"Information: ", u"There is no associated image."
            )
            self.resetQgsRubberBand()
            self.ChangeUrlViewer(self.DEFAULT_EMPTY)
            return

        # Copy file to local server
        self.CopyFile(self.current_image)

        # Set RubberBand
        self.resetQgsRubberBand()
        self.setOrientation()
        self.setPosition()

    """Update data from Marzipano Viewer"""
    def onNewData(self, data):
        try:
            newYaw = float(data[0])
            newFov = self.current_fov
            if len(data) > 1:
                parsed_fov = self.toFloat(data[1])
                if parsed_fov is not None:
                    newFov = parsed_fov
            self.UpdateOrientation(yaw=newYaw, fov=newFov)
        except:
            None

    def CreateViewer(self):
        """Create Viewer"""
        qgsutils.showUserAndLogMessage(u"Information: ", u"Create viewer", onlyLog=True)

        self.cef_widget = QWebView()
        self.cef_widget.setContextMenuPolicy(Qt.NoContextMenu)

        self.cef_widget.settings().setAttribute(QWebSettings.JavascriptEnabled, True)
        pano_view_settings = self.cef_widget.settings()
        pano_view_settings.setAttribute(QWebSettings.WebGLEnabled, True)
        # pano_view_settings.setAttribute(QWebSettings.DeveloperExtrasEnabled, True)
        pano_view_settings.setAttribute(QWebSettings.Accelerated2dCanvasEnabled, True)
        pano_view_settings.setAttribute(QWebSettings.JavascriptEnabled, True)

        self.page = _ViewerPage()
        self.page.newData.connect(self.onNewData)
        self.cef_widget.setPage(self.page)

        self.cef_widget.load(QUrl(self.DEFAULT_URL))
        self.cef_widget.loadFinished.connect(lambda _: self.UpdateImageFilters())
        self.ViewerLayout.addWidget(self.cef_widget, 1, 0)

    def CreateEnhancementControls(self):
        """Create brightness, contrast and saturation controls."""
        filter_layout = QHBoxLayout()
        filter_layout.setObjectName("filterLayout")

        for key, label, minimum, maximum, default in (
            ("brightness", "Brightness", 50, 150, 100),
            ("contrast", "Contrast", 50, 150, 100),
            ("saturation", "Saturation", 0, 200, 100),
        ):
            name_label = QLabel(label, self.dockWidgetContents)
            value_label = QLabel(str(default) + "%", self.dockWidgetContents)
            value_label.setMinimumWidth(38)
            slider = QSlider(Qt.Horizontal, self.dockWidgetContents)
            slider.setRange(minimum, maximum)
            slider.setValue(default)
            slider.setMinimumWidth(90)
            slider.valueChanged.connect(self.UpdateImageFilters)

            self.filter_sliders[key] = slider
            self.filter_value_labels[key] = value_label
            filter_layout.addWidget(name_label)
            filter_layout.addWidget(slider)
            filter_layout.addWidget(value_label)

        reset_button = QPushButton("Reset", self.dockWidgetContents)
        reset_button.setCursor(Qt.PointingHandCursor)
        reset_button.clicked.connect(self.ResetImageFilters)
        filter_layout.addWidget(reset_button)

        self.verticalLayout_3.addLayout(filter_layout)

    def UpdateImageFilters(self, _=None):
        """Apply image enhancement sliders to the web viewer."""
        values = {}
        for key, slider in self.filter_sliders.items():
            value = slider.value()
            values[key] = value
            self.filter_value_labels[key].setText(str(value) + "%")

        if not hasattr(self, "cef_widget"):
            return

        script = (
            "if (typeof SetImageFilter === 'function') "
            "{{ SetImageFilter({brightness}, {contrast}, {saturation}); }}"
        ).format(**values)
        try:
            self.cef_widget.page().mainFrame().evaluateJavaScript(script)
        except Exception:
            pass

    def ResetImageFilters(self):
        """Reset image enhancement controls."""
        defaults = {"brightness": 100, "contrast": 100, "saturation": 100}
        for key, value in defaults.items():
            self.filter_sliders[key].setValue(value)
        self.UpdateImageFilters()

    # def SetInitialYaw(self):
    #     """Set Initial Viewer Yaw"""
    #     self.bearing = self.selected_features.attribute(config.column_yaw)
    #     # self.view.browser.GetMainFrame().ExecuteFunction("InitialYaw",
    #     #                                                  self.bearing)
    #     return

    def RemoveImage(self):
        """Remove Image"""
        try:
            os.remove(self.plugin_path + "/viewer/image.jpg")
        except OSError:
            pass

    def CopyFile(self, src):
        """Copy Image File in Local Server"""
        qgsutils.showUserAndLogMessage(u"Information: ", u"Copying image", onlyLog=True)

        dst_dir = self.plugin_path + "/viewer"

        # Copy image in local folder
        dst_dir = dst_dir + "/image.jpg"

        try:
            os.remove(dst_dir)
        except OSError:
            pass

        image = QImage(src)
        if not image.isNull():
            image.save(dst_dir, "JPG")
        else:
            shutil.copyfile(src, dst_dir)

    def GetImage(self):
        """Get Selected Image"""
        try:
            if self.image_field is None:
                raise ValueError("Image path field not found.")
            path = qgsutils.getAttributeFromFeature(
                self.selected_features, self.image_field
            )
            if path in ("", None):
                return ""
            if not os.path.isabs(path):  # Relative Path to Project
                path_project = QgsProject.instance().readPath("./")
                path = os.path.normpath(os.path.join(path_project, path))
        except Exception:
            qgsutils.showUserAndLogMessage(
                u"Information: ", u"Image path column not found."
            )
            return ""

        qgsutils.showUserAndLogMessage(u"Information: ", str(path), onlyLog=True)
        return path

    def ChangeUrlViewer(self, new_url):
        """Change Url Viewer"""
        self.cef_widget.load(QUrl(new_url))

    def ReloadView(self, newId):
        """Reaload Image viewer"""
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
        # this will activate the window
        self.activateWindow()
        self.selected_features = qgsutils.getToFeature(self.layer, newId)
        self.featuresId = newId

        self.current_image = self.GetImage()

        # Check if image exist
        if not self.current_image or os.path.exists(self.current_image) is False:
            qgsutils.showUserAndLogMessage(
                u"Information: ", u"There is no associated image."
            )
            self.ChangeUrlViewer(self.DEFAULT_EMPTY)
            self.resetQgsRubberBand()
            return

        # Set RubberBand
        self.resetQgsRubberBand()
        self.setOrientation()
        self.setPosition()

        # Copy file to local server
        self.CopyFile(self.current_image)

        self.ChangeUrlViewer(self.DEFAULT_URL)

    def GetBackNextImage(self):
        """Get to Back Image"""
        sender = QObject.sender(self)

        if self.layer is None:
            qgsutils.showUserAndLogMessage(
                u"Information: ", u"You need load the photo layer."
            )
            return

        ordered_ids = self.orderedFeatureIds()
        if not ordered_ids:
            qgsutils.showUserAndLogMessage(
                u"Information: ", u"The photo layer has no features."
            )
            return

        try:
            current_index = ordered_ids.index(self.selected_features.id())
        except ValueError:
            current_index = 0

        step = -1 if sender.objectName() == "btn_back" else 1
        new_index = current_index + step
        if new_index < 0 or new_index >= len(ordered_ids):
            qgsutils.showUserAndLogMessage(
                u"Information: ", u"There is no previous/next image."
            )
            return

        new_id = ordered_ids[new_index]
        qgsutils.zoomToFeature(self.canvas, self.layer, new_id)
        self.ReloadView(new_id)
        return

    def orderedFeatureIds(self):
        """Return feature IDs ordered by the order field, then feature id."""
        ordered = []
        for feature in self.layer.getFeatures():
            order_value = self.toFloat(
                qgsutils.getOptionalAttribute(feature, self.order_field, feature.id())
            )
            if order_value is None:
                order_value = feature.id()
            ordered.append((order_value, feature.id()))
        ordered.sort(key=lambda item: (item[0], item[1]))
        return [item[1] for item in ordered]

    def FullScreen(self, value):
        """FullScreen action button"""
        qgsutils.showUserAndLogMessage(u"Information: ", u"Fullscreen.", onlyLog=True)
        if value:
            self.showFullScreen()
        else:
            self.showNormal()

    def UpdateOrientation(self, yaw=None, fov=None):
        """Update Orientation"""
        self.drawOrientation(yaw, fov)


    def setOrientation(self, yaw=None, fov=None):
        """Set Orientation in the firt time"""
        self.bearing = self.baseBearing()

        originalPoint = self.selected_features.geometry().asPoint()
        self.actualPointDx = qgsutils.convertProjection(
            originalPoint.x(),
            originalPoint.y(),
            self.layer.crs().authid(),
            self.canvas.mapSettings().destinationCrs().authid(),
        )

        self.rotateTool = transformGeometry()
        epsg = self.canvas.mapSettings().destinationCrs().authid()
        self.dumLayer = QgsVectorLayer(
            "Point?crs=" + epsg, "temporary_points", "memory"
        )
        self.drawOrientation(yaw, fov)

    def drawOrientation(self, yaw=None, fov=None):
        """Draw the current map direction frustum from image bearing + viewer yaw."""
        try:
            self.actualPointOrientation.reset()
        except Exception:
            pass
        try:
            self.actualPointFrustum.reset()
        except Exception:
            pass

        if self.actualPointDx is None:
            return

        yaw_value = self.toFloat(yaw)
        if yaw_value is None:
            yaw_value = 0.0
        fov_value = self.normalizedFov(fov)
        self.current_fov = fov_value
        heading = (self.baseBearing() + yaw_value) % 360.0

        length = self.canvas.mapUnitsPerPixel() * 70
        center_line = QgsGeometry.fromPolylineXY(
            [self.actualPointDx, self.pointFromHeading(self.actualPointDx, heading, length)]
        )

        self.actualPointFrustum = QgsRubberBand(
            self.iface.mapCanvas(), QgsWkbTypes.PolygonGeometry
        )
        self.actualPointFrustum.setColor(QColor(0, 80, 255, 190))
        self.actualPointFrustum.setWidth(2)
        try:
            self.actualPointFrustum.setFillColor(QColor(0, 160, 255, 55))
        except Exception:
            pass
        self.actualPointFrustum.setToGeometry(
            self.frustumGeometry(self.actualPointDx, heading, length, fov_value),
            self.dumLayer,
        )

        self.actualPointOrientation = QgsRubberBand(
            self.iface.mapCanvas(), QgsWkbTypes.LineGeometry
        )
        self.actualPointOrientation.setColor(QColor(0, 45, 220))
        self.actualPointOrientation.setWidth(3)
        self.actualPointOrientation.setToGeometry(center_line, self.dumLayer)

        tmpGeom = center_line.asPolyline()
        azim = tmpGeom[0].azimuth(tmpGeom[1])
        if azim < 0:
            azim += 360
        self.yawLbl.setText(
            "Yaw : {}  Heading : {}  FOV : {}".format(
                round(yaw_value, 2), round(azim, 2), round(fov_value, 2)
            )
        )

    def frustumGeometry(self, center, heading, length, field_of_view):
        """Create a viewing cone polygon around the current heading."""
        segments = 14
        points = [center]
        start = heading - field_of_view / 2.0
        for index in range(segments + 1):
            angle = start + field_of_view * index / segments
            points.append(self.pointFromHeading(center, angle, length))
        points.append(center)
        return QgsGeometry.fromPolygonXY([points])

    def normalizedFov(self, fov):
        """Return a safe horizontal field-of-view for drawing the frustum."""
        fov_value = self.toFloat(fov)
        if fov_value is None:
            fov_value = self.current_fov
        return max(5.0, min(160.0, fov_value))

    def pointFromHeading(self, center, heading, distance):
        """Project a point from a compass heading in map canvas units."""
        angle = math.radians(heading)
        x = center.x() + distance * math.sin(angle)
        y = center.y() + distance * math.cos(angle)
        return QgsPointXY(float(x), float(y))

    def baseBearing(self):
        value = qgsutils.getOptionalAttribute(self.selected_features, self.yaw_field, 0)
        number = self.toFloat(value)
        if number is None:
            return 0.0
        return number

    def toFloat(self, value):
        try:
            return float(value)
        except Exception:
            return None

    def setPosition(self):
        """Set RubberBand Position"""
        # Transform Point
        originalPoint = self.selected_features.geometry().asPoint()
        self.actualPointDx = qgsutils.convertProjection(
            originalPoint.x(),
            originalPoint.y(),
            self.layer.crs().authid(),
            self.canvas.mapSettings().destinationCrs().authid(),
        )

        self.positionDx = QgsRubberBand(
            self.iface.mapCanvas(), QgsWkbTypes.PointGeometry
        )
        self.positionDx.setWidth(6)
        self.positionDx.setIcon(QgsRubberBand.ICON_CIRCLE)
        self.positionDx.setIconSize(6)
        self.positionDx.setColor(Qt.black)
        self.positionSx = QgsRubberBand(
            self.iface.mapCanvas(), QgsWkbTypes.PointGeometry
        )
        self.positionSx.setWidth(5)
        self.positionSx.setIcon(QgsRubberBand.ICON_CIRCLE)
        self.positionSx.setIconSize(4)
        self.positionSx.setColor(Qt.blue)
        self.positionInt = QgsRubberBand(
            self.iface.mapCanvas(), QgsWkbTypes.PointGeometry
        )
        self.positionInt.setWidth(5)
        self.positionInt.setIcon(QgsRubberBand.ICON_CIRCLE)
        self.positionInt.setIconSize(3)
        self.positionInt.setColor(Qt.white)

        self.positionDx.addPoint(self.actualPointDx)
        self.positionSx.addPoint(self.actualPointDx)
        self.positionInt.addPoint(self.actualPointDx)

    def closeEvent(self, _):
        """Close dialog"""
        self.resetQgsRubberBand()
        self.canvas.refresh()
        self.iface.actionPan().trigger()
        self.parent.orbitalViewer = None
        self.RemoveImage()

    def resetQgsRubberBand(self):
        """Remove RubbeBand"""
        try:
            self.yawLbl.setText("")
            self.positionSx.reset()
            self.positionInt.reset()
            self.positionDx.reset()
            self.actualPointOrientation.reset()
            self.actualPointFrustum.reset()
        except Exception:
            None
