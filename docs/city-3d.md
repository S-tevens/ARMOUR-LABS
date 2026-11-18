# Geographical 3D city view

The City tab defaults to a MapLibre view of Bengaluru with OpenFreeMap/OpenMapTiles data derived from OpenStreetMap. It replaces the earlier randomly generated city blocks.

- Building footprints, streets, parks and water follow the vector source geometry.
- Buildings are extruded with the source's `render_height` and `render_min_height`. These fields can contain estimated/default values; they are not surveyed measurements. When height is absent, the view uses 9 metres (minimum rendered height: 3 metres).
- Architectural mode adds roof and vertical wall edges using those same polygons and heights. It does not invent windows, floor counts or facade details.
- Grid coordinates, mapped transmission routes and inferred ties continue to come from the existing backend layout. Inferred ties are dashed. Grid state, power flows, outages and recovery remain simulated.

The default **Grid focus** view frames the featured substation and its surrounding connections. **Highlight grid** is enabled by default: bold blue lines with white casing and glow, larger flow particles, substation voltage labels, and softer buildings. Out-of-service lines turn red and overloaded lines turn amber. Solid lines are mapped routes; dashed lines are inferred connections.

Use **City detail** for the central city model, **Entire grid** to frame all substations, or the substation selector to fly to a location. Click a building for its rendered height and provenance note. Right-drag tilts/rotates; scroll zooms. The existing 2D map remains available.

Internet access is required for vector tiles, fonts and the style. Attribution to OpenFreeMap, OpenMapTiles and OpenStreetMap is retained on the map. MapLibre's worker is served by Vite using an explicit local worker URL.

Sources:
- https://openfreemap.org/quick_start/
- https://maplibre.org/maplibre-gl-js/docs/examples/display-buildings-in-3d/
