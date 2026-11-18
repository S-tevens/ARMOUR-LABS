import { useEffect, useRef, useState } from "react";
import maplibregl, { type GeoJSONSource, type StyleSpecification } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import workerUrl from "maplibre-gl/dist/maplibre-gl-csp-worker.js?url";
import type { FeatureCollection, LineString, Point } from "geojson";
import type { CityLayout, CityState } from "./types";
import { architecturalEdges } from "./ArchitecturalEdges";

const COLORS = { ok: "#10a4bd", attention: "#e79b30", dark: "#e04b61", stale: "#8b9caf" };
maplibregl.setWorkerUrl(workerUrl);
const CITY_CENTER: [number, number] = [77.5946, 12.9716];
const EMPTY: FeatureCollection = { type: "FeatureCollection", features: [] };
type Props = { layout: CityLayout; state: CityState; selected: string | null; onSelect: (id: string) => void; onFallback: () => void };
type Route = { id: string; points: number[][]; distances: number[]; length: number };

function routesFor(layout: CityLayout): Route[] {
  const districts = new Map(layout.districts.map(d => [d.id, d]));
  return layout.lines.flatMap(l => {
    const a = districts.get(l.from), b = districts.get(l.to);
    if (!a || !b || a.lon == null || a.lat == null || b.lon == null || b.lat == null || l.source === "grid-entry") return [];
    const points = l.path?.length ? l.path.map(([lat, lon]) => [lon, lat]) : [[a.lon, a.lat], [b.lon, b.lat]];
    const distances = [0];
    for (let i = 1; i < points.length; i++) distances.push(distances[i - 1] + Math.hypot((points[i][0] - points[i - 1][0]) * Math.cos(points[i][1] * Math.PI / 180), points[i][1] - points[i - 1][1]));
    return [{ id: l.id, points, distances, length: distances[distances.length - 1] }];
  });
}
function routePoint(route: Route, fraction: number) {
  const target = fraction * route.length;
  let i = 1;
  while (i < route.distances.length - 1 && route.distances[i] < target) i++;
  const a = route.points[i - 1], b = route.points[i];
  const f = (target - route.distances[i - 1]) / (route.distances[i] - route.distances[i - 1] || 1);
  return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f];
}

