import { useEffect, useRef, useState } from "react";
import { MapPin, Search } from "lucide-react";
import type { FotoMindClient, Place } from "@fotomind/api-client";
import { L, createMap, formatCoords } from "./map";

export interface PickedLocation {
  latitude: number;
  longitude: number;
  label: string;
}

export interface LocationPickerProps {
  client: FotoMindClient;
  value: PickedLocation | null;
  onChange(value: PickedLocation): void;
}

const SEARCH_DEBOUNCE_MS = 250;

/** Choose a position by place search, by clicking the map, or by typing coordinates. */
export function LocationPicker({ client, value, onChange }: LocationPickerProps) {
  const [text, setText] = useState("");
  const [results, setResults] = useState<Place[]>([]);
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const markerRef = useRef<L.Marker | null>(null);
  const onChangeRef = useRef(onChange);
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => {
    onChangeRef.current = onChange;
  });

  useEffect(() => {
    const element = containerRef.current;
    if (!element) return;
    const map = createMap(element, { minZoom: 1 });
    map.setView([30, 10], 2);
    map.on("click", (event: L.LeafletMouseEvent) => {
      const { lat, lng } = event.latlng.wrap();
      onChangeRef.current({
        latitude: Number(lat.toFixed(6)),
        longitude: Number(lng.toFixed(6)),
        label: "",
      });
    });
    mapRef.current = map;
    return () => {
      window.clearTimeout(timer.current);
      map.remove();
      mapRef.current = null;
      markerRef.current = null;
    };
  }, []);

  const lat = value?.latitude;
  const lon = value?.longitude;
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (lat === undefined || lon === undefined) {
      markerRef.current?.remove();
      markerRef.current = null;
      return;
    }
    const icon = L.divIcon({ className: "fm-map-pin", iconSize: [18, 18] });
    if (markerRef.current) markerRef.current.setLatLng([lat, lon]);
    else markerRef.current = L.marker([lat, lon], { icon, keyboard: false }).addTo(map);
    if (!map.getBounds().pad(-0.2).contains([lat, lon])) {
      map.setView([lat, lon], Math.max(map.getZoom(), 10));
    }
  }, [lat, lon]);

  function search(next: string) {
    setText(next);
    window.clearTimeout(timer.current);
    const q = next.trim();
    if (!q) {
      setResults([]);
      return;
    }
    timer.current = window.setTimeout(() => {
      client.searchPlaces(q, 8).then(setResults, () => setResults([]));
    }, SEARCH_DEBOUNCE_MS);
  }

  function pick(place: Place) {
    setText("");
    setResults([]);
    onChange({ latitude: place.latitude, longitude: place.longitude, label: place.label });
  }

  function setCoord(field: "latitude" | "longitude", raw: string) {
    const number = Number(raw);
    if (raw.trim() === "" || !Number.isFinite(number)) return;
    onChange({
      latitude: field === "latitude" ? number : (value?.latitude ?? 0),
      longitude: field === "longitude" ? number : (value?.longitude ?? 0),
      label: "",
    });
  }

  return (
    <div className="fm-location-picker">
      <div className="fm-place-search">
        <Search aria-hidden="true" />
        <input
          type="search"
          aria-label="Search places"
          placeholder="Search a city or country…"
          value={text}
          onChange={(e) => search(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              if (results[0]) pick(results[0]);
            }
          }}
        />
      </div>
      {results.length > 0 && (
        <ul className="fm-place-results" aria-label="Places">
          {results.map((place) => (
            <li key={`${place.label}-${place.latitude}`}>
              <button type="button" onClick={() => pick(place)}>
                <MapPin aria-hidden="true" />
                <span>{place.label}</span>
                {place.kind === "country" && <span className="fm-pill">country</span>}
              </button>
            </li>
          ))}
        </ul>
      )}
      <div
        ref={containerRef}
        className="fm-map fm-map-mini"
        role="application"
        aria-label="Map: click to set the position"
      />
      <div className="fm-coords">
        <label>
          Latitude
          <input
            key={`lat-${lat ?? ""}`}
            type="number"
            step="any"
            min={-90}
            max={90}
            defaultValue={lat ?? ""}
            onBlur={(e) => setCoord("latitude", e.target.value)}
          />
        </label>
        <label>
          Longitude
          <input
            key={`lon-${lon ?? ""}`}
            type="number"
            step="any"
            min={-180}
            max={180}
            defaultValue={lon ?? ""}
            onBlur={(e) => setCoord("longitude", e.target.value)}
          />
        </label>
      </div>
      <p className="fm-muted fm-small">
        {value
          ? `${value.label || "Pinned"} · ${formatCoords(value.latitude, value.longitude)}`
          : "Search a place or click the map."}
      </p>
    </div>
  );
}
