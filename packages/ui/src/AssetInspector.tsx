import { useEffect, useRef, useState, type ReactNode } from "react";
import { Plus, X } from "lucide-react";
import type {
  Album,
  AssetDetail,
  AssetSummary,
  AssetUpdate,
  FotoMindClient,
} from "@fotomind/api-client";
import { StarRating } from "./StarRating";
import {
  errorMessage,
  fileFormat,
  formatBytes,
  formatDate,
  formatDuration,
  formatExposure,
  formatVideoInfo,
  isRawFormat,
} from "./format";

export interface AssetInspectorProps {
  client: FotoMindClient;
  asset: AssetSummary;
  /** Albums offered in "Add to album". */
  albums?: Album[];
  /** Existing tag names, suggested while typing. */
  tagSuggestions?: string[];
  /** The asset's rating, tags or albums changed. */
  onChanged?(asset: AssetSummary): void;
  /** Keys 0–5 set the rating while this panel is shown. */
  hotkeys?: boolean;
  /** Show the thumbnail at the top (docked in the library). */
  preview?: boolean;
  /** Buttons next to the title (open, close). */
  actions?: ReactNode;
}

type DetailState =
  { kind: "loading" } | { kind: "ready"; detail: AssetDetail } | { kind: "error"; message: string };

export function isTyping(target: EventTarget | null): boolean {
  return (
    target instanceof HTMLElement &&
    (target.isContentEditable || ["INPUT", "SELECT", "TEXTAREA"].includes(target.tagName))
  );
}

