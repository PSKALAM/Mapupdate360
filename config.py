# Photo layer defaults
#
# The viewer now detects the active point layer automatically. These names are
# used for layers created by the plugin and as the first choices when detecting
# existing layers created by QGIS/ArcGIS tools.
column_name = "path"
column_yaw = "direction"
column_order = "order"

image_field_candidates = (
    column_name,
    "photo",
    "image",
    "image_path",
    "filepath",
    "file_path",
    "filename",
    "file",
)

yaw_field_candidates = (
    column_yaw,
    "bearing",
    "heading",
    "yaw",
    "track",
    "azimuth",
)

order_field_candidates = (
    column_order,
    "sequence",
    "seq",
    "photo_id",
    "id",
)

# Panorama Viewer
IP = "127.0.0.1"
PORT = 1520
