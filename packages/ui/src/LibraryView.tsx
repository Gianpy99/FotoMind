import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";
import {
  ChevronDown,
  ChevronRight,
  CloudOff,
  Film,
  Filter,
  Grid2x2,
  Grid3x3,
  Image as ImageIcon,
  Maximize2,
  MousePointerClick,
  Play,
  X,
} from "lucide-react";
import type {
  Album,
  AssetSummary,
  AssetType,
  FotoMindClient,
  LibraryFacets,
  ListAssetsParams,
} from "@fotomind/api-client";
import { AssetInspector, isTyping } from "./AssetInspector";
import { AssetViewer } from "./AssetViewer";
import { StarDisplay, StarRating } from "./StarRating";
import {
  errorMessage,
  fileFormat,
  formatDuration,
  isRawFormat,
  monthKey,
  monthLabel,
  yearRange,
} from "./format";

const PAGE_SIZE = 100;
const TILE_SIZE_KEY = "fotomind.tileSize";
const TILE_SIZES = { min: 110, max: 280, default: 170 };

interface Filters {
  minRating: number;
  tag: string;
  camera: string;
  year: string;
  sort: "newest" | "oldest";
}

const NO_FILTERS: Filters = { minRating: 0, tag: "", camera: "", year: "", sort: "newest" };

interface LibraryState {
  items: AssetSummary[];
  total: number;
  cursor: string | null;
  loading: boolean;
  error: string | null;
}

const EMPTY: LibraryState = { items: [], total: 0, cursor: null, loading: true, error: null };

export interface LibraryViewProps {
  client: FotoMindClient;
  /** Heading shown in the toolbar. */
  heading?: ReactNode;
  /** Restrict the grid to one album (album detail page). */
  albumId?: string;
  /** Restrict the grid to photos or videos. */
  assetType?: AssetType | "all";
  /** Global search text (debounced by the shell). */
  query?: string;
  facets?: LibraryFacets | null;
  albums?: Album[];
  /** Clear the global search too ("Clear filters"). */
  onClearSearch?(): void;
  /** Ratings, tags or album membership changed. */
  onCatalogChanged?(): void;
}

function storedTileSize(): number {
  try {
    const value = Number(localStorage.getItem(TILE_SIZE_KEY));
    return value >= TILE_SIZES.min && value <= TILE_SIZES.max ? value : TILE_SIZES.default;
  } catch {
    return TILE_SIZES.default;
  }
}

interface Group {
  key: string;
  label: string;
  items: { asset: AssetSummary; index: number }[];
}

function groupByMonth(items: AssetSummary[]): Group[] {
  const groups: Group[] = [];
  items.forEach((asset, index) => {
    const key = monthKey(asset.sort_at);
    let group = groups[groups.length - 1];
    if (!group || group.key !== key) {
      group = { key, label: monthLabel(asset.sort_at), items: [] };
      groups.push(group);
    }
    group.items.push({ asset, index });
  });
  return groups;
}

