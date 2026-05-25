import os
import shutil

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor, QImage, QPainter
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)
from qgis.core import (
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsFeature,
    QgsProject,
    QgsVectorFileWriter,
    QgsVectorLayer,
)

import Mapupdate360.config as config
from Mapupdate360.utils.qgsutils import qgsutils


SHAPEFILE_EXTENSIONS = (
    ".shp",
    ".shx",
    ".dbf",
    ".prj",
    ".cpg",
    ".qpj",
    ".sbn",
    ".sbx",
    ".fix",
)


class PrivacyOptions:
    def __init__(self, enabled=False, output_folder="", mode="blur", bottom_percent=18):
        self.enabled = enabled
        self.output_folder = output_folder
        self.mode = mode
        self.bottom_percent = bottom_percent


class PhotoPrivacyProcessor:
    def __init__(self, iface=None):
        self.iface = iface

    def process_image(self, image_path, output_folder, mode="blur", bottom_percent=18):
        if not os.path.isfile(image_path):
            raise ValueError("Image not found: {}".format(image_path))

        os.makedirs(output_folder, exist_ok=True)
        output_path = self.unique_output_path(image_path, output_folder)
        image = QImage(image_path)

        if image.isNull():
            shutil.copyfile(image_path, output_path)
            return output_path

        bottom_percent = max(1, min(60, int(bottom_percent)))
        mask_height = max(1, int(image.height() * bottom_percent / 100.0))
        mask_top = image.height() - mask_height

        if mode == "cover":
            self.cover_bottom(image, mask_top, mask_height)
        else:
            self.blur_bottom(image, mask_top, mask_height)

        if not image.save(output_path):
            raise ValueError("Could not save processed image: {}".format(output_path))
        return output_path

    def blur_bottom(self, image, mask_top, mask_height):
        rect = image.copy(0, mask_top, image.width(), mask_height)
        small_width = max(1, int(rect.width() / 28))
        small_height = max(1, int(rect.height() / 28))
        blurred = rect.scaled(
            small_width,
            small_height,
            Qt.IgnoreAspectRatio,
            Qt.SmoothTransformation,
        ).scaled(
            rect.width(),
            rect.height(),
            Qt.IgnoreAspectRatio,
            Qt.SmoothTransformation,
        )

        painter = QPainter(image)
        painter.drawImage(0, mask_top, blurred)
        painter.fillRect(0, mask_top, image.width(), mask_height, QColor(0, 0, 0, 35))
        painter.end()

    def cover_bottom(self, image, mask_top, mask_height):
        painter = QPainter(image)
        painter.fillRect(0, mask_top, image.width(), mask_height, QColor(0, 0, 0, 230))
        painter.end()

    def unique_output_path(self, image_path, output_folder):
        base_name = os.path.basename(image_path)
        name, ext = os.path.splitext(base_name)
        ext = ext if ext else ".jpg"
        candidate = os.path.join(output_folder, name + "_camera_bottom_hidden" + ext)
        counter = 2
        while os.path.exists(candidate):
            candidate = os.path.join(
                output_folder,
                "{}_camera_bottom_hidden_{}{}".format(name, counter, ext),
            )
            counter += 1
        return os.path.normpath(candidate)

    def resolve_image_path(self, path):
        path = os.path.normpath(str(path))
        if os.path.isabs(path):
            return path
        project_path = QgsProject.instance().readPath("./")
        return os.path.normpath(os.path.join(project_path, path))

    def remove_existing_shapefile(self, output_path):
        root, _ = os.path.splitext(output_path)
        for extension in SHAPEFILE_EXTENSIONS:
            path = root + extension
            if os.path.exists(path):
                os.remove(path)

    def writer_result(self, result):
        if isinstance(result, tuple):
            error = result[0]
            message = result[1] if len(result) > 1 else ""
            return error, message
        return result, ""

    def anonymize_layer(self, source_layer, output_path, layer_name, options):
        image_field = qgsutils.findFieldName(source_layer, config.image_field_candidates)
        if image_field is None:
            raise ValueError("Select a photo layer with an image path field.")

        output_path = os.path.normpath(output_path)
        if not output_path.lower().endswith(".shp"):
            output_path += ".shp"
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.isdir(output_dir):
            raise ValueError("Select a valid output folder.")
        if not options.output_folder:
            options.output_folder = os.path.join(
                output_dir or os.getcwd(), "camera_bottom_hidden_images"
            )

        os.makedirs(options.output_folder, exist_ok=True)
        display_name = layer_name.strip() or os.path.splitext(os.path.basename(output_path))[0]
        memory_layer = QgsVectorLayer(
            "Point?crs={}".format(source_layer.crs().authid() or "EPSG:4326"),
            display_name,
            "memory",
        )
        provider = memory_layer.dataProvider()
        provider.addAttributes([field for field in source_layer.fields()])
        memory_layer.updateFields()

        path_index = source_layer.fields().indexOf(image_field)
        features = []
        processed = 0
        skipped = 0

        for source_feature in source_layer.getFeatures():
            attrs = source_feature.attributes()
            image_path = attrs[path_index] if path_index >= 0 else ""
            try:
                source_image = self.resolve_image_path(image_path)
                processed_image = self.process_image(
                    source_image,
                    options.output_folder,
                    options.mode,
                    options.bottom_percent,
                )
                attrs[path_index] = processed_image
                processed += 1
            except Exception:
                skipped += 1

            feature = QgsFeature(memory_layer.fields())
            feature.setGeometry(source_feature.geometry())
            feature.setAttributes(attrs)
            features.append(feature)

        if not features:
            raise ValueError("The selected layer has no features.")

        provider.addFeatures(features)
        memory_layer.updateExtents()
        self.remove_existing_shapefile(output_path)

        result = QgsVectorFileWriter.writeAsVectorFormat(
            memory_layer,
            output_path,
            "UTF-8",
            source_layer.crs() or QgsCoordinateReferenceSystem("EPSG:4326"),
            "ESRI Shapefile",
        )
        error, message = self.writer_result(result)
        if error != QgsVectorFileWriter.NoError:
            raise ValueError("Could not create shapefile: {}".format(message or error))

        output_layer = QgsVectorLayer(output_path, display_name, "ogr")
        if not output_layer.isValid():
            raise ValueError("The shapefile was written but QGIS could not load it.")

        return output_layer, processed, skipped


