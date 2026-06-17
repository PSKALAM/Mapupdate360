# Changelog

## 1.2

- Reworked GPano/XMP metadata reading to avoid XML parsing of untrusted image metadata.
- Kept support for `PoseHeadingDegrees`, pitch, and roll using a lightweight metadata text scanner.
- Removed the development `compile.sh` shell script from the upload package to satisfy QGIS suspicious file security checks.
- Prepared the package for a fresh QGIS Plugin Repository security scan.

## 1.1

- Added GPano/XMP panorama orientation metadata support for `PoseHeadingDegrees`, pitch, and roll.
- Added raw heading audit fields: `pose_head`, `gps_imgdir`, `gps_track`, `yaw_source`, and `mount_off`.
- Added optional camera mount offset correction in the Create Photo Point Layer dialog for GPSImgDirection and GPSTrack based heading.
- Added a clear notice when images have no heading metadata and their `direction` is set to `0`.
- Kept existing viewer behavior backward compatible by continuing to use the `direction` field.

## 1.0

- Released plugin as **Mapupdate360**.
- Added publish-ready metadata for QGIS Plugin Repository and GitHub.
- Added author attribution for Pankaj Singh Kalam.
- Retained credit to the original Equirectangular Viewer by Francisco Raga / All4GIS.
- Added photo point layer creation from geotagged images.
- Removed hard-coded photo layer name requirement.
- Added live dynamic map frustum that updates with panorama pan and zoom/FOV.
- Added image brightness, contrast, and saturation controls.
- Added camera-bottom blur/cover privacy processing while creating photo layers.
- Added **Hide/Blur Camera Bottom** tool for existing photo layers.
