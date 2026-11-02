import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import type {
  Album,
  AssetSummary,
  AssetType,
  FotoMindClient,
  LibraryFacets,
  ListAssetsParams,
} from "@fotomind/api-client";
import { AssetViewer } from "./AssetViewer";
import { errorMessage, formatDuration, yearRange } from "./format";

const PAGE_SIZE = 100;
const SEARCH_DEBOUNCE_MS = 300;

interface Filters {
  q: string;
  type: AssetType | "all";
  minRating: number;
  tag: string;
  camera: string;
  year: string;
  sort: "newest" | "oldest";
}

const NO_FILTERS: Filters = {
  q: "",
  type: "all",
  minRating: 0,
  tag: "",
  camera: "",
  year: "",
  sort: "newest",
};

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
  /** Restrict the grid to one album (album detail page). */
  albumId?: string;
  /** Replaces the default "Library" heading. */
  heading?: ReactNode;
  /** Album membership changed (assets added or removed from albums). */
  onAlbumsChanged?(): void;
}

function toParams(filters: Filters, albumId: string | undefined): ListAssetsParams {
  return {
    q: filters.q.trim() || undefined,
    asset_type: filters.type === "all" ? undefined : filters.type,
    min_rating: filters.minRating || undefined,
    tag: filters.tag ? [filters.tag] : undefined,
    camera: filters.camera || undefined,
    ...(filters.year ? yearRange(filters.year) : {}),
    sort: filters.sort,
    album_id: albumId,
  };
}

