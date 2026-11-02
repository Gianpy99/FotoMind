import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Supercluster, { type ClusterProperties, type PointFeature } from "supercluster";
import { Check, Film, MapPin, Tag, Undo2, X } from "lucide-react";
import type {
  Album,
  AssetSummary,
  FotoMindClient,
  MapPoint,
  MapPoints,
  TagPlaces,
  TagPlaceSuggestion,
} from "@fotomind/api-client";
import { AssetViewer } from "./AssetViewer";
import { L, MAX_ZOOM, createMap } from "./map";
import { errorMessage, plural } from "./format";

export interface MapFocus {
  latitude: number;
  longitude: number;
}

export interface MapViewProps {
  client: FotoMindClient;
  /** Global search text: the map shows matching items only. */
  query?: string;
  albums?: Album[];
  tagSuggestions?: string[];
  /** Centre on this position (e.g. "Show on map" from an item's details). */
  focus?: MapFocus | null;
  onCatalogChanged?(): void;
}

type PointProps = { point: MapPoint };
type Feature = PointFeature<PointProps>;

const MARKER_PX = 52;
const PANEL_LIMIT = 120;
const SOURCE_LABELS: Record<MapPoint["source"], string> = {
  file: "GPS",
  manual: "set by hand",
  tag: "from a tag",
};

function markerElement(thumbnail: string | null, count: number, video: boolean): HTMLElement {
  const root = document.createElement("div");
  root.className = "fm-map-marker";
  if (thumbnail) {
    const img = document.createElement("img");
    img.src = thumbnail;
    img.alt = "";
    img.loading = "lazy";
    root.append(img);
  } else {
    root.classList.add("fm-map-marker-empty");
  }
  if (count > 1) {
    const badge = document.createElement("span");
    badge.className = "fm-map-count";
    badge.textContent = count > 999 ? `${Math.round(count / 100) / 10}k` : String(count);
    root.append(badge);
  } else if (video) {
    root.classList.add("fm-map-marker-video");
  }
  return root;
}