export function AssetInspector({
  client,
  asset,
  albums = [],
  tagSuggestions = [],
  onChanged,
  hotkeys = false,
  preview = false,
  actions,
}: AssetInspectorProps) {
  const [loaded, setLoaded] = useState<{ id: string; state: DetailState } | null>(null);
  // Derived, so switching assets shows "loading" without resetting state inside an effect.
  const state: DetailState = loaded?.id === asset.id ? loaded.state : { kind: "loading" };
  const [saving, setSaving] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [newTag, setNewTag] = useState("");
  const detail = state.kind === "ready" ? state.detail : null;

  useEffect(() => {
    let cancelled = false;
    const id = asset.id;
    client
      .getAsset(id)
      .then((d) => !cancelled && setLoaded({ id, state: { kind: "ready", detail: d } }))
      .catch(
        (err: unknown) =>
          !cancelled && setLoaded({ id, state: { kind: "error", message: errorMessage(err) } }),
      );
    return () => {
      cancelled = true;
    };
  }, [client, asset.id]);

  function save(body: AssetUpdate) {
    const id = asset.id;
    setSaving(true);
    setActionError(null);
    client.updateAsset(id, body).then(
      (updated) => {
        setLoaded({ id, state: { kind: "ready", detail: updated } });
        setSaving(false);
        onChanged?.(updated);
      },
      (err: unknown) => {
        setSaving(false);
        setActionError(errorMessage(err));
      },
    );
  }

  function addTag() {
    const name = newTag.trim();
    if (!detail || !name) return;
    setNewTag("");
    if (!detail.tags?.some((t) => t.toLowerCase() === name.toLowerCase())) {
      save({ tags: [...(detail.tags ?? []), name] });
    }
  }

  function addToAlbum(albumId: string) {
    const album = albums.find((a) => a.id === albumId);
    if (!detail || !album) return;
    const id = asset.id;
    setActionError(null);
    client.addToAlbum(albumId, [id]).then(
      () => {
        const next = {
          ...detail,
          albums: [...(detail.albums ?? []), { id: album.id, name: album.name }],
        };
        setLoaded({ id, state: { kind: "ready", detail: next } });
        onChanged?.(next);
      },
      (err: unknown) => setActionError(errorMessage(err)),
    );
  }

  const rating = detail?.rating ?? asset.rating;
  const ratingRef = useRef({ rating, canRate: detail !== null && !saving, save });
  useEffect(() => {
    ratingRef.current = { rating, canRate: detail !== null && !saving, save };
  });

  useEffect(() => {
    if (!hotkeys) return;
    function onKey(event: KeyboardEvent) {
      if (isTyping(event.target) || event.ctrlKey || event.metaKey || event.altKey) return;
      if (/^[0-5]$/.test(event.key) && ratingRef.current.canRate) {
        const value = Number(event.key);
        if (value !== ratingRef.current.rating) ratingRef.current.save({ rating: value });
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [hotkeys]);

  const format = fileFormat(asset.display_name);
  const dimensions = asset.width && asset.height ? `${asset.width} × ${asset.height}` : null;
  const camera = detail
    ? [detail.camera_make, detail.camera_model].filter(Boolean).join(" ") || null
    : null;
  const exposure = detail ? formatExposure(detail.metadata) : null;
  const videoInfo = detail ? formatVideoInfo(detail.metadata) : null;
  const original = detail?.files.find((f) => f.role === "original") ?? detail?.files[0];
  const inAlbums = new Set((detail?.albums ?? []).map((a) => a.id));
  const otherAlbums = albums.filter((a) => !inAlbums.has(a.id));
  const tags = detail?.tags ?? asset.tags ?? [];

  return (
    <div className="fm-inspector-body">
      {preview && (
        <div className="fm-inspector-preview">
          {asset.thumbnail_url ? (
            <img src={client.url(asset.thumbnail_url)} alt="" />
          ) : (
            <span className="fm-tile-placeholder">No preview yet</span>
          )}
        </div>
      )}

      <div className="fm-inspector-head">
        <h2 title={asset.display_name}>{asset.display_name}</h2>
        {format && (
          <span className={isRawFormat(format) ? "fm-pill fm-pill-accent" : "fm-pill"}>
            {format}
          </span>
        )}
        {actions}
      </div>

      <dl className="fm-meta">
        <dt>Taken</dt>
        <dd>{formatDate(asset.captured_at ?? asset.sort_at)}</dd>
        {dimensions && (
          <>
            <dt>Size</dt>
            <dd>
              {dimensions}
              {original && ` · ${formatBytes(original.size_bytes)}`}
            </dd>
          </>
        )}
        {asset.asset_type === "video" && (
          <>
            <dt>Duration</dt>
            <dd>{formatDuration(asset.duration_s)}</dd>
          </>
        )}
        {videoInfo && (
          <>
            <dt>Video</dt>
            <dd>{videoInfo}</dd>
          </>
        )}
        {camera && (
          <>
            <dt>Camera</dt>
            <dd>{camera}</dd>
          </>
        )}
        {detail?.lens_model && (
          <>
            <dt>Lens</dt>
            <dd>{detail.lens_model}</dd>
          </>
        )}
        {exposure && (
          <>
            <dt>Exposure</dt>
            <dd>{exposure}</dd>
          </>
        )}
        <dt>Status</dt>
        <dd>
          <span className={`fm-status fm-status-${asset.availability}`}>{asset.availability}</span>
        </dd>
      </dl>

      <StarRating
        value={rating}
        disabled={!detail || saving}
        onChange={(value) => save({ rating: value })}
      />

      {state.kind === "loading" && <p className="fm-muted fm-small">Loading details…</p>}
      {state.kind === "error" && (
        <p role="alert" className="fm-error">
          {state.message}
        </p>
      )}
      {actionError && (
        <p role="alert" className="fm-error">
          {actionError}
        </p>
      )}

      {detail && (
        <>
          <section className="fm-panel-section" aria-labelledby={`fm-tags-${asset.id}`}>
            <h3 id={`fm-tags-${asset.id}`}>Tags</h3>
            {tags.length > 0 && (
              <ul className="fm-chips" aria-label="Tags">
                {tags.map((tag) => (
                  <li key={tag} className="fm-chip">
                    {tag}
                    <button
                      type="button"
                      aria-label={`Remove tag ${tag}`}
                      disabled={saving}
                      onClick={() => save({ tags: tags.filter((t) => t !== tag) })}
                    >
                      <X aria-hidden="true" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <form
              className="fm-inline-form"
              onSubmit={(e) => {
                e.preventDefault();
                addTag();
              }}
            >
              <input
                aria-label="New tag"
                placeholder="Add a tag"
                list="fm-inspector-tags"
                maxLength={100}
                value={newTag}
                onChange={(e) => setNewTag(e.target.value)}
              />
              <datalist id="fm-inspector-tags">
                {tagSuggestions.map((t) => (
                  <option key={t} value={t} />
                ))}
              </datalist>
              <button type="submit" className="fm-btn" disabled={saving || !newTag.trim()}>
                <Plus aria-hidden="true" />
                Add
              </button>
            </form>
          </section>

          <section className="fm-panel-section" aria-labelledby={`fm-albums-${asset.id}`}>
            <h3 id={`fm-albums-${asset.id}`}>Albums</h3>
            {(detail.albums ?? []).length > 0 ? (
              <ul className="fm-chips" aria-label="Albums">
                {(detail.albums ?? []).map((album) => (
                  <li key={album.id} className="fm-chip">
                    {album.name}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="fm-muted fm-small">Not in any album.</p>
            )}
            {otherAlbums.length > 0 && (
              <select
                aria-label="Add to album"
                value=""
                onChange={(e) => addToAlbum(e.target.value)}
              >
                <option value="">Add to album…</option>
                {otherAlbums.map((album) => (
                  <option key={album.id} value={album.id}>
                    {album.name}
                  </option>
                ))}
              </select>
            )}
          </section>

          <section className="fm-panel-section" aria-labelledby={`fm-files-${asset.id}`}>
            <h3 id={`fm-files-${asset.id}`}>Files</h3>
            <ul className="fm-files">
              {detail.files.map((file) => (
                <li key={file.id}>
                  <code>
                    {file.storage_root_label}/{file.relative_path}
                  </code>
                  <span className="fm-muted">
                    {formatBytes(file.size_bytes)} · {file.role.replace("_", " ")}
                    {file.availability !== "online" && ` · ${file.availability}`}
                  </span>
                </li>
              ))}
            </ul>
            <p className="fm-muted fm-small">
              Originals stay on the PC; this is a preview. Ratings, tags and albums live in the
              catalogue and never modify the files.
            </p>
          </section>
        </>
      )}
    </div>
  );
}
