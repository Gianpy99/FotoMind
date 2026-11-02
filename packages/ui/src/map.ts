import L from "leaflet";
import "leaflet/dist/leaflet.css";

// OpenStreetMap's public tiles: fine for a family library's light use (tile usage policy:
// valid attribution, no bulk downloading). Place names come from the offline GeoNames file.
export const OSM_TILES = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
export const MAP_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a> contributors · places &copy; <a href="https://www.geonames.org/" target="_blank" rel="noreferrer">GeoNames</a>';
export const MAX_ZOOM = 18;

/** A Leaflet map with OSM tiles; the dark theme dims the tiles through CSS. */
export function createMap(element: HTMLElement, options: L.MapOptions = {}): L.Map {
  const map = L.map(element, {
    worldCopyJump: true,
    minZoom: 2,
    maxZoom: MAX_ZOOM,
    ...options,
  });
  L.tileLayer(OSM_TILES, { maxZoom: MAX_ZOOM, attribution: MAP_ATTRIBUTION }).addTo(map);
  map.attributionControl.setPrefix(false);
  // Leaflet only watches the window; layouts (panels, breakpoints, dialogs) resize the box too.
  if (typeof ResizeObserver !== "undefined") {
    const observer = new ResizeObserver(() => map.invalidateSize({ pan: false }));
    observer.observe(element);
    map.on("unload", () => observer.disconnect());
  }
  return map;
}

export function formatCoords(latitude: number, longitude: number): string {
  const lat = `${Math.abs(latitude).toFixed(4)}° ${latitude >= 0 ? "N" : "S"}`;
  const lon = `${Math.abs(longitude).toFixed(4)}° ${longitude >= 0 ? "E" : "W"}`;
  return `${lat}, ${lon}`;
}

export { L };