export function LibraryView({
  client,
  heading,
  albumId,
  assetType = "all",
  query = "",
  facets = null,
  albums = [],
  onClearSearch,
  onCatalogChanged,
}: LibraryViewProps) {
  const [filters, setFilters] = useState<Filters>(NO_FILTERS);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [state, setState] = useState<LibraryState>(EMPTY);
  const [reload, setReload] = useState(0);
  const [currentId, setCurrentId] = useState<string | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);
  const [selected, setSelected] = useState<ReadonlySet<string>>(new Set());
  const [collapsed, setCollapsed] = useState<ReadonlySet<string>>(new Set());
  const [tileSize, setTileSize] = useState(storedTileSize);
  const [bulkTag, setBulkTag] = useState("");
  const [bulkAlbum, setBulkAlbum] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const fetchPage = useCallback(
    (cursor: string | null) => {
      const params: ListAssetsParams = {
        limit: PAGE_SIZE,
        cursor,
        q: query.trim() || undefined,
        asset_type: assetType === "all" ? undefined : assetType,
        min_rating: filters.minRating || undefined,
        tag: filters.tag ? [filters.tag] : undefined,
        camera: filters.camera || undefined,
        ...(filters.year ? yearRange(filters.year) : {}),
        sort: filters.sort,
        album_id: albumId,
      };
      return client.listAssets(params);
    },
    [client, filters, albumId, assetType, query],
  );

  useEffect(() => {
    let cancelled = false;
    fetchPage(null)
      .then((page) => {
        if (!cancelled) {
          setState({
            items: page.items,
            total: page.total,
            cursor: page.next_cursor,
            loading: false,
            error: null,
          });
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) setState({ ...EMPTY, loading: false, error: errorMessage(err) });
      });
    return () => {
      cancelled = true;
    };
  }, [fetchPage, reload]);

  const items = state.items;
  const indexOf = useCallback((id: string | null) => items.findIndex((a) => a.id === id), [items]);
  const current = items.find((a) => a.id === currentId) ?? null;
  const openIndex = indexOf(openId);
  const openAsset = openIndex >= 0 ? items[openIndex] : undefined;
  const prevAsset = openIndex > 0 ? items[openIndex - 1] : undefined;
  const nextAsset = openIndex >= 0 ? items[openIndex + 1] : undefined;
  const selecting = selected.size > 0;

  // Grid keyboard: ←/→ move the inspected item, Esc clears the selection.
  useEffect(() => {
    if (openId !== null) return;
    function onKey(event: KeyboardEvent) {
      if (isTyping(event.target) || event.ctrlKey || event.metaKey || event.altKey) return;
      if (event.key === "Escape" && selected.size > 0) {
        setSelected(new Set());
      } else if (event.key === "ArrowRight" || event.key === "ArrowLeft") {
        if (items.length === 0) return;
        const i = indexOf(currentId);
        const next =
          i < 0
            ? 0
            : Math.min(items.length - 1, Math.max(0, i + (event.key === "ArrowRight" ? 1 : -1)));
        setCurrentId(items[next]?.id ?? null);
        event.preventDefault();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [openId, items, currentId, indexOf, selected.size]);

  function applyFilters(next: Partial<Filters>) {
    setFilters((f) => ({ ...f, ...next }));
    setState(EMPTY);
    setCurrentId(null);
    setSelected(new Set());
  }

  function clearFilters() {
    onClearSearch?.();
    applyFilters(NO_FILTERS);
  }

  function changeTileSize(size: number) {
    setTileSize(size);
    try {
      localStorage.setItem(TILE_SIZE_KEY, String(size));
    } catch {
      // Not persisted; fine.
    }
  }

  function loadMore() {
    if (!state.cursor) return;
    setState((s) => ({ ...s, loading: true }));
    fetchPage(state.cursor)
      .then((page) =>
        setState((s) => ({
          items: [...s.items, ...page.items],
          total: page.total,
          cursor: page.next_cursor,
          loading: false,
          error: null,
        })),
      )
      .catch((err: unknown) =>
        setState((s) => ({ ...s, loading: false, error: errorMessage(err) })),
      );
  }

  function toggle(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function clickTile(id: string) {
    if (selecting) toggle(id);
    else if (currentId === id) setOpenId(id);
    else setCurrentId(id);
  }

  function toggleGroup(key: string) {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  async function bulk(action: () => Promise<string>) {
    setBusy(true);
    setNotice(null);
    try {
      setNotice(await action());
      setReload((n) => n + 1);
      onCatalogChanged?.();
    } catch (err) {
      setNotice(`Failed: ${errorMessage(err)}`);
    } finally {
      setBusy(false);
    }
  }

  const ids = [...selected];

  function rateSelection(rating: number) {
    void bulk(async () => {
      const { updated } = await client.bulkUpdateAssets({ asset_ids: ids, rating });
      return rating ? `Rated ${updated} item(s) ${rating}★` : `Cleared ${updated} rating(s)`;
    });
  }

  function tagSelection(mode: "add" | "remove") {
    const tag = bulkTag.trim();
    if (!tag) return;
    void bulk(async () => {
      const body =
        mode === "add"
          ? { asset_ids: ids, add_tags: [tag] }
          : { asset_ids: ids, remove_tags: [tag] };
      const { updated } = await client.bulkUpdateAssets(body);
      setBulkTag("");
      return `${mode === "add" ? "Tagged" : "Untagged"} ${updated} item(s) “${tag}”`;
    });
  }

  function addSelectionToAlbum() {
    const name = bulkAlbum.trim();
    if (!name) return;
    void bulk(async () => {
      const existing = albums.find((a) => a.name.toLowerCase() === name.toLowerCase());
      const album = existing
        ? await client.addToAlbum(existing.id, ids)
        : await client.createAlbum({ name, asset_ids: ids });
      setBulkAlbum("");
      return `${existing ? "Added to" : "Created"} album “${album.name}” (${album.asset_count} items)`;
    });
  }

  function removeSelectionFromAlbum() {
    if (!albumId) return;
    void bulk(async () => {
      const album = await client.removeFromAlbum(albumId, ids);
      setSelected(new Set());
      return `Removed from “${album.name}”`;
    });
  }

  function assetChanged(updated: AssetSummary) {
    setState((s) => ({
      ...s,
      items: s.items.map((a) =>
        a.id === updated.id ? { ...a, rating: updated.rating, tags: updated.tags } : a,
      ),
    }));
    onCatalogChanged?.();
  }

  const groups = useMemo(() => groupByMonth(items), [items]);
  const activeFilters = (filters.tag ? 1 : 0) + (filters.camera ? 1 : 0) + (filters.year ? 1 : 0);
  const filtered = query.trim() !== "" || filters.minRating > 0 || activeFilters > 0;
  const tagNames = facets?.tags.map((t) => t.value) ?? [];
  const showFilterRow = filtersOpen || activeFilters > 0;

  return (
    <section
      aria-label={albumId ? "Album" : "Library"}
      className="fm-library"
      style={{ "--fm-tile-min": `${tileSize}px` } as CSSProperties}
    >
      <div className="fm-workarea">
        <div className="fm-libbar">
          <div className="fm-libbar-title">
            {heading ?? <h2>Library</h2>}
            <span className="fm-muted fm-num">
              {state.loading ? "Loading…" : `${state.total} items`}
            </span>
          </div>
          <div className="fm-libbar-tools">
            <select
              aria-label="Sort"
              value={filters.sort}
              onChange={(e) => applyFilters({ sort: e.target.value as Filters["sort"] })}
            >
              <option value="newest">Date taken (newest)</option>
              <option value="oldest">Date taken (oldest)</option>
            </select>
            <button
              type="button"
              className={showFilterRow ? "fm-btn fm-btn-active" : "fm-btn"}
              aria-expanded={showFilterRow}
              aria-controls="fm-filter-row"
              onClick={() => setFiltersOpen((o) => !o)}
            >
              <Filter aria-hidden="true" />
              Filter
              {activeFilters > 0 && (
                <span className="fm-pill fm-pill-accent fm-num">{activeFilters}</span>
              )}
            </button>
            <span className="fm-rating-filter">
              <StarRating
                size="sm"
                label="Minimum rating"
                itemLabel={(n) => `At least ${n} star${n > 1 ? "s" : ""}`}
                value={filters.minRating}
                onChange={(n) => applyFilters({ minRating: n })}
              />
            </span>
            {filtered && (
              <button type="button" className="fm-btn fm-btn-ghost" onClick={clearFilters}>
                <X aria-hidden="true" />
                Clear filters
              </button>
            )}
            <label className="fm-density" title="Thumbnail size">
              <Grid3x3 aria-hidden="true" />
              <input
                type="range"
                aria-label="Thumbnail size"
                min={TILE_SIZES.min}
                max={TILE_SIZES.max}
                step={10}
                value={tileSize}
                onChange={(e) => changeTileSize(Number(e.target.value))}
              />
              <Grid2x2 aria-hidden="true" />
            </label>
          </div>
        </div>

        {showFilterRow && (
          <div className="fm-filter-row" id="fm-filter-row" role="group" aria-label="Filters">
            <select
              aria-label="Tag"
              value={filters.tag}
              onChange={(e) => applyFilters({ tag: e.target.value })}
            >
              <option value="">Any tag</option>
              {facets?.tags.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.value} ({t.count})
                </option>
              ))}
            </select>
            <select
              aria-label="Camera"
              value={filters.camera}
              onChange={(e) => applyFilters({ camera: e.target.value })}
            >
              <option value="">Any camera</option>
              {facets?.cameras.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.value} ({c.count})
                </option>
              ))}
            </select>
            <select
              aria-label="Year"
              value={filters.year}
              onChange={(e) => applyFilters({ year: e.target.value })}
            >
              <option value="">Any year</option>
              {facets?.years.map((y) => (
                <option key={y.value} value={y.value}>
                  {y.value} ({y.count})
                </option>
              ))}
            </select>
          </div>
        )}

        {selecting && (
          <div className="fm-bulkbar" role="toolbar" aria-label="Selection">
            <strong className="fm-num">{selected.size} selected</strong>
            <select
              aria-label="Rate selection"
              value=""
              disabled={busy}
              onChange={(e) => e.target.value !== "" && rateSelection(Number(e.target.value))}
            >
              <option value="">Rate…</option>
              {[1, 2, 3, 4, 5].map((n) => (
                <option key={n} value={n}>
                  {"★".repeat(n)}
                </option>
              ))}
              <option value={0}>Clear rating</option>
            </select>
            <span className="fm-inline-form">
              <input
                aria-label="Tag for selection"
                placeholder="Tag"
                list="fm-bulk-tags"
                maxLength={100}
                value={bulkTag}
                onChange={(e) => setBulkTag(e.target.value)}
              />
              <datalist id="fm-bulk-tags">
                {tagNames.map((t) => (
                  <option key={t} value={t} />
                ))}
              </datalist>
              <button
                type="button"
                className="fm-btn"
                disabled={busy || !bulkTag.trim()}
                onClick={() => tagSelection("add")}
              >
                Add tag
              </button>
              <button
                type="button"
                className="fm-btn"
                disabled={busy || !bulkTag.trim()}
                onClick={() => tagSelection("remove")}
              >
                Remove tag
              </button>
            </span>
            <span className="fm-inline-form">
              <input
                aria-label="Album for selection"
                placeholder="Album (new or existing)"
                list="fm-bulk-albums"
                maxLength={200}
                value={bulkAlbum}
                onChange={(e) => setBulkAlbum(e.target.value)}
              />
              <datalist id="fm-bulk-albums">
                {albums.map((a) => (
                  <option key={a.id} value={a.name} />
                ))}
              </datalist>
              <button
                type="button"
                className="fm-btn fm-btn-primary"
                disabled={busy || !bulkAlbum.trim()}
                onClick={addSelectionToAlbum}
              >
                Add to album
              </button>
            </span>
            {albumId && (
              <button
                type="button"
                className="fm-btn"
                disabled={busy}
                onClick={removeSelectionFromAlbum}
              >
                Remove from album
              </button>
            )}
            <span className="fm-bulkbar-end">
              <button
                type="button"
                className="fm-btn fm-btn-ghost"
                onClick={() => setSelected(new Set(items.map((a) => a.id)))}
              >
                Select all loaded
              </button>
              <button
                type="button"
                className="fm-btn fm-btn-ghost"
                onClick={() => setSelected(new Set())}
              >
                Clear selection
              </button>
            </span>
          </div>
        )}
        {notice && (
          <p className="fm-notice" role="status">
            {notice}
          </p>
        )}

        {state.error && (
          <p role="alert" className="fm-error">
            Could not load the library: {state.error}
          </p>
        )}

        {!state.loading && !state.error && items.length === 0 && (
          <div className="fm-empty">
            {filtered ? (
              "Nothing matches these filters."
            ) : albumId ? (
              "This album is empty. Select photos in the Library and use “Add to album”."
            ) : (
              <>
                Nothing catalogued yet. Add a folder on your PC with{" "}
                <code>fotomind-worker roots add &lt;folder&gt;</code>, then press <em>Scan now</em>{" "}
                in Sources.
              </>
            )}
          </div>
        )}

        {groups.map((group) => {
          const isCollapsed = collapsed.has(group.key);
          return (
            <div key={group.key} className="fm-group">
              <h3 className="fm-group-head">
                <button
                  type="button"
                  aria-expanded={!isCollapsed}
                  onClick={() => toggleGroup(group.key)}
                >
                  {isCollapsed ? (
                    <ChevronRight aria-hidden="true" />
                  ) : (
                    <ChevronDown aria-hidden="true" />
                  )}
                  {group.label}
                </button>
                <span className="fm-muted fm-num" aria-hidden="true">
                  {group.items.length}
                </span>
              </h3>
              {!isCollapsed && (
                <ul className={selecting ? "fm-grid fm-selecting" : "fm-grid"}>
                  {group.items.map(({ asset }) => {
                    const isSelected = selected.has(asset.id);
                    const format = fileFormat(asset.display_name);
                    const classes = ["fm-tile-wrap"];
                    if (isSelected) classes.push("fm-selected");
                    if (asset.id === currentId) classes.push("fm-current");
                    return (
                      <li key={asset.id} className={classes.join(" ")}>
                        <button
                          type="button"
                          className="fm-tile"
                          onClick={() => clickTile(asset.id)}
                          onDoubleClick={() => !selecting && setOpenId(asset.id)}
                          title={asset.display_name}
                        >
                          {asset.thumbnail_url ? (
                            <img
                              src={client.url(asset.thumbnail_url)}
                              alt={asset.display_name}
                              loading="lazy"
                            />
                          ) : (
                            <span className="fm-tile-placeholder">{asset.display_name}</span>
                          )}
                          <span className="fm-tile-corner" aria-hidden="true">
                            {asset.asset_type === "video" ? <Film /> : <ImageIcon />}
                            {isRawFormat(format) && <span>RAW</span>}
                          </span>
                          {asset.asset_type === "video" && (
                            <span className="fm-tile-duration fm-num">
                              <Play aria-hidden="true" />
                              {formatDuration(asset.duration_s)}
                            </span>
                          )}
                          {asset.availability !== "online" && (
                            <span className="fm-tile-warn">
                              <CloudOff aria-hidden="true" />
                              {asset.availability}
                            </span>
                          )}
                        </button>
                        <input
                          type="checkbox"
                          className="fm-select"
                          aria-label={`Select ${asset.display_name}`}
                          checked={isSelected}
                          onChange={() => toggle(asset.id)}
                        />
                        <div className="fm-tile-meta">
                          {asset.rating > 0 && <StarDisplay value={asset.rating} />}
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          );
        })}

        {state.cursor && (
          <div className="fm-more">
            <button type="button" className="fm-btn" onClick={loadMore} disabled={state.loading}>
              {state.loading ? "Loading…" : "Load more"}
            </button>
          </div>
        )}
      </div>

      <aside className="fm-inspector" aria-label="Details">
        {current && openId === null ? (
          <AssetInspector
            client={client}
            asset={current}
            albums={albums}
            tagSuggestions={tagNames}
            onChanged={assetChanged}
            hotkeys
            preview
            actions={
              <>
                <button
                  type="button"
                  className="fm-icon-btn"
                  aria-label="Open viewer"
                  title="Open viewer (or click the photo again)"
                  onClick={() => setOpenId(current.id)}
                >
                  <Maximize2 aria-hidden="true" />
                </button>
                <button
                  type="button"
                  className="fm-icon-btn"
                  aria-label="Close details"
                  title="Close details"
                  onClick={() => setCurrentId(null)}
                >
                  <X aria-hidden="true" />
                </button>
              </>
            }
          />
        ) : (
          <div className="fm-inspector-empty">
            <MousePointerClick aria-hidden="true" />
            <p>Select a photo or video to see its details, rating and tags.</p>
            <p className="fm-small">
              Click again or double-click to open it large. Keys <kbd>←</kbd> <kbd>→</kbd> move,{" "}
              <kbd>0</kbd>–<kbd>5</kbd> rate.
            </p>
          </div>
        )}
      </aside>

      {openAsset && (
        <AssetViewer
          client={client}
          asset={openAsset}
          hasPrev={prevAsset !== undefined}
          hasNext={nextAsset !== undefined}
          onPrev={() => prevAsset && setOpenId(prevAsset.id)}
          onNext={() => nextAsset && setOpenId(nextAsset.id)}
          onClose={() => {
            setCurrentId(openId);
            setOpenId(null);
          }}
          albums={albums}
          tagSuggestions={tagNames}
          onChanged={assetChanged}
        />
      )}
    </section>
  );
}
