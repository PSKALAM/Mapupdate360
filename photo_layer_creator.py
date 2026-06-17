import csv
import os
import struct
import xml.etree.ElementTree as ET

from qgis.PyQt.QtCore import Qt, QVariant
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
    QgsField,
    QgsGeometry,
    QgsProject,
    QgsPointXY,
    QgsVectorFileWriter,
    QgsVectorLayer,
)

import Mapupdate360.config as config
from Mapupdate360.privacy_processor import PhotoPrivacyProcessor, PrivacyOptions


IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".tif", ".tiff")
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


class CreatePhotoLayerDialog(QDialog):
    def __init__(self, parent=None):
        QDialog.__init__(self, parent)
        self.setWindowTitle("Create Photo Point Layer")
        self.setMinimumWidth(560)

        self.folder_edit = QLineEdit()
        self.layer_name_edit = QLineEdit("photo_points")
        self.output_edit = QLineEdit()
        self.metadata_edit = QLineEdit()
        self.privacy_check = QCheckBox("Hide/blur camera bottom in image copies")
        self.privacy_folder_edit = QLineEdit()
        self.privacy_mode_combo = QComboBox()
        self.privacy_mode_combo.addItem("Blur bottom area", "blur")
        self.privacy_mode_combo.addItem("Cover bottom area", "cover")
        self.privacy_bottom_spin = QSpinBox()
        self.privacy_bottom_spin.setRange(5, 45)
        self.privacy_bottom_spin.setValue(18)
        self.privacy_bottom_spin.setSuffix("%")
        self.mount_offset_check = QCheckBox(
            "Apply correction for camera mount offset *2"
        )
        self.mount_offset_combo = QComboBox()
        self.mount_offset_combo.addItem("Straight forward (0 deg)", 0)
        self.mount_offset_combo.addItem("Mounted 90 deg right (+90 deg)", 90)
        self.mount_offset_combo.addItem("Mounted backward (+180 deg)", 180)
        self.mount_offset_combo.addItem("Mounted 90 deg left (-90 deg)", -90)
        self.mount_offset_combo.addItem("Custom offset", None)
        self.mount_offset_spin = QSpinBox()
        self.mount_offset_spin.setRange(-359, 359)
        self.mount_offset_spin.setValue(0)
        self.mount_offset_spin.setSuffix(" deg")
        self.recursive_check = QCheckBox("Include subfolders")
        self.recursive_check.setChecked(True)

        form = QFormLayout()
        form.addRow("Image folder", self._path_row(self.folder_edit, self._choose_folder))
        form.addRow("Layer name", self.layer_name_edit)
        form.addRow("Output shapefile", self._path_row(self.output_edit, self._choose_output))
        form.addRow(
            "Metadata CSV (optional) *1",
            self._path_row(self.metadata_edit, self._choose_metadata),
        )
        form.addRow("", self.recursive_check)
        form.addRow("", self.mount_offset_check)
        form.addRow("Camera mount", self.mount_offset_combo)
        form.addRow("Custom mount offset", self.mount_offset_spin)
        form.addRow("", self.privacy_check)
        form.addRow(
            "Processed image folder",
            self._path_row(self.privacy_folder_edit, self._choose_privacy_folder),
        )
        form.addRow("Camera bottom method", self.privacy_mode_combo)
        form.addRow("Bottom area", self.privacy_bottom_spin)

        note = QLabel(
            "*1 Metadata CSV may provide filename, latitude, longitude, order, or datetime.\n"
            "*2 Camera mount offset is optional. Use it only when heading comes from "
            "GPSImgDirection or GPSTrack and the camera reference/front lens was not "
            "aligned with the vehicle movement direction.\n"
            "GPano pose heading is treated as already north-referenced. Processed "
            "copies keep original images untouched."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #555;")

        self.mount_offset_check.toggled.connect(self._update_mount_offset_state)
        self.mount_offset_combo.currentIndexChanged.connect(
            self._update_mount_offset_state
        )
        self._update_mount_offset_state()

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(note)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def _path_row(self, edit, slot):
        row = QHBoxLayout()
        row.addWidget(edit)
        browse = QPushButton("Browse")
        browse.setCursor(Qt.PointingHandCursor)
        browse.clicked.connect(slot)
        row.addWidget(browse)
        return row

    def _choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select image folder")
        if folder:
            self.folder_edit.setText(folder)
            if not self.layer_name_edit.text().strip():
                self.layer_name_edit.setText("photo_points")
            if not self.output_edit.text():
                self.output_edit.setText(
                    os.path.join(folder, self._output_name_from_layer() + ".shp")
                )
            if not self.privacy_folder_edit.text():
                self.privacy_folder_edit.setText(
                    os.path.join(folder, "camera_bottom_hidden_images")
                )

    def _choose_output(self):
        output, _ = QFileDialog.getSaveFileName(
            self,
            "Save photo point layer",
            self.output_edit.text() or "photo_points.shp",
            "Shapefile (*.shp)",
        )
        if output:
            if not output.lower().endswith(".shp"):
                output += ".shp"
            self.output_edit.setText(output)
            if not self.layer_name_edit.text().strip():
                self.layer_name_edit.setText(
                    os.path.splitext(os.path.basename(output))[0]
                )

    def _choose_metadata(self):
        metadata, _ = QFileDialog.getOpenFileName(
            self,
            "Select optional metadata CSV",
            "",
            "CSV files (*.csv);;All files (*.*)",
        )
        if metadata:
            self.metadata_edit.setText(metadata)

    def _choose_privacy_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select processed image folder", self.privacy_folder_edit.text()
        )
        if folder:
            self.privacy_folder_edit.setText(folder)

    def values(self):
        return {
            "folder": self.folder_edit.text().strip(),
            "layer_name": self.layer_name_edit.text().strip(),
            "output": self.output_edit.text().strip(),
            "metadata": self.metadata_edit.text().strip(),
            "recursive": self.recursive_check.isChecked(),
            "mount_offset": self._mount_offset_value(),
            "privacy": PrivacyOptions(
                enabled=self.privacy_check.isChecked(),
                output_folder=self.privacy_folder_edit.text().strip(),
                mode=self.privacy_mode_combo.currentData(),
                bottom_percent=self.privacy_bottom_spin.value(),
            ),
        }

    def _output_name_from_layer(self):
        name = self.layer_name_edit.text().strip() or "photo_points"
        safe = "".join(char if char.isalnum() or char in ("_", "-") else "_" for char in name)
        return safe.strip("_") or "photo_points"

    def _mount_offset_value(self):
        if not self.mount_offset_check.isChecked():
            return 0.0
        value = self.mount_offset_combo.currentData()
        if value is None:
            value = self.mount_offset_spin.value()
        return float(value)

    def _update_mount_offset_state(self):
        enabled = self.mount_offset_check.isChecked()
        self.mount_offset_combo.setEnabled(enabled)
        self.mount_offset_spin.setEnabled(
            enabled and self.mount_offset_combo.currentData() is None
        )


