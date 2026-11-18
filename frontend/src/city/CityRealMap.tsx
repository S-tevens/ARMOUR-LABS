import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useEffect, useRef } from "react";
import type { CityLayout, CityState, DistrictState, FacilityStatus, LineState } from "./types";

// Free basemap: the official OpenStreetMap tiles (no key needed; attribution required, and fine for a demo, but self-host
// or use a tile provider for heavy production use). The pale look comes from a CSS filter on the tile pane.
const TILES = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
const STATUS_COLOR: Record<string, string> = { ok: "#2DB56A", attention: "#F0A030", dark: "#E5484D", stale: "#8A94AD" };
const FAC_GLYPH: Record<string, string> = { hospital: "+", metro: "M", airport: "A", water: "W", tech: "T" };
const FAC_ZOOM = 12; // facilities appear when zoomed in this far

interface Refs {
  map: L.Map;
  nodes: Map<string, L.CircleMarker>;
  labelled: Map<string, boolean>;
  lines: Map<string, { base: L.Polyline; flow: L.Polyline; source: string }>;
  facs: Map<string, L.Marker>;
  facLayer: L.LayerGroup;
}

function radius(load: number, entry: boolean) {
  return entry ? 11 : Math.max(6, Math.min(12, 4 + Math.sqrt(load) * 0.9));
}

