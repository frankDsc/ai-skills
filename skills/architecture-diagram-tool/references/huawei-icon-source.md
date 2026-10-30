# Huawei Cloud icon bundle

Use the bundled XML libraries instead of fetching icons at render time.

- Source repository: [huaweicloud-latam/drawio-libraries](https://github.com/huaweicloud-latam/drawio-libraries)
- Version: `v3.2`
- Source commit: `52c33aa12fb816a5de403da85067e1c0f039b5be`
- Default path: `../assets-huawei-cloud-color/` — current color libraries used for Huawei Cloud console/product visuals.
- Compatibility path: `../assets-huawei-cloud-line/` — legacy line libraries; use only when a monochrome style is explicitly requested.

The XML files are Draw.io `mxlibrary` files containing service entries with embedded SVG/data-URI content. Select an exact service entry, preserve its official icon artwork, and embed the local SVG/data URI in HTML/SVG output. Do not invent a Huawei service icon when the bundle does not contain the requested product; use a clearly labeled generic boundary or note the limitation.