class PhotoLayerCreator:
    def __init__(self, iface):
        self.iface = iface

    def run(self):
        dialog = CreatePhotoLayerDialog(self.iface.mainWindow())
        if dialog.exec_() != QDialog.Accepted:
            return None

        values = dialog.values()
        try:
            layer, created, skipped, notices = self.create_layer(
                values["folder"],
                values["output"],
                values["metadata"],
                values["recursive"],
                values["layer_name"],
                values["privacy"],
                values["mount_offset"],
            )
        except Exception as exc:
            self._message("Photo layer", str(exc), Qgis.Critical)
            return None

        QgsProject.instance().addMapLayer(layer)
        self._message(
            "Photo layer",
            self._success_message(created, skipped, notices),
            Qgis.Info,
        )
        return layer

    def create_layer(
        self,
        folder,
        output_path,
        metadata_path="",
        recursive=True,
        layer_name="",
        privacy_options=None,
        mount_offset=0.0,
    ):
        folder = os.path.normpath(folder)
        output_path = os.path.normpath(output_path)

        if not os.path.isdir(folder):
            raise ValueError("Select a valid image folder.")
        if not output_path.lower().endswith(".shp"):
            output_path += ".shp"
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.isdir(output_dir):
            raise ValueError("Select a valid output folder.")
        if privacy_options is None:
            privacy_options = PrivacyOptions()
        if privacy_options.enabled and not privacy_options.output_folder:
            privacy_options.output_folder = os.path.join(
                folder, "camera_bottom_hidden_images"
            )

        metadata = self._read_metadata(metadata_path)
        images = self._image_paths(folder, recursive)
        if not images:
            raise ValueError("No JPG/TIFF images were found in the selected folder.")

        display_name = layer_name.strip() or os.path.splitext(os.path.basename(output_path))[0]
        memory_layer = self._create_memory_layer(display_name)
        provider = memory_layer.dataProvider()

        records = []
        skipped = 0
        order = 1

        for image_path in images:
            image_meta = self._read_image_metadata(image_path)
            csv_meta = self._metadata_for_image(metadata, image_path)
            csv_values = {k: v for k, v in csv_meta.items() if v not in ("", None)}
            orientation_meta = {
                key: image_meta.get(key)
                for key in (
                    "direction",
                    "pose_heading",
                    "gps_img_direction",
                    "gps_track",
                    "yaw_source",
                    "pitch",
                    "roll",
                )
            }
            image_meta.update(csv_values)
            for key in orientation_meta:
                image_meta.pop(key, None)
            image_meta.update(
                {
                    key: value
                    for key, value in orientation_meta.items()
                    if value not in ("", None)
                }
            )

            latitude = self._first_float(
                image_meta, ("latitude", "lat", "y", "gpslatitude", "gps_latitude")
            )
            longitude = self._first_float(
                image_meta,
                ("longitude", "long", "lon", "x", "gpslongitude", "gps_longitude"),
            )
            if latitude is None or longitude is None:
                skipped += 1
                continue

            direction = self._rational_float(orientation_meta.get("direction"))
            item_order = self._first_int(image_meta, ("order", "sequence", "seq"))
            if direction is None:
                direction = 0.0
            yaw_source = self._clean_text(orientation_meta.get("yaw_source")) or "default"
            if item_order is None:
                item_order = order
            records.append(
                {
                    "image_path": image_path,
                    "image_meta": image_meta,
                    "latitude": latitude,
                    "longitude": longitude,
                    "direction": direction,
                    "order": item_order,
                    "yaw_source": yaw_source,
                }
            )
            order += 1

        if not records:
            raise ValueError("No images with GPS coordinates were found.")

        gps_heading_count = sum(
            1
            for record in records
            if record["yaw_source"] in ("gps_img_direction", "gps_track")
        )
        default_heading_count = sum(
            1 for record in records if record["yaw_source"] == "default"
        )
        mount_offset = self._rational_float(mount_offset)
        if mount_offset is None:
            mount_offset = 0.0

        features = []
        privacy_skipped = 0
        privacy_processor = PhotoPrivacyProcessor(self.iface)

        for record in records:
            image_path = record["image_path"]
            image_meta = record["image_meta"]
            direction = record["direction"]
            yaw_source = record["yaw_source"]
            applied_offset = 0.0
            if yaw_source in ("gps_img_direction", "gps_track"):
                applied_offset = mount_offset
                direction = (direction + mount_offset) % 360.0

            output_image_path = os.path.normpath(image_path)
            if privacy_options.enabled:
                try:
                    output_image_path = privacy_processor.process_image(
                        image_path,
                        privacy_options.output_folder,
                        privacy_options.mode,
                        privacy_options.bottom_percent,
                    )
                except Exception:
                    privacy_skipped += 1

            feature = QgsFeature(memory_layer.fields())
            feature.setGeometry(
                QgsGeometry.fromPointXY(
                    QgsPointXY(record["longitude"], record["latitude"])
                )
            )
            feature.setAttributes(
                [
                    output_image_path,
                    float(direction),
                    int(record["order"]),
                    os.path.basename(image_path),
                    str(image_meta.get("datetime", "")),
                    float(record["latitude"]),
                    float(record["longitude"]),
                    self._optional_float(image_meta.get("pose_heading")),
                    self._optional_float(image_meta.get("gps_img_direction")),
                    self._optional_float(image_meta.get("gps_track")),
                    yaw_source,
                    self._optional_float(image_meta.get("pitch")),
                    self._optional_float(image_meta.get("roll")),
                    float(applied_offset),
                ]
            )
            features.append(feature)

        provider.addFeatures(features)
        memory_layer.updateExtents()
        self._remove_existing_shapefile(output_path)

        result = QgsVectorFileWriter.writeAsVectorFormat(
            memory_layer,
            output_path,
            "UTF-8",
            QgsCoordinateReferenceSystem("EPSG:4326"),
            "ESRI Shapefile",
        )
        error, message = self._writer_result(result)
        if error != QgsVectorFileWriter.NoError:
            raise ValueError("Could not create shapefile: {}".format(message or error))

        output_layer = QgsVectorLayer(
            output_path, display_name, "ogr"
        )
        if not output_layer.isValid():
            raise ValueError("The shapefile was written but QGIS could not load it.")

        notices = []
        if gps_heading_count and mount_offset:
            notices.append(
                "Camera mount offset of {} deg was applied to GPS-based heading records.".format(
                    self._format_degrees(mount_offset)
                )
            )
        elif gps_heading_count:
            notices.append("GPS-based heading was used without mount offset.")
        if default_heading_count:
            notices.append(
                "Some images did not contain panorama heading metadata. "
                "Their direction was set to 0 by default. Check "
                "yaw_source = default records if orientation is important."
            )

        return output_layer, len(features), skipped + privacy_skipped, notices

    def _format_degrees(self, value):
        if float(value).is_integer():
            return str(int(value))
        return str(round(value, 6))

    def _success_message(self, created, skipped, notices):
        parts = [
            "Created {} point(s). Skipped {} image(s).".format(created, skipped)
        ]
        parts.extend(notices or [])
        return " ".join(parts)

    def _create_memory_layer(self, name):
        layer = QgsVectorLayer("Point?crs=EPSG:4326", name or "photo_points", "memory")
        provider = layer.dataProvider()
        provider.addAttributes(
            [
                QgsField(config.column_name, QVariant.String, "", 254),
                QgsField(config.column_yaw, QVariant.Double, "", 20, 6),
                QgsField(config.column_order, QVariant.Int, "", 10),
                QgsField("filename", QVariant.String, "", 128),
                QgsField("datetime", QVariant.String, "", 32),
                QgsField("latitude", QVariant.Double, "", 20, 8),
                QgsField("longitude", QVariant.Double, "", 20, 8),
                QgsField("pose_head", QVariant.Double, "", 20, 6),
                QgsField("gps_imgdir", QVariant.Double, "", 20, 6),
                QgsField("gps_track", QVariant.Double, "", 20, 6),
                QgsField("yaw_source", QVariant.String, "", 32),
                QgsField("pitch", QVariant.Double, "", 20, 6),
                QgsField("roll", QVariant.Double, "", 20, 6),
                QgsField("mount_off", QVariant.Double, "", 20, 6),
            ]
        )
        layer.updateFields()
        return layer

    def _read_image_metadata(self, image_path):
        metadata = {}
        file_data = self._read_file_bytes(image_path)
        if not file_data:
            return metadata

        exif = self._read_exif_from_data(file_data)
        xmp = self._read_xmp_from_data(file_data)

        for date_tag in ("datetime_original", "datetime_digitized", "datetime"):
            value = exif.get(date_tag)
            if value:
                metadata["datetime"] = self._clean_text(value)
                break

        latitude = self._coordinate(
            exif.get("gps_latitude"), exif.get("gps_latitude_ref")
        )
        longitude = self._coordinate(
            exif.get("gps_longitude"), exif.get("gps_longitude_ref")
        )
        if latitude is not None:
            metadata["latitude"] = latitude
        if longitude is not None:
            metadata["longitude"] = longitude

        pose_heading = self._rational_float(xmp.get("pose_heading"))
        gps_img_direction = self._rational_float(exif.get("gps_img_direction"))
        gps_track = self._rational_float(exif.get("gps_track"))
        pitch = self._rational_float(xmp.get("pitch"))
        roll = self._rational_float(xmp.get("roll"))

        if pose_heading is not None:
            metadata["pose_heading"] = pose_heading
        if gps_img_direction is not None:
            metadata["gps_img_direction"] = gps_img_direction
        if gps_track is not None:
            metadata["gps_track"] = gps_track
        if pitch is not None:
            metadata["pitch"] = pitch
        if roll is not None:
            metadata["roll"] = roll

        direction, yaw_source = self._best_orientation(
            pose_heading, gps_img_direction, gps_track
        )
        metadata["direction"] = direction
        metadata["yaw_source"] = yaw_source

        return metadata

    def _read_exif(self, image_path):
        data = self._read_file_bytes(image_path)
        return self._read_exif_from_data(data)

    def _read_file_bytes(self, image_path):
        try:
            with open(image_path, "rb") as handle:
                return handle.read()
        except Exception:
            return b""

    def _read_exif_from_data(self, data):
        tiff = self._extract_tiff(data)
        if not tiff:
            return {}

        parser = ExifParser(tiff)
        return parser.metadata()

    def _read_xmp_from_data(self, data):
        packet = self._extract_xmp(data)
        if not packet:
            return {}

        try:
            root = ET.fromstring(packet)
        except Exception:
            return {}

        metadata = {}
        fields = {
            "PoseHeadingDegrees": "pose_heading",
            "PosePitchDegrees": "pitch",
            "PoseRollDegrees": "roll",
        }
        for element in root.iter():
            for raw_name, value in element.attrib.items():
                local_name = self._xml_local_name(raw_name)
                if local_name in fields:
                    metadata[fields[local_name]] = self._clean_text(value)
            local_name = self._xml_local_name(element.tag)
            if local_name in fields and element.text:
                metadata[fields[local_name]] = self._clean_text(element.text)
        return metadata

    def _extract_xmp(self, data):
        if data[:2] != b"\xff\xd8":
            return b""

        xmp_header = b"http://ns.adobe.com/xap/1.0/\x00"
        offset = 2
        length = len(data)
        while offset + 4 <= length:
            if data[offset] != 0xFF:
                offset += 1
                continue
            while offset < length and data[offset] == 0xFF:
                offset += 1
            if offset >= length:
                break

            marker = data[offset]
            offset += 1
            if marker in (0xD8, 0xD9):
                continue
            if marker == 0xDA or offset + 2 > length:
                break

            segment_length = struct.unpack(">H", data[offset:offset + 2])[0]
            segment_start = offset + 2
            segment_end = offset + segment_length
            if marker == 0xE1:
                segment = data[segment_start:segment_end]
                if segment.startswith(xmp_header):
                    return segment[len(xmp_header):]
            offset = segment_end
        return b""

    def _xml_local_name(self, name):
        if "}" in name:
            return name.rsplit("}", 1)[1]
        if ":" in name:
            return name.rsplit(":", 1)[1]
        return name

    def _best_orientation(self, pose_heading, gps_img_direction, gps_track):
        for source, value in (
            ("pose_heading", pose_heading),
            ("gps_img_direction", gps_img_direction),
            ("gps_track", gps_track),
        ):
            number = self._rational_float(value)
            if number is not None:
                return number % 360.0, source
        return 0.0, "default"

    def _extract_tiff(self, data):
        if data[:4] in (b"II*\x00", b"MM\x00*"):
            return data
        if data[:2] != b"\xff\xd8":
            return b""

        offset = 2
        length = len(data)
        while offset + 4 <= length:
            if data[offset] != 0xFF:
                offset += 1
                continue
            while offset < length and data[offset] == 0xFF:
                offset += 1
            if offset >= length:
                break

            marker = data[offset]
            offset += 1
            if marker in (0xD8, 0xD9):
                continue
            if marker == 0xDA or offset + 2 > length:
                break

            segment_length = struct.unpack(">H", data[offset:offset + 2])[0]
            segment_start = offset + 2
            segment_end = offset + segment_length
            if marker == 0xE1:
                segment = data[segment_start:segment_end]
                if segment.startswith(b"Exif\x00\x00"):
                    return segment[6:]
            offset = segment_end
        return b""

    def _coordinate(self, value, ref):
        if not value or len(value) < 3:
            return None
        degrees = self._rational_float(value[0])
        minutes = self._rational_float(value[1])
        seconds = self._rational_float(value[2])
        if degrees is None or minutes is None or seconds is None:
            return None
        coordinate = degrees + minutes / 60.0 + seconds / 3600.0
        ref = self._clean_text(ref).upper()
        if ref in ("S", "W"):
            coordinate *= -1
        return coordinate

    def _read_metadata(self, metadata_path):
        if not metadata_path:
            return {}
        metadata_path = os.path.normpath(metadata_path)
        if not os.path.isfile(metadata_path):
            raise ValueError("The selected metadata CSV was not found.")

        rows = {}
        with open(metadata_path, "r", newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                normalized = {
                    self._clean_text(key).lower(): self._clean_text(value)
                    for key, value in row.items()
                    if key is not None
                }
                key = self._metadata_key(normalized)
                if key:
                    rows[key] = normalized
        return rows

    def _metadata_key(self, row):
        for field in ("filename", "file", "image", "photo", "path"):
            value = row.get(field)
            if value:
                return os.path.basename(value).lower()
        return None

    def _metadata_for_image(self, metadata, image_path):
        if not metadata:
            return {}
        basename = os.path.basename(image_path).lower()
        return metadata.get(basename, {})

    def _image_paths(self, folder, recursive):
        paths = []
        if recursive:
            walker = os.walk(folder)
            for root, _, files in walker:
                for file_name in files:
                    if file_name.lower().endswith(IMAGE_EXTENSIONS):
                        paths.append(os.path.join(root, file_name))
        else:
            for file_name in os.listdir(folder):
                path = os.path.join(folder, file_name)
                if os.path.isfile(path) and file_name.lower().endswith(IMAGE_EXTENSIONS):
                    paths.append(path)
        return sorted(paths)

    def _first_float(self, metadata, names):
        for name in names:
            value = metadata.get(name)
            number = self._rational_float(value)
            if number is not None:
                return number
        return None

    def _first_int(self, metadata, names):
        value = self._first_float(metadata, names)
        if value is None:
            return None
        return int(value)

    def _optional_float(self, value):
        number = self._rational_float(value)
        if number is None:
            return None
        return float(number)

    def _rational_float(self, value):
        if value in ("", None):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if hasattr(value, "numerator") and hasattr(value, "denominator"):
            if value.denominator == 0:
                return None
            return float(value.numerator) / float(value.denominator)
        if isinstance(value, (tuple, list)) and len(value) == 2:
            numerator = self._rational_float(value[0])
            denominator = self._rational_float(value[1])
            if numerator is None or denominator in (None, 0):
                return None
            return numerator / denominator
        try:
            return float(str(value).strip())
        except Exception:
            return None

    def _clean_text(self, value):
        if value is None:
            return ""
        if isinstance(value, bytes):
            value = value.decode("utf-8", errors="ignore")
        return str(value).replace("\x00", "").strip()

    def _remove_existing_shapefile(self, output_path):
        root, _ = os.path.splitext(output_path)
        for extension in SHAPEFILE_EXTENSIONS:
            path = root + extension
            if os.path.exists(path):
                os.remove(path)

    def _writer_result(self, result):
        if isinstance(result, tuple):
            error = result[0]
            message = result[1] if len(result) > 1 else ""
            return error, message
        return result, ""

    def _message(self, title, text, level):
        try:
            self.iface.messageBar().pushMessage(title, text, level=level, duration=6)
        except Exception:
            QMessageBox.information(None, title, text)


class ExifParser:
    TYPE_SIZES = {
        1: 1,
        2: 1,
        3: 2,
        4: 4,
        5: 8,
        7: 1,
        9: 4,
        10: 8,
    }
    TAGS = {
        0x0132: "datetime",
        0x8769: "exif_ifd",
        0x8825: "gps_ifd",
        0x9003: "datetime_original",
        0x9004: "datetime_digitized",
    }
    GPS_TAGS = {
        0x0001: "gps_latitude_ref",
        0x0002: "gps_latitude",
        0x0003: "gps_longitude_ref",
        0x0004: "gps_longitude",
        0x000F: "gps_track",
        0x0011: "gps_img_direction",
    }

    def __init__(self, data):
        self.data = data
        self.endian = "<" if data[:2] == b"II" else ">"

    def metadata(self):
        if self.data[:2] not in (b"II", b"MM"):
            return {}
        if self._unpack_short(2) != 42:
            return {}

        first_ifd = self._unpack_long(4)
        result = {}
        root = self._read_ifd(first_ifd, self.TAGS)
        result.update(
            {
                key: value
                for key, value in root.items()
                if key not in ("exif_ifd", "gps_ifd")
            }
        )

        exif_ifd = root.get("exif_ifd")
        if isinstance(exif_ifd, int):
            result.update(self._read_ifd(exif_ifd, self.TAGS))

        gps_ifd = root.get("gps_ifd")
        if isinstance(gps_ifd, int):
            result.update(self._read_ifd(gps_ifd, self.GPS_TAGS))

        return result

    def _read_ifd(self, offset, tag_names):
        result = {}
        if offset is None or offset < 0 or offset + 2 > len(self.data):
            return result

        count = self._unpack_short(offset)
        for index in range(count):
            entry = offset + 2 + index * 12
            if entry + 12 > len(self.data):
                break
            tag = self._unpack_short(entry)
            tag_type = self._unpack_short(entry + 2)
            value_count = self._unpack_long(entry + 4)
            name = tag_names.get(tag)
            if name:
                result[name] = self._read_value(entry + 8, tag_type, value_count)
        return result

    def _read_value(self, value_offset, tag_type, count):
        unit_size = self.TYPE_SIZES.get(tag_type)
        if unit_size is None:
            return None

        total_size = unit_size * count
        if total_size <= 4:
            raw = self.data[value_offset:value_offset + 4][:total_size]
        else:
            data_offset = self._unpack_long(value_offset)
            raw = self.data[data_offset:data_offset + total_size]

        if len(raw) < total_size:
            return None

        if tag_type == 2:
            return raw.split(b"\x00", 1)[0].decode("utf-8", errors="ignore")
        if tag_type in (1, 7):
            values = list(raw)
        elif tag_type == 3:
            values = [
                struct.unpack(self.endian + "H", raw[i:i + 2])[0]
                for i in range(0, total_size, 2)
            ]
        elif tag_type == 4:
            values = [
                struct.unpack(self.endian + "L", raw[i:i + 4])[0]
                for i in range(0, total_size, 4)
            ]
        elif tag_type == 5:
            values = [
                self._rational(raw[i:i + 8], signed=False)
                for i in range(0, total_size, 8)
            ]
        elif tag_type == 9:
            values = [
                struct.unpack(self.endian + "l", raw[i:i + 4])[0]
                for i in range(0, total_size, 4)
            ]
        elif tag_type == 10:
            values = [
                self._rational(raw[i:i + 8], signed=True)
                for i in range(0, total_size, 8)
            ]
        else:
            return None

        if count == 1:
            return values[0]
        return values

    def _rational(self, raw, signed=False):
        fmt = "l" if signed else "L"
        numerator = struct.unpack(self.endian + fmt, raw[:4])[0]
        denominator = struct.unpack(self.endian + fmt, raw[4:])[0]
        if denominator == 0:
            return None
        return float(numerator) / float(denominator)

    def _unpack_short(self, offset):
        return struct.unpack(self.endian + "H", self.data[offset:offset + 2])[0]

    def _unpack_long(self, offset):
        return struct.unpack(self.endian + "L", self.data[offset:offset + 4])[0]
