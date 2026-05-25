# Mapupdate360

**Mapupdate360** is a QGIS plugin for using local 360/equirectangular
street-view images to support 2D GIS map updating and field-context
visualization.

The plugin can create photo point layers from geotagged 360 images, open linked
equirectangular images in a dockable viewer, show a live map frustum while the
image is panned or zoomed, and provide quick image enhancement controls.

## Main Features

- Create a point shapefile/photo layer directly from geotagged JPG/TIFF images.
- Read GPS latitude, longitude, date/time, and GPS track/image direction from EXIF.
- Use flexible image path fields instead of a hard-coded layer name.
- Open local equirectangular/360 images in QGIS using Marzipano.
- Navigate previous/next images using an order field.
- Show a live direction frustum on the map that updates with image pan and zoom/FOV.
- Adjust brightness, contrast, and saturation inside the viewer.
- Create privacy-safe image copies using bottom/camera-nadir blur or cover masking.
- Generate a new layer from an existing photo layer using **Hide/Blur Camera Bottom**.

## Publishing Notes

The Python package/internal plugin folder is named `Mapupdate360`, while the
public plugin name shown in QGIS is **Mapupdate360**.

Before uploading to the official QGIS Plugin Repository, replace the placeholder
email in `metadata.txt`:

```ini
email=replace-with-your-email@example.com
```

Suggested GitHub repository:

```text
https://github.com/pankajsinghkalam/Mapupdate360
```

## Credits

Author and maintainer: **Pankaj Singh Kalam**

This plugin is derived from the original **Equirectangular Viewer** QGIS plugin
by **Francisco Raga / All4GIS**.

Original project:
https://github.com/All4Gis/EquirectangularViewer

The original plugin provided local equirectangular image visualization in QGIS
using Marzipano. Mapupdate360 builds on that foundation with photo point layer
creation, flexible layer detection, live frustum updates, image enhancement, and
privacy masking workflows for 360-image-assisted GIS updating.

## License

Mapupdate360 is distributed under **GPL-3.0-or-later**.

The original Equirectangular Viewer plugin was distributed under GPL version 2
or later. Under that license grant, this derivative is released under GPL-3.0
or later.
