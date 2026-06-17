"""
/***************************************************************************
 Mapupdate360 QGIS plugin helpers
 ***************************************************************************/
"""

from qgis.core import Qgis as QGis
from qgis.gui import QgsRubberBand
from qgis.utils import iface
from qgis.core import (
    QgsPointXY,
    QgsProject,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsRectangle,
)
from Mapupdate360.utils.log import log


class qgsutils(object):
    @staticmethod
    def findFieldName(layer, candidates):
        """Return the real layer field name matching one of the candidates."""
        if layer is None:
            return None

        fields = layer.fields()
        lookup = {field.name().lower(): field.name() for field in fields}
        for candidate in candidates:
            if candidate and candidate.lower() in lookup:
                return lookup[candidate.lower()]
        return None

    @staticmethod
    def getOptionalAttribute(feature, columnName, default=None):
        """Get an attribute when the column exists, otherwise return default."""
        if feature is None or not columnName:
            return default
        try:
            value = feature.attribute(columnName)
        except Exception:
            return default
        if value in ("", None):
            return default
        return value

    @staticmethod
    def convertProjection(x, y, from_crs, to_crs):
        """Convert Coordinates EPSG"""
        crsSrc = QgsCoordinateReferenceSystem(from_crs)
        crsDest = QgsCoordinateReferenceSystem(to_crs)
        xform = QgsCoordinateTransform(crsSrc, crsDest, QgsProject.instance())
        pt = xform.transform(QgsPointXY(x, y))
        return pt

    @staticmethod
    def getAttributeFromFeature(feature, columnName):
        """Get Attribute from feature"""
        return feature.attribute(columnName)

    @staticmethod
    def zoomToFeature(canvas, layer, ide):
        """Zoom to feature by Id"""
        if layer:
            for feature in layer.getFeatures():
                if feature.id() == ide:
                    # Transform Point
                    actualPoint = feature.geometry().asPoint()
                    projPoint = qgsutils.convertProjection(
                        actualPoint.x(),
                        actualPoint.y(),
                        layer.crs().authid(),
                        canvas.mapSettings().destinationCrs().authid(),
                    )
                    x = projPoint.x()
                    y = projPoint.y()
                    rect = QgsRectangle(x, y, x, y)
                    canvas.setExtent(rect)
                    canvas.refresh()
                    return True
        return False

    @staticmethod
    def showUserAndLogMessage(
        before, text="", level=QGis.Info, duration=3, onlyLog=False
    ):
        """Show user & log info/warning/error messages"""
        if not onlyLog:
            iface.messageBar().popWidget()
            iface.messageBar().pushMessage(before, text, level=level, duration=duration)
        if level == QGis.Info:
            log.info(text)
        elif level == QGis.Warning:
            log.warning(text)
        elif level == QGis.Critical:
            log.error(text)
        return

    @staticmethod
    def getToFeature(layer, ide):
        """Get To feature by ID"""
        if layer:
            for feature in layer.getFeatures():
                if feature.id() == ide:
                    return feature
        return False
