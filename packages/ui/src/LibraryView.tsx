import { useCallback, useEffect, useState } from "react";
import type { AssetSummary, AssetType, FotoMindClient } from "@fotomind/api-client";
import { AssetViewer } from "./AssetViewer";
import { errorMessage, formatDuration } from "./format";

const PAGE_SIZE = 100;

type TypeFilter = AssetType | "all";

interface LibraryState {
  items: AssetSummary[];
  total: number;
  cursor: string | null;
  loading: boolean;
  error: string | null;
}

const EMPTY: LibraryState = { items: [], total: 0, cursor: null, loading: true, error: null };

export function LibraryView({ client }: { client: FotoMindClient }) {
  const [filter, setFilter] = useState<TypeFilter>("all");
  const [state, setState] = useState<LibraryState>(EMPTY);
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  const fetchPage = useCallback(
    (cursor: string | null) =>
      client.listAssets({
        limit: PAGE_SIZE,
        cursor,
        asset_type: filter === "all" ? undefined : filter,
      }),
    [client, filter],
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
  }, [fetchPage]);

  function changeFilter(next: TypeFilter) {
    setFilter(next);
    setState(EMPTY);
    setOpenIndex(null);
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

  return (
    <section aria-labelledby="fm-library-title" className="fm-library">
      <div className="fm-toolbar">
        <h2 id="fm-library-title">Library</h2>
        <span className="fm-muted">{state.loading ? "Loading…" : `${state.total} items`}</span>
        <label className="fm-toolbar-end">
          Show{" "}
          <select value={filter} onChange={(e) => changeFilter(e.target.value as TypeFilter)}>
            <option value="all">Photos &amp; videos</option>
            <option value="photo">Photos</option>
            <option value="video">Videos</option>
          </select>
        </label>
      </div>

      {state.error && (
        <p role="alert" className="fm-error">
          Could not load the library: {state.error}
        </p>
      )}

      {!state.loading && !state.error && state.items.length === 0 && (
        <p className="fm-empty">
          Nothing catalogued yet. Add a folder on your PC with{" "}
          <code>fotomind-worker roots add &lt;folder&gt;</code>, then press <em>Scan now</em> in
          Sources.
        </p>
      )}

      <ul className="fm-grid">
        {state.items.map((asset, index) => (
          <li key={asset.id}>
            <button
              type="button"
              className="fm-tile"
              onClick={() => setOpenIndex(index)}
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
            </button>
          </li>
        ))}
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
        />
      )}
    </section>
  );
}
