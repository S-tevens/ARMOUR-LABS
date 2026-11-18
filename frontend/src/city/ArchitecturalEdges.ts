import * as THREE from "three";
import { MercatorCoordinate, type CustomLayerInterface, type MapSourceDataEvent, type Map as GeoMap } from "maplibre-gl";

/** Roof and wall edges from the same mapped polygons/heights as the extrusion layer. */
export function architecturalEdges(map: GeoMap) {
  const scene = new THREE.Scene(), camera = new THREE.Camera();
  const material = new THREE.LineBasicMaterial({ color: 0x34434d, transparent: true, opacity: 0.42, depthTest: true, depthWrite: false });
  const lines = new THREE.LineSegments(new THREE.BufferGeometry(), material);
  lines.frustumCulled = false; scene.add(lines);
  const origin = MercatorCoordinate.fromLngLat([77.5946, 12.9716]);
  const unit = origin.meterInMercatorCoordinateUnits();
  const transform = new THREE.Matrix4().set(unit, 0, 0, origin.x, 0, 0, unit, origin.y, 0, unit, 0, 0, 0, 0, 0, 1);
  let renderer: THREE.WebGLRenderer | null = null, signature = "", enabled = true, removed = false;
  let rebuildTimer: ReturnType<typeof setTimeout> | undefined;
  const scheduleRebuild = () => { clearTimeout(rebuildTimer); rebuildTimer = setTimeout(rebuild, 180); };
  const sourceChanged = (e: MapSourceDataEvent) => { if (e.sourceId === "openmaptiles") scheduleRebuild(); };
  const rebuild = () => {
    if (removed || !map.getLayer("architectural-buildings")) return;
    if (map.getZoom() < 14) { lines.visible = false; return; }
    lines.visible = enabled;
    const features = map.queryRenderedFeatures(undefined, { layers: ["architectural-buildings"] });
    const c = map.getCenter();
    const next = `${c.lng.toFixed(5)}:${c.lat.toFixed(5)}:${map.getZoom().toFixed(2)}:${map.getBearing().toFixed(1)}:${map.getPitch().toFixed(1)}:${features.length}`;
    if (next === signature) return; signature = next;
    const coordinates: number[] = [], seen = new Set<string>();
    const point = (p: number[], h: number) => { const m = MercatorCoordinate.fromLngLat([p[0], p[1]]); return [(m.x - origin.x) / unit, h, (m.y - origin.y) / unit]; };
    const edge = (a: number[], b: number[]) => coordinates.push(...a, ...b);
    for (const f of features) {
      if (f.geometry.type !== "Polygon" && f.geometry.type !== "MultiPolygon") continue;
      const polygons = f.geometry.type === "Polygon" ? [f.geometry.coordinates] : f.geometry.coordinates;
      const h = Math.max(3, Number(f.properties.render_height) || 9) + 0.2;
      const base = Number(f.properties.render_min_height) || 0;
      for (const polygon of polygons) for (const ring of polygon) {
        const key = `${f.id}:${ring[0][0]}:${ring[0][1]}:${ring.length}`;
        if (seen.has(key)) continue; seen.add(key);
        for (let i = 0; i < ring.length - 1; i++) {
          edge(point(ring[i], h), point(ring[i + 1], h));
          edge(point(ring[i], base), point(ring[i], h));
        }
      }
      if (coordinates.length > 650000) break;
    }
    lines.geometry.dispose(); lines.geometry = new THREE.BufferGeometry();
    lines.geometry.setAttribute("position", new THREE.Float32BufferAttribute(coordinates, 3));
    map.triggerRepaint();
  };
  const dispose = () => { if (removed) return; removed = true; clearTimeout(rebuildTimer); map.off("idle", rebuild); map.off("moveend", scheduleRebuild); map.off("sourcedata", sourceChanged); lines.geometry.dispose(); material.dispose(); renderer?.dispose(); };
  const layer: CustomLayerInterface = {
    id: "architectural-edges", type: "custom", renderingMode: "3d",
    onAdd(_map, gl) { renderer = new THREE.WebGLRenderer({ canvas: map.getCanvas(), context: gl as WebGL2RenderingContext }); renderer.autoClear = false; map.on("idle", rebuild); map.on("moveend", scheduleRebuild); map.on("sourcedata", sourceChanged); scheduleRebuild(); },
    render(_gl, args) {
      if (!renderer || !enabled || map.getZoom() < 14) return;
      camera.projectionMatrix = new THREE.Matrix4().fromArray(args.defaultProjectionData.mainMatrix).multiply(transform);
      renderer.resetState(); renderer.render(scene, camera); renderer.resetState();
    },
    onRemove: dispose,
  };
  return { layer, dispose, setEnabled(value: boolean) { enabled = value; lines.visible = value; map.triggerRepaint(); } };
}