function TagPlacesPanel({
  data,
  busy,
  onDecide,
}: {
  data: TagPlaces;
  busy: boolean;
  onDecide(
    tag: string,
    status: "confirmed" | "rejected" | "unset",
    suggestion?: TagPlaceSuggestion,
    index?: number,
  ): void;
}) {
  const [chosen, setChosen] = useState<Record<string, number>>({});
  const confirmed = data.decided.filter((d) => d.status === "confirmed");
  const rejected = data.decided.filter((d) => d.status === "rejected");
  return (
    <section className="fm-panel-section" aria-labelledby="fm-tag-places">
      <h3 id="fm-tag-places">Places in your tags</h3>
      {data.suggestions.length === 0 && confirmed.length === 0 && (
        <p className="fm-muted fm-small">
          Tag photos with a city or country (e.g. “Rome”) and confirm it here to put them on the
          map.
        </p>
      )}
      {data.suggestions.length > 0 && (
        <ul className="fm-place-list" aria-label="Suggested places">
          {data.suggestions.map((s) => {
            const index = chosen[s.tag] ?? 0;
            return (
              <li key={s.tag}>
                <div className="fm-place-row">
                  <Tag aria-hidden="true" />
                  <strong>{s.tag}</strong>
                  <span className="fm-muted fm-num">{s.count}</span>
                </div>
                {s.candidates.length > 1 ? (
                  <select
                    aria-label={`Place for ${s.tag}`}
                    value={index}
                    onChange={(e) => setChosen((c) => ({ ...c, [s.tag]: Number(e.target.value) }))}
                  >
                    {s.candidates.map((c, i) => (
                      <option key={`${c.label}-${i}`} value={i}>
                        {c.label}
                      </option>
                    ))}
                  </select>
                ) : (
                  <span className="fm-small">{s.candidates[0]?.label}</span>
                )}
                <div className="fm-place-actions">
                  <button
                    type="button"
                    className="fm-btn fm-btn-primary"
                    disabled={busy}
                    aria-label={`Confirm ${s.tag} as a place`}
                    onClick={() => onDecide(s.tag, "confirmed", s, index)}
                  >
                    <Check aria-hidden="true" />
                    It's this place
                  </button>
                  <button
                    type="button"
                    className="fm-btn fm-btn-ghost"
                    disabled={busy}
                    aria-label={`${s.tag} is not a place`}
                    onClick={() => onDecide(s.tag, "rejected")}
                  >
                    Not a place
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      )}
      {confirmed.length > 0 && (
        <ul className="fm-chips" aria-label="Confirmed places">
          {confirmed.map((d) => (
            <li key={d.tag} className="fm-chip" title={d.label ?? undefined}>
              <MapPin aria-hidden="true" />
              {d.tag}
              <button
                type="button"
                aria-label={`Forget place for ${d.tag}`}
                disabled={busy}
                onClick={() => onDecide(d.tag, "unset")}
              >
                <X aria-hidden="true" />
              </button>
            </li>
          ))}
        </ul>
      )}
      {rejected.length > 0 && (
        <p className="fm-muted fm-small">
          Not places: {rejected.map((d) => d.tag).join(", ")}{" "}
          <button
            type="button"
            className="fm-link"
            disabled={busy}
            onClick={() => rejected.forEach((d) => onDecide(d.tag, "unset"))}
          >
            <Undo2 aria-hidden="true" />
            Ask again
          </button>
        </p>
      )}
    </section>
  );
}

export function MapView({
  client,
  query = "",
  albums,
  tagSuggestions,
  focus = null,
  onCatalogChanged,
}: MapViewProps) {
  const [points, setPoints] = useState<MapPoints | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tagPlaces, setTagPlaces] = useState<TagPlaces | null>(null);
  const [deciding, setDeciding] = useState(false);
  const [reload, setReload] = useState(0);
  const [inView, setInView] = useState<MapPoint[]>([]);
  const [picked, setPicked] = useState<{ title: string; points: MapPoint[] } | null>(null);
  const [viewer, setViewer] = useState<{ list: MapPoint[]; index: number } | null>(null);
  const [openAsset, setOpenAsset] = useState<AssetSummary | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const fittedRef = useRef(false);

  useEffect(() => {
    let cancelled = false;
    client.mapAssets({ q: query.trim() || undefined }).then(
      (result) => {
        if (cancelled) return;
        setPoints(result);
        // A picked cluster refers to the old points (they may have moved or gone).
        setPicked(null);
        setError(null);
      },
      (err: unknown) => !cancelled && setError(errorMessage(err)),
    );
    return () => {
      cancelled = true;
    };
  }, [client, query, reload]);

  useEffect(() => {
    let cancelled = false;
    client.tagPlaces().then(
      (result) => !cancelled && setTagPlaces(result),
      () => undefined,
    );
    return () => {
      cancelled = true;
    };
  }, [client, reload]);

  useEffect(() => {
    const element = containerRef.current;
    if (!element) return;
    const map = createMap(element);
    map.setView([30, 10], 2);
    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  const index = useMemo(() => {
    const cluster = new Supercluster<PointProps>({ radius: 64, maxZoom: MAX_ZOOM - 1 });
    const features: Feature[] = (points?.items ?? []).map((point) => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: [point.longitude, point.latitude] },
      properties: { point },
    }));
    cluster.load(features);
    return cluster;
  }, [points]);

  const openList = useCallback((list: MapPoint[], at: number) => {
    setViewer({ list, index: at });
  }, []);

  // Markers: re-clustered for the visible area whenever the map moves or the data changes.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !points) return;
    const layer = L.layerGroup().addTo(map);

    function draw() {
      if (!map) return;
      layer.clearLayers();
      const bounds = map.getBounds();
      const wide = bounds.getEast() - bounds.getWest() >= 360;
      const bbox: [number, number, number, number] = wide
        ? [-180, -85, 180, 85]
        : [
            Math.max(-180, bounds.getWest()),
            Math.max(-85, bounds.getSouth()),
            Math.min(180, bounds.getEast()),
            Math.min(85, bounds.getNorth()),
          ];
      const visible: MapPoint[] = [];
      for (const feature of index.getClusters(bbox, Math.round(map.getZoom()))) {
        const [lon, lat] = feature.geometry.coordinates as [number, number];
        const props = feature.properties as Partial<ClusterProperties> & {
          point?: MapPoint;
        };
        if (props.cluster && props.cluster_id !== undefined) {
          const clusterId = props.cluster_id;
          const leaves = index.getLeaves(clusterId, PANEL_LIMIT).map((f) => f.properties.point);
          visible.push(...leaves);
          const cover = leaves[0];
          const icon = L.divIcon({
            className: "fm-map-icon",
            html: markerElement(
              cover?.thumbnail_url ? client.url(cover.thumbnail_url) : null,
              props.point_count ?? leaves.length,
              false,
            ),
            iconSize: [MARKER_PX, MARKER_PX],
          });
          L.marker([lat, lon], { icon, title: plural(props.point_count ?? 0, "item") })
            .on("click", () => {
              setPicked({
                title: plural(props.point_count ?? leaves.length, "item"),
                points: leaves,
              });
              const zoom = index.getClusterExpansionZoom(clusterId);
              if (zoom <= MAX_ZOOM - 1) map.flyTo([lat, lon], zoom, { duration: 0.4 });
            })
            .addTo(layer);
        } else if (props.point) {
          const point = props.point;
          visible.push(point);
          const icon = L.divIcon({
            className: "fm-map-icon",
            html: markerElement(
              point.thumbnail_url ? client.url(point.thumbnail_url) : null,
              1,
              point.asset_type === "video",
            ),
            iconSize: [MARKER_PX, MARKER_PX],
          });
          L.marker([lat, lon], { icon, title: point.display_name })
            .on("click", () => openList([point], 0))
            .addTo(layer);
        }
      }
      visible.sort((a, b) => b.sort_at.localeCompare(a.sort_at));
      setInView(visible.slice(0, PANEL_LIMIT));
    }

    map.on("moveend", draw);
    if (!fittedRef.current && points.items.length > 0 && !focus) {
      fittedRef.current = true;
      const bounds = L.latLngBounds(points.items.map((p) => [p.latitude, p.longitude]));
      // Pad by a marker's size so thumbnails at the edge are not cut off.
      map.fitBounds(bounds, { padding: [48, 48], maxZoom: 12, animate: false });
    }
    map.fire("moveend");
    return () => {
      map.off("moveend", draw);
      layer.remove();
    };
  }, [client, index, points, focus, openList]);

  useEffect(() => {
    if (focus) mapRef.current?.setView([focus.latitude, focus.longitude], 14);
  }, [focus]);

  // Load the full item for the viewer (map points carry only what markers need).
  const viewerPoint = viewer ? viewer.list[viewer.index] : undefined;
  useEffect(() => {
    if (!viewerPoint) return;
    let cancelled = false;
    client.getAsset(viewerPoint.id).then(
      (asset) => !cancelled && setOpenAsset(asset),
      () => !cancelled && setViewer(null),
    );
    return () => {
      cancelled = true;
    };
  }, [client, viewerPoint]);

  function decide(
    tag: string,
    status: "confirmed" | "rejected" | "unset",
    suggestion?: TagPlaceSuggestion,
    at = 0,
  ) {
    const place = suggestion?.candidates[at];
    setDeciding(true);
    client
      .decideTagPlace({
        tag,
        status,
        place: place
          ? {
              latitude: place.latitude,
              longitude: place.longitude,
              label: place.label,
              kind: place.kind,
            }
          : null,
      })
      .then(
        (result) => {
          setTagPlaces(result);
          setDeciding(false);
          setReload((n) => n + 1);
          onCatalogChanged?.();
        },
        (err: unknown) => {
          setDeciding(false);
          setError(errorMessage(err));
        },
      );
  }

  const panelPoints = picked?.points ?? inView;
  const total = points?.items.length ?? 0;
  const shownAsset = openAsset && viewerPoint && openAsset.id === viewerPoint.id ? openAsset : null;

  return (
    <section className="fm-map-page" aria-label="Map">
      <div className="fm-map-main">
        <div className="fm-libbar">
          <div className="fm-libbar-title">
            <h2>Map</h2>
            <span className="fm-muted fm-num">
              {points === null
                ? "Loading…"
                : `${plural(total, "item")} with a location${points.truncated ? " (newest shown)" : ""}`}
            </span>
          </div>
        </div>
        {error && (
          <p role="alert" className="fm-error">
            {error}
          </p>
        )}
        <div className="fm-map-frame">
          <div ref={containerRef} className="fm-map" role="application" aria-label="Photo map" />
          {points !== null && total === 0 && (
            <div className="fm-map-empty">
              <MapPin aria-hidden="true" />
              <p>
                {query.trim()
                  ? "Nothing matching the search has a location."
                  : "No located photos yet. Photos with GPS appear here after a scan; you can also confirm place tags or set a location with “Edit info”."}
              </p>
            </div>
          )}
        </div>
      </div>

      <aside className="fm-inspector fm-map-panel" aria-label="Map details">
        <div className="fm-inspector-body">
          <section className="fm-panel-section fm-panel-first" aria-labelledby="fm-map-here">
            <div className="fm-panel-head">
              <h3 id="fm-map-here">{picked ? picked.title : "In this area"}</h3>
              {picked && (
                <button type="button" className="fm-link" onClick={() => setPicked(null)}>
                  Show all in view
                </button>
              )}
            </div>
            {panelPoints.length === 0 ? (
              <p className="fm-muted fm-small">Nothing in this part of the map.</p>
            ) : (
              <ul className="fm-map-strip" aria-label="Items here">
                {panelPoints.map((point, i) => (
                  <li key={point.id}>
                    <button
                      type="button"
                      title={`${point.display_name} · location ${SOURCE_LABELS[point.source]}`}
                      onClick={() => openList(panelPoints, i)}
                    >
                      {point.thumbnail_url ? (
                        <img
                          src={client.url(point.thumbnail_url)}
                          alt={point.display_name}
                          loading="lazy"
                        />
                      ) : (
                        <span className="fm-tile-placeholder">{point.display_name}</span>
                      )}
                      {point.asset_type === "video" && <Film aria-hidden="true" />}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>
          {tagPlaces && <TagPlacesPanel data={tagPlaces} busy={deciding} onDecide={decide} />}
        </div>
      </aside>

      {viewer && shownAsset && (
        <AssetViewer
          client={client}
          asset={shownAsset}
          hasPrev={viewer.index > 0}
          hasNext={viewer.index < viewer.list.length - 1}
          onPrev={() => setViewer((v) => (v ? { ...v, index: Math.max(0, v.index - 1) } : v))}
          onNext={() =>
            setViewer((v) => (v ? { ...v, index: Math.min(v.list.length - 1, v.index + 1) } : v))
          }
          onClose={() => {
            setViewer(null);
            setOpenAsset(null);
          }}
          albums={albums}
          tagSuggestions={tagSuggestions}
          onChanged={(asset) => {
            setOpenAsset(asset);
            // The location may have changed: refresh the markers.
            setReload((n) => n + 1);
            onCatalogChanged?.();
          }}
        />
      )}
    </section>
  );
}