export function LibraryView({ client, albumId, heading, onAlbumsChanged }: LibraryViewProps) {
  const [filters, setFilters] = useState<Filters>(NO_FILTERS);
  const [searchText, setSearchText] = useState("");
  const [state, setState] = useState<LibraryState>(EMPTY);
  const [reload, setReload] = useState(0);
  const [openIndex, setOpenIndex] = useState<number | null>(null);
  const [selected, setSelected] = useState<ReadonlySet<string>>(new Set());
  const [facets, setFacets] = useState<LibraryFacets | null>(null);
  const [facetsVersion, setFacetsVersion] = useState(0);
  const [albums, setAlbums] = useState<Album[]>([]);
  const [albumsVersion, setAlbumsVersion] = useState(0);
  const [bulkTag, setBulkTag] = useState("");
  const [bulkAlbum, setBulkAlbum] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const searchTimer = useRef<number | undefined>(undefined);

  const fetchPage = useCallback(
    (cursor: string | null) =>
      client.listAssets({ limit: PAGE_SIZE, cursor, ...toParams(filters, albumId) }),
    [client, filters, albumId],
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

  useEffect(() => {
    let cancelled = false;
    client
      .facets()
      .then((f) => !cancelled && setFacets(f))
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [client, facetsVersion]);

  useEffect(() => {
    let cancelled = false;
    client
      .listAlbums()
      .then((a) => !cancelled && setAlbums(a))
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [client, albumsVersion]);

  useEffect(() => () => window.clearTimeout(searchTimer.current), []);

  function applyFilters(next: Partial<Filters>) {
    setFilters((f) => ({ ...f, ...next }));
    setState(EMPTY);
    setOpenIndex(null);
    setSelected(new Set());
  }

  function changeSearch(text: string) {
    setSearchText(text);
    window.clearTimeout(searchTimer.current);
    searchTimer.current = window.setTimeout(() => applyFilters({ q: text }), SEARCH_DEBOUNCE_MS);
  }

  function clearFilters() {
    window.clearTimeout(searchTimer.current);
    setSearchText("");
    applyFilters(NO_FILTERS);
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

  async function bulk(action: () => Promise<string>, after: { albums?: boolean } = {}) {
    setBusy(true);
    setNotice(null);
    try {
      setNotice(await action());
      setReload((n) => n + 1);
      setFacetsVersion((n) => n + 1);
      if (after.albums) {
        setAlbumsVersion((n) => n + 1);
        onAlbumsChanged?.();
      }
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
    void bulk(
      async () => {
        const existing = albums.find((a) => a.name.toLowerCase() === name.toLowerCase());
        const album = existing
          ? await client.addToAlbum(existing.id, ids)
          : await client.createAlbum({ name, asset_ids: ids });
        setBulkAlbum("");
        return `${existing ? "Added to" : "Created"} album “${album.name}” (${album.asset_count} items)`;
      },
      { albums: true },
    );
  }

  function removeSelectionFromAlbum() {
    if (!albumId) return;
    void bulk(
      async () => {
        const album = await client.removeFromAlbum(albumId, ids);
        setSelected(new Set());
        return `Removed from “${album.name}”`;
      },
      { albums: true },
    );
  }

  function assetChanged(updated: AssetSummary) {
    setState((s) => ({
      ...s,
      items: s.items.map((a) =>
        a.id === updated.id ? { ...a, rating: updated.rating, tags: updated.tags } : a,
      ),
    }));
    setFacetsVersion((n) => n + 1);
  }

  const filtered =
    searchText !== "" ||
    filters.type !== "all" ||
    filters.minRating > 0 ||
    filters.tag !== "" ||
    filters.camera !== "" ||
    filters.year !== "";
  const tagNames = facets?.tags.map((t) => t.value) ?? [];

  return (
    <section aria-label={albumId ? "Album" : "Library"} className="fm-library">
      <div className="fm-toolbar">
        {heading ?? <h2>Library</h2>}
        <span className="fm-muted">{state.loading ? "Loading…" : `${state.total} items`}</span>
      </div>

      <div className="fm-filters" role="search">
        <input
          type="search"
          aria-label="Search"
          placeholder="Search names, folders, cameras, tags…"
          value={searchText}
          onChange={(e) => changeSearch(e.target.value)}
        />
        <select
          aria-label="Type"
          value={filters.type}
          onChange={(e) => applyFilters({ type: e.target.value as Filters["type"] })}
        >
          <option value="all">Photos &amp; videos</option>
          <option value="photo">Photos</option>
          <option value="video">Videos</option>
        </select>
        <select
          aria-label="Minimum rating"
          value={filters.minRating}
          onChange={(e) => applyFilters({ minRating: Number(e.target.value) })}
        >
          <option value={0}>Any rating</option>
          {[1, 2, 3, 4, 5].map((n) => (
            <option key={n} value={n}>
              {"★".repeat(n)}
              {n < 5 ? " or more" : ""}
            </option>
          ))}
        </select>
        {facets && facets.tags.length > 0 && (
          <select
            aria-label="Tag"
            value={filters.tag}
            onChange={(e) => applyFilters({ tag: e.target.value })}
          >
            <option value="">Any tag</option>
            {facets.tags.map((t) => (
              <option key={t.value} value={t.value}>
                {t.value} ({t.count})
              </option>
            ))}
          </select>
        )}
        {facets && facets.cameras.length > 0 && (
          <select
            aria-label="Camera"
            value={filters.camera}
            onChange={(e) => applyFilters({ camera: e.target.value })}
          >
            <option value="">Any camera</option>
            {facets.cameras.map((c) => (
              <option key={c.value} value={c.value}>
                {c.value} ({c.count})
              </option>
            ))}
          </select>
        )}
        {facets && facets.years.length > 0 && (
          <select
            aria-label="Year"
            value={filters.year}
            onChange={(e) => applyFilters({ year: e.target.value })}
          >
            <option value="">Any year</option>
            {facets.years.map((y) => (
              <option key={y.value} value={y.value}>
                {y.value} ({y.count})
              </option>
            ))}
          </select>
        )}
        <select
          aria-label="Sort"
          value={filters.sort}
          onChange={(e) => applyFilters({ sort: e.target.value as Filters["sort"] })}
        >
          <option value="newest">Newest first</option>
          <option value="oldest">Oldest first</option>
        </select>
        {filtered && (
          <button type="button" onClick={clearFilters}>
            Clear filters
          </button>
        )}
      </div>

      {selected.size > 0 && (
        <div className="fm-bulkbar" role="toolbar" aria-label="Selection">
          <strong>{selected.size} selected</strong>
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
          <span className="fm-bulk-group">
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
              disabled={busy || !bulkTag.trim()}
              onClick={() => tagSelection("add")}
            >
              Add tag
            </button>
            <button
              type="button"
              disabled={busy || !bulkTag.trim()}
              onClick={() => tagSelection("remove")}
            >
              Remove tag
            </button>
          </span>
          <span className="fm-bulk-group">
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
              disabled={busy || !bulkAlbum.trim()}
              onClick={addSelectionToAlbum}
            >
              Add to album
            </button>
          </span>
          {albumId && (
            <button type="button" disabled={busy} onClick={removeSelectionFromAlbum}>
              Remove from album
            </button>
          )}
          <button type="button" onClick={() => setSelected(new Set(state.items.map((a) => a.id)))}>
            Select all loaded
          </button>
          <button type="button" onClick={() => setSelected(new Set())}>
            Clear selection
          </button>
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

      {!state.loading && !state.error && state.items.length === 0 && (
        <p className="fm-empty">
          {filtered ? (
            "Nothing matches these filters."
          ) : albumId ? (
            "This album is empty. Select photos in the Library and use “Add to album”."
          ) : (
            <>
              Nothing catalogued yet. Add a folder on your PC with{" "}
              <code>fotomind-worker roots add &lt;folder&gt;</code>, then press <em>Scan now</em> in
              Sources.
            </>
          )}
        </p>
      )}

      <ul className={selected.size > 0 ? "fm-grid fm-selecting" : "fm-grid"}>
        {state.items.map((asset, index) => {
          const isSelected = selected.has(asset.id);
          return (
            <li key={asset.id} className={isSelected ? "fm-tile-wrap fm-selected" : "fm-tile-wrap"}>
              <button
                type="button"
                className="fm-tile"
                onClick={() => (selected.size > 0 ? toggle(asset.id) : setOpenIndex(index))}
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
                {asset.asset_type === "video" && (
                  <span className="fm-badge">▶ {formatDuration(asset.duration_s)}</span>
                )}
                {asset.availability !== "online" && (
                  <span className="fm-badge fm-badge-warn">{asset.availability}</span>
                )}
                {asset.rating > 0 && (
                  <span className="fm-badge fm-badge-rating" aria-label={`${asset.rating} stars`}>
                    {"★".repeat(asset.rating)}
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
            </li>
          );
        })}
      </ul>

      {state.cursor && (
        <div className="fm-more">
          <button type="button" onClick={loadMore} disabled={state.loading}>
            {state.loading ? "Loading…" : "Load more"}
          </button>
        </div>
      )}

      {openIndex !== null && state.items[openIndex] && (
        <AssetViewer
          client={client}
          asset={state.items[openIndex]}
          hasPrev={openIndex > 0}
          hasNext={openIndex < state.items.length - 1}
          onPrev={() => setOpenIndex((i) => (i !== null && i > 0 ? i - 1 : i))}
          onNext={() => setOpenIndex((i) => (i !== null && i < state.items.length - 1 ? i + 1 : i))}
          onClose={() => setOpenIndex(null)}
          albums={albums}
          tagSuggestions={tagNames}
          onChanged={assetChanged}
        />
      )}
    </section>
  );
}