class AnonymizeLayerDialog(QDialog):
    def __init__(self, parent=None, default_folder=""):
        QDialog.__init__(self, parent)
        self.setWindowTitle("Hide/Blur Camera Bottom")
        self.setMinimumWidth(560)

        self.layer_name_edit = QLineEdit("photo_points_camera_bottom_hidden")
        self.output_edit = QLineEdit()
        self.output_folder_edit = QLineEdit(default_folder)
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Blur bottom area", "blur")
        self.mode_combo.addItem("Cover bottom area", "cover")
        self.bottom_spin = QSpinBox()
        self.bottom_spin.setRange(5, 45)
        self.bottom_spin.setValue(18)
        self.bottom_spin.setSuffix("%")

        form = QFormLayout()
        form.addRow("New layer name", self.layer_name_edit)
        form.addRow("Output shapefile", self.path_row(self.output_edit, self.choose_output))
        form.addRow(
            "Processed image folder",
            self.path_row(self.output_folder_edit, self.choose_output_folder),
        )
        form.addRow("Camera bottom method", self.mode_combo)
        form.addRow("Bottom area", self.bottom_spin)

        note = QLabel(
            "Original images are not changed. The new layer will point to processed copies with the camera bottom hidden."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #555;")

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(note)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def path_row(self, edit, slot):
        row = QHBoxLayout()
        row.addWidget(edit)
        browse = QPushButton("Browse")
        browse.setCursor(Qt.PointingHandCursor)
        browse.clicked.connect(slot)
        row.addWidget(browse)
        return row

    def choose_output(self):
        output, _ = QFileDialog.getSaveFileName(
            self,
            "Save camera-bottom-hidden photo layer",
            self.output_edit.text() or "photo_points_camera_bottom_hidden.shp",
            "Shapefile (*.shp)",
        )
        if output:
            if not output.lower().endswith(".shp"):
                output += ".shp"
            self.output_edit.setText(output)
            if not self.output_folder_edit.text().strip():
                self.output_folder_edit.setText(
                    os.path.join(
                        os.path.dirname(output),
                        "camera_bottom_hidden_images",
                    )
                )

    def choose_output_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select processed image folder", self.output_folder_edit.text()
        )
        if folder:
            self.output_folder_edit.setText(folder)

    def values(self):
        return {
            "layer_name": self.layer_name_edit.text().strip(),
            "output": self.output_edit.text().strip(),
            "options": PrivacyOptions(
                enabled=True,
                output_folder=self.output_folder_edit.text().strip(),
                mode=self.mode_combo.currentData(),
                bottom_percent=self.bottom_spin.value(),
            ),
        }


class HideCameraBottomLayerTool:
    def __init__(self, iface, layer_provider):
        self.iface = iface
        self.layer_provider = layer_provider
        self.processor = PhotoPrivacyProcessor(iface)

    def run(self):
        source_layer = self.layer_provider()
        if source_layer is None:
            self.message(
                "Hide/Blur Camera Bottom",
                "Select a point layer with an image path field first.",
                Qgis.Critical,
            )
            return None

        dialog = AnonymizeLayerDialog(self.iface.mainWindow())
        if dialog.exec_() != QDialog.Accepted:
            return None

        values = dialog.values()
        try:
            output_layer, processed, skipped = self.processor.anonymize_layer(
                source_layer,
                values["output"],
                values["layer_name"],
                values["options"],
            )
        except Exception as exc:
            self.message("Hide/Blur Camera Bottom", str(exc), Qgis.Critical)
            return None

        QgsProject.instance().addMapLayer(output_layer)
        self.message(
            "Hide/Blur Camera Bottom",
            "Processed {} image(s). Skipped {} image(s).".format(processed, skipped),
            Qgis.Info,
        )
        return output_layer

    def message(self, title, text, level):
        try:
            self.iface.messageBar().pushMessage(title, text, level=level, duration=6)
        except Exception:
            QMessageBox.information(None, title, text)


AnonymizePhotoLayerTool = HideCameraBottomLayerTool