/** The real city map. Substations, mapped line routes and facilities come from OpenStreetMap; the live overlay is simulated. */
export default function CityRealMap({
  layout, state, selected, onSelect,
}: { layout: CityLayout; state: CityState; selected: string | null; onSelect: (id: string) => void }) {
  const host = useRef<HTMLDivElement>(null);
  const refs = useRef<Refs | null>(null);
  const latest = useRef({ state, layout, onSelect });
  latest.current = { state, layout, onSelect };

  // build the map once per layout
  useEffect(() => {
    if (!host.current) return;
    const map = L.map(host.current, { zoomControl: true, zoomSnap: 0.25, attributionControl: true });
    L.tileLayer(TILES, {
      maxZoom: 19,
      attribution: layout.attribution ?? "© OpenStreetMap contributors",
    }).addTo(map);
    const byId = new Map(layout.districts.map((d) => [d.id, d]));
    const located = layout.districts.filter((d) => d.lat != null && d.lon != null);
    map.fitBounds(L.latLngBounds(located.map((d) => L.latLng(d.lat!, d.lon!))).pad(0.1));

    // real 66 kV substations, as quiet context
    for (const f of layout.feeders) {
      L.circleMarker([f.lat, f.lon], { radius: 2.5, color: "#9AA6C3", weight: 1, fillColor: "#fff", fillOpacity: 1, interactive: false })
        .bindTooltip(`${f.name}, ${f.voltage_kv} kV`, { className: "map-tip" }).addTo(map);
    }

    const lines: Refs["lines"] = new Map();
    for (const ln of layout.lines) {
      if (ln.source === "grid-entry") continue;
      const a = byId.get(ln.from), b = byId.get(ln.to);
      if (!a || !b || a.lat == null || b.lat == null) continue;
      const pts = ln.path ? ln.path.map((p) => L.latLng(p[0], p[1])) : [L.latLng(a.lat, a.lon!), L.latLng(b.lat, b.lon!)];
      const base = L.polyline(pts, { weight: 4, opacity: 0.9, color: "#7E96C8", lineCap: "round" }).addTo(map);
      const flow = L.polyline(pts, { className: "map-flow", weight: 3, opacity: 0, color: "#2F6BFF", dashArray: "2 12", interactive: false }).addTo(map);
      base.bindTooltip(() => {
        const s = latest.current.state.lines.find((l) => l.id === ln.id);
        const src = ln.source === "osm" ? "mapped in OpenStreetMap" : "inferred tie, not mapped";
        const load = s && s.status === "in_service" ? `${Math.abs(s.flow_mw).toFixed(0)} MW, ${Math.round(s.loading * 100)}% of its rating` : s?.status === "open" ? "open for maintenance" : "out of service";
        return `${a.name} to ${b.name}<br/>${ln.voltage_kv ?? ""} kV, ${src}<br/>${load}`;
      }, { sticky: true, className: "map-tip" });
      lines.set(ln.id, { base, flow, source: ln.source ?? "inferred" });
    }

    const nodes: Refs["nodes"] = new Map();
    for (const d of located) {
      const m = L.circleMarker([d.lat!, d.lon!], {
        radius: radius(d.base_load_mw ?? 20, !!d.entry), color: "#fff", weight: 2, fillColor: STATUS_COLOR.ok, fillOpacity: 1,
      }).addTo(map);
      m.on("click", () => latest.current.onSelect(d.id));
      m.bindTooltip(`${d.name}, ${d.voltage_kv ?? ""} kV`, { direction: "top", offset: [0, -8], className: "map-tip" });
      nodes.set(d.id, m);
    }

    const facLayer = L.layerGroup();
    const facs: Refs["facs"] = new Map();
    for (const d of located) {
      for (const f of d.facilities) {
        if (f.lat == null || f.lon == null) continue;
        const icon = L.divIcon({ className: `fac-icon ${f.type}`, html: `<span>${FAC_GLYPH[f.type] ?? "?"}</span>`, iconSize: [18, 18] });
        const mk = L.marker([f.lat, f.lon], { icon, keyboard: false }).bindTooltip(`${f.name ?? f.type} (supplied via ${d.name})`, { className: "map-tip" });
        facLayer.addLayer(mk);
        facs.set(f.id, mk);
      }
    }
    const syncFacilities = () => {
      if (map.getZoom() >= FAC_ZOOM) { if (!map.hasLayer(facLayer)) map.addLayer(facLayer); } else if (map.hasLayer(facLayer)) map.removeLayer(facLayer);
    };
    map.on("zoomend", syncFacilities);
    syncFacilities();

    refs.current = { map, nodes, labelled: new Map(), lines, facs, facLayer };
    setTimeout(() => map.invalidateSize(), 50);
    return () => {
      map.remove();
      refs.current = null;
    };
  }, [layout]);

  // restyle on every state change; nothing is recreated
  useEffect(() => {
    const r = refs.current;
    if (!r) return;
    const byLine = new Map<string, LineState>(state.lines.map((l) => [l.id, l]));
    for (const [id, { base, flow, source }] of r.lines) {
      const s = byLine.get(id);
      if (!s) continue;
      const out = s.status !== "in_service";
      const flowing = !out && Math.abs(s.flow_mw) > 1;
      const hot = s.loading > 1 ? "#E5484D" : s.loading > 0.9 ? "#F0A030" : null;
      base.setStyle({
        color: out ? (s.status === "open" ? "#9AA4BC" : "#E5484D") : hot ?? (source === "osm" ? "#6F8BC4" : "#AEBBD8"),
        weight: out ? 3 : 3 + 3 * Math.min(s.loading, 1.2),
        dashArray: out ? "3 8" : source === "inferred" ? "7 7" : undefined,
        opacity: out ? 0.9 : 0.95,
      });
      flow.setStyle({ opacity: flowing ? 1 : 0, color: hot ?? "#2F6BFF" });
      const el = flow.getElement() as SVGElement | undefined;
      if (el) {
        el.classList.toggle("rev", s.flow_mw < 0);
        el.style.animationDuration = `${Math.max(0.5, 3 - Math.abs(s.flow_mw) / 60)}s`;
      }
    }
    const byDistrict = new Map<string, DistrictState>(state.districts.map((d) => [d.id, d]));
    for (const [id, m] of r.nodes) {
      const d = byDistrict.get(id);
      if (!d) continue;
      const isSel = id === selected;
      m.setStyle({ fillColor: STATUS_COLOR[d.status], color: isSel ? "#2F6BFF" : "#fff", weight: isSel ? 4 : 2 });
      (m.getElement() as SVGElement | undefined)?.classList.toggle("node-dark", d.status === "dark");
      // a name label for entry points and for anything that has failed; everything else shows its name on hover
      const lay = latest.current.layout.districts.find((x) => x.id === id);
      const want = !!lay?.entry || d.status === "dark" || d.status === "stale" || isSel;
      if (r.labelled.get(id) !== want) {
        r.labelled.set(id, want);
        m.unbindTooltip();
        m.bindTooltip(lay ? `${lay.name}${lay.voltage_kv ? `, ${lay.voltage_kv} kV` : ""}` : d.name, {
          permanent: want, direction: "top", offset: [0, -8], className: want ? "map-label" : "map-tip",
        });
      }
    }
    for (const d of state.districts) {
      for (const f of d.facilities) {
        const el = r.facs.get(f.id)?.getElement();
        if (el) for (const s of ["ok", "backup", "down"] as FacilityStatus[]) el.classList.toggle(`st-${s}`, f.status === s);
      }
    }
  }, [state, selected]);

  // bring the selected substation into view
  useEffect(() => {
    const r = refs.current;
    const d = selected ? layout.districts.find((x) => x.id === selected) : null;
    if (r && d && d.lat != null && d.lon != null && !r.map.getBounds().pad(-0.25).contains([d.lat, d.lon])) {
      r.map.panTo([d.lat, d.lon], { animate: true });
    }
  }, [selected, layout]);

  return <div ref={host} className="realmap" role="application" aria-label="Map of the Bengaluru power grid" />;
}