/** Geographical 3D: OSM footprints and streets, source heights, live simulated grid. */
export default function City3DMap({ layout, state, selected, onSelect, onFallback }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const updateRef = useRef<(() => void) | null>(null);
  const edgesRef = useRef<ReturnType<typeof architecturalEdges> | null>(null);
  const latest = useRef({ state, selected, onSelect }); latest.current = { state, selected, onSelect };
  const [orbiting, setOrbiting] = useState(false);
  const orbit = useRef(false);
  const [failed, setFailed] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [detail, setDetail] = useState(true);
  const [ink, setInk] = useState(true);
  const [building, setBuilding] = useState<{ height: number; levels: string } | null>(null);
  const [zoom, setZoom] = useState(15.8);

  useEffect(() => {
    if (!host.current) return;
    const controller = new AbortController();
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let disposed = false, map: maplibregl.Map | undefined, animation = 0;
    const markers: { id: string; marker: maplibregl.Marker; button: HTMLButtonElement }[] = [];
    const routes = routesFor(layout);
    const setup = async () => {
      try {
        const response = await fetch("https://tiles.openfreemap.org/styles/positron", { signal: controller.signal });
        if (!response.ok) throw new Error("Map style unavailable");
        const style = await response.json() as StyleSpecification;
        // Architectural base: retain actual street geometry, parks, water and place labels.
        style.layers = style.layers.filter(l => l.id !== "building" && !l.id.includes("poi") && !l.id.includes("housenumber"));
        for (const layer of style.layers) {
          if (layer.type === "background") layer.paint = { ...layer.paint, "background-color": "#edf0f0" };
          if (layer.type === "fill") {
            if (layer.id.includes("water")) layer.paint = { ...layer.paint, "fill-color": "#cadce1" };
            else if (layer.id.includes("park") || layer.id.includes("wood")) layer.paint = { ...layer.paint, "fill-color": "#dae4dc" };
            else layer.paint = { ...layer.paint, "fill-color": "#e9edeb" };
          }
          if (layer.type === "symbol") layer.paint = { ...layer.paint, "text-color": "#6c7a82", "text-halo-color": "#ffffff", "text-halo-width": 1.5 };
        }
        if (disposed) return;
        map = new maplibregl.Map({ container: host.current!, style, center: CITY_CENTER, zoom: 15.8, pitch: 58, bearing: -28, maxPitch: 75, minZoom: 9, maxZoom: 19, attributionControl: false, canvasContextAttributes: { antialias: true } });
        mapRef.current = map;
        map.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-right");
        map.addControl(new maplibregl.ScaleControl({ maxWidth: 90, unit: "metric" }), "bottom-left");
        map.touchZoomRotate.enableRotation();
        map.on("error", e => { console.warn("City map resource:", e.error.message); });
        map.on("zoomend", () => { if (!map) return; setZoom(map.getZoom()); setDetail(map.getZoom() >= 14); });
        map.on("dragstart", () => { orbit.current = false; setOrbiting(false); });
        map.on("load", () => {
          if (!map || disposed) return;
          const labelLayer = map.getStyle().layers.find(l => l.type === "symbol")?.id;
          map.setLight({ anchor: "viewport", color: "#ffffff", intensity: 0.52, position: [1.5, 190, 45] });
          map.addLayer({ id: "architectural-buildings", type: "fill-extrusion", source: "openmaptiles", "source-layer": "building", minzoom: 13,
            filter: ["!=", ["get", "hide_3d"], true],
            paint: { "fill-extrusion-color": "#fafbfc", "fill-extrusion-height": ["max", 3, ["to-number", ["get", "render_height"], 9]], "fill-extrusion-base": ["to-number", ["get", "render_min_height"], 0], "fill-extrusion-opacity": 1, "fill-extrusion-vertical-gradient": true } }, labelLayer);
          map.addLayer({ id: "footprint-outlines", type: "line", source: "openmaptiles", "source-layer": "building", minzoom: 14, paint: { "line-color": "#737e86", "line-width": 0.55, "line-opacity": 0.5 } }, "architectural-buildings");
          edgesRef.current = architecturalEdges(map);
          map.addLayer(edgesRef.current.layer);
          map.addSource("live-grid", { type: "geojson", data: EMPTY });
          map.addLayer({ id: "grid-glow", type: "line", source: "live-grid", paint: { "line-color": ["get", "color"], "line-width": 8, "line-opacity": 0.12, "line-blur": 4 } });
          map.addLayer({ id: "grid-mapped", type: "line", source: "live-grid", filter: ["==", ["get", "source"], "osm"], paint: { "line-color": ["get", "color"], "line-width": 2.2, "line-opacity": 0.9 } });
          map.addLayer({ id: "grid-inferred", type: "line", source: "live-grid", filter: ["!=", ["get", "source"], "osm"], paint: { "line-color": ["get", "color"], "line-width": 1.5, "line-opacity": 0.5, "line-dasharray": [3, 3] } });
          map.addSource("flow-particles", { type: "geojson", data: EMPTY });
          map.addLayer({ id: "flow-particles", type: "circle", source: "flow-particles", paint: { "circle-radius": 2.5, "circle-color": "#19bfd8", "circle-stroke-width": 1, "circle-stroke-color": "#ffffff" } });
          for (const d of layout.districts) {
            if (d.lat == null || d.lon == null) continue;
            const button = document.createElement("button"); button.className = "geo-substation"; button.type = "button";
            button.innerHTML = '<span class="geo-beacon"><i></i></span><span class="geo-node-name"></span>';
            button.querySelector(".geo-node-name")!.textContent = d.name;
            button.setAttribute("aria-label", `Select ${d.name} substation`);
            button.onclick = e => { e.stopPropagation(); latest.current.onSelect(d.id); };
            const marker = new maplibregl.Marker({ element: button, anchor: "bottom" }).setLngLat([d.lon, d.lat]).addTo(map);
            markers.push({ id: d.id, marker, button });
          }
          const sync = () => {
            if (!map || !map.getSource("live-grid")) return;
            const current = latest.current;
            const lines = new Map(current.state.lines.map(l => [l.id, l]));
            const data: FeatureCollection<LineString> = { type: "FeatureCollection", features: routes.map(r => {
              const s = lines.get(r.id), l = layout.lines.find(l => l.id === r.id)!;
              const color = s && s.status !== "in_service" ? COLORS.dark : s && s.loading > 0.9 ? COLORS.attention : COLORS.ok;
              return { type: "Feature", properties: { id: r.id, color, source: l.source }, geometry: { type: "LineString", coordinates: r.points } };
            }) };
            (map.getSource("live-grid") as GeoJSONSource).setData(data);
            for (const n of markers) {
              const s = current.state.districts.find(d => d.id === n.id);
              n.button.style.setProperty("--node-color", COLORS[s?.status ?? "stale"]);
              n.button.classList.toggle("is-dark", s?.status === "dark"); n.button.classList.toggle("is-selected", n.id === current.selected);
              n.button.setAttribute("aria-label", `Select ${layout.districts.find(d => d.id === n.id)?.name}, ${s?.status === "dark" ? "without power" : s?.status ?? "no data"}`);
            }
          };
          updateRef.current = sync; sync(); setLoaded(true);
          let lastTime = 0;
          const animate = (time: number) => {
            animation = requestAnimationFrame(animate);
            if (!map || time - lastTime < 70) return; lastTime = time;
            if (orbit.current && !reduced) map.jumpTo({ bearing: map.getBearing() + 0.035 });
            const states = new Map(latest.current.state.lines.map(l => [l.id, l]));
            const dots: FeatureCollection<Point> = { type: "FeatureCollection", features: [] };
            for (const route of routes) {
              const s = states.get(route.id); if (!s || s.status !== "in_service" || Math.abs(s.flow_mw) < 1) continue;
              for (let i = 0; i < 3; i++) { const fraction = reduced ? i / 3 : (time * 0.00006 + i / 3) % 1;
                dots.features.push({ type: "Feature", properties: {}, geometry: { type: "Point", coordinates: routePoint(route, s.flow_mw < 0 ? 1 - fraction : fraction) } }); }
            }
            (map.getSource("flow-particles") as GeoJSONSource)?.setData(dots);
          };
          animation = requestAnimationFrame(animate);
          map.on("click", "architectural-buildings", e => {
            const p = e.features?.[0]?.properties; if (!p) return;
            setBuilding({ height: Number(p.render_height) || 9, levels: p["building:levels"] ? String(p["building:levels"]) : "Not available" });
          });
          map.on("mouseenter", "architectural-buildings", () => { if (map) map.getCanvas().style.cursor = "pointer"; });
          map.on("mouseleave", "architectural-buildings", () => { if (map) map.getCanvas().style.cursor = ""; });
        });
      } catch (error) { if (!disposed) { console.warn("3D map unavailable", error); setFailed(true); } }
    };
    void setup();
    return () => { disposed = true; controller.abort(); cancelAnimationFrame(animation); updateRef.current = null; edgesRef.current?.dispose(); edgesRef.current = null; mapRef.current = null; markers.forEach(m => m.marker.remove()); map?.remove(); };
  }, [layout]);

  useEffect(() => { updateRef.current?.(); }, [state, selected]);
  useEffect(() => {
    const map = mapRef.current; const d = layout.districts.find(d => d.id === selected);
    if (map && d && d.lon != null && d.lat != null) map.flyTo({ center: [d.lon, d.lat], zoom: 15.7, pitch: 58, duration: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 1500 });
  }, [selected, layout]);
  const overview = () => {
    const map = mapRef.current; if (!map) return;
    orbit.current = false; setOrbiting(false); setBuilding(null);
    const bounds = new maplibregl.LngLatBounds(); layout.districts.forEach(d => { if (d.lon != null && d.lat != null) bounds.extend([d.lon, d.lat]); });
    map.fitBounds(bounds, { padding: { top: 180, bottom: 130, left: 65, right: 65 }, pitch: 30, bearing: -12, duration: 1400 });
  };
  const cityDetail = () => { orbit.current = false; setOrbiting(false); setBuilding(null); mapRef.current?.flyTo({ center: CITY_CENTER, zoom: 15.8, pitch: 58, bearing: -28, duration: 1400 }); };
  const toggleInk = () => {
    const map = mapRef.current; if (!map?.getLayer("architectural-buildings")) return;
    setInk(!ink);
    edgesRef.current?.setEnabled(!ink);
    map.setPaintProperty("architectural-buildings", "fill-extrusion-color", ink ? "#e2eaf1" : "#fafbfc");
    map.setPaintProperty("footprint-outlines", "line-opacity", ink ? 0.15 : 0.5);
    map.setLight({ intensity: ink ? 0.3 : 0.52 });
  };
  return <div className={`city3d geographical ${detail ? "detail" : "overview"} ${ink ? "architectural" : "soft"}`}>
    <div ref={host} className="city3d-canvas" role="application" aria-label="Geographical 3D Bengaluru map. Drag to pan, right-drag to tilt and rotate, scroll to zoom. Real building footprints from OpenStreetMap." />
    <div className="city3d-heading"><span className="city3d-kicker">ARMOUR / GEOGRAPHICAL DIGITAL TWIN</span><h2>Bengaluru, in real detail.</h2><p><i /> {detail ? "Architectural detail" : "Grid overview"} · {layout.districts.length} live substations</p></div>
    <div className="city3d-search"><span aria-hidden="true">⌕</span><select aria-label="Locate a substation" value={selected ?? ""} onChange={e => { if (e.target.value) { setBuilding(null); onSelect(e.target.value); } }}><option value="">Fly to a substation</option>{layout.districts.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}</select></div>
    <div className="geo-view-controls"><button className={detail ? "active" : ""} onClick={cityDetail}>City detail</button><button className={!detail ? "active" : ""} onClick={overview}>Entire grid</button><button aria-pressed={ink} onClick={toggleInk}>{ink ? "Architectural" : "Soft model"}</button></div>
    <div className="city3d-tools"><button onClick={() => mapRef.current?.zoomIn()} aria-label="Zoom in">+</button><button onClick={() => mapRef.current?.zoomOut()} aria-label="Zoom out">−</button><span /><button onClick={cityDetail} aria-label="Reset camera">⌖</button><button className={orbiting ? "active" : ""} aria-pressed={orbiting} onClick={() => { orbit.current = !orbit.current; setOrbiting(orbit.current); }} aria-label="Toggle cinematic orbit">↻</button><button onClick={() => { const parent = host.current?.parentElement?.parentElement; if (document.fullscreenElement) void document.exitFullscreen(); else void parent?.requestFullscreen?.().catch(() => {}); }} aria-label="Expand map fullscreen">⛶</button></div>
    <div className="city3d-footer"><span>Right-drag to tilt · Scroll to explore · z{zoom.toFixed(1)}</span><span>OSM footprints · Heights from source or estimates</span></div>
    <div className="geo-data-note">Mapped streets, parks & water · Building heights are not surveyed</div>
    {!loaded && !failed && <div className="geo-loading" role="status">Loading mapped city geometry…</div>}
    {building && <div className="geo-building-card"><button className="geo-close" onClick={() => setBuilding(null)} aria-label="Close building details">×</button><span className="city3d-kicker">MAPPED BUILDING</span><h3>Real footprint. Source height.</h3><strong>{building.height.toFixed(1)} m</strong><p>Rendered height from the tile source, which can include defaults. Not a surveyed measurement.</p></div>}
    {failed && <div className="city3d-fallback"><h3>Map data could not load</h3><p>An internet connection is needed for building tiles.</p><button className="btn primary" onClick={onFallback}>Open 2D map</button></div>}
  </div>;
}
