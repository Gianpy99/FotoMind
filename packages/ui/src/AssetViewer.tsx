import { useEffect, useRef, useState } from "react";
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
  formatBytes,
  formatDate,
  formatDuration,
  formatExposure,
  formatVideoInfo,
} from "./format";

export interface AssetViewerProps {
  client: FotoMindClient;
  asset: AssetSummary;
  hasPrev: boolean;
  hasNext: boolean;
  onPrev(): void;
  onNext(): void;
  onClose(): void;
  /** Albums offered in "Add to album". */
  albums?: Album[];
  /** Existing tag names, suggested while typing. */
  tagSuggestions?: string[];
  /** The asset's rating, tags or albums changed. */
  onChanged?(asset: AssetSummary): void;
}

type DetailState =
  { kind: "loading" } | { kind: "ready"; detail: AssetDetail } | { kind: "error"; message: string };

function isTyping(target: EventTarget | null): boolean {
  return (
    target instanceof HTMLElement &&
    (target.isContentEditable || ["INPUT", "SELECT", "TEXTAREA"].includes(target.tagName))
  );
}

export function AssetViewer({
  client,
  asset,
  hasPrev,
  hasNext,
  onPrev,
  onNext,
  onClose,
  albums = [],
  tagSuggestions = [],
  onChanged,
}: AssetViewerProps) {
  const [loaded, setLoaded] = useState<{ id: string; state: DetailState } | null>(null);
  // Derived, so switching assets shows "loading" without resetting state inside an effect.
  const state: DetailState = loaded?.id === asset.id ? loaded.state : { kind: "loading" };
  const [saving, setSaving] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [newTag, setNewTag] = useState("");
  const dialogRef = useRef<HTMLDivElement>(null);
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
    dialogRef.current?.focus();
    function onKey(event: KeyboardEvent) {
      if (isTyping(event.target)) return;
      if (event.key === "Escape") onClose();
      else if (event.key === "ArrowLeft" && hasPrev) onPrev();
      else if (event.key === "ArrowRight" && hasNext) onNext();
      else if (/^[0-5]$/.test(event.key) && ratingRef.current.canRate) {
        const value = Number(event.key);
        if (value !== ratingRef.current.rating) ratingRef.current.save({ rating: value });
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [hasPrev, hasNext, onPrev, onNext, onClose]);

  const dimensions = asset.width && asset.height ? `${asset.width} × ${asset.height}` : null;
  const camera = detail
    ? [detail.camera_make, detail.camera_model].filter(Boolean).join(" ") || null
    : null;
  const exposure = detail ? formatExposure(detail.metadata) : null;
  const videoInfo = detail ? formatVideoInfo(detail.metadata) : null;
  const inAlbums = new Set((detail?.albums ?? []).map((a) => a.id));
  const otherAlbums = albums.filter((a) => !inAlbums.has(a.id));
  const tags = detail?.tags ?? asset.tags ?? [];

  return (
    <div
      className="fm-viewer"
      role="dialog"
      aria-modal="true"
      aria-label={asset.display_name}
      tabIndex={-1}
      ref={dialogRef}
    >
      <div className="fm-viewer-stage">
        <button type="button" className="fm-viewer-nav" onClick={onPrev} disabled={!hasPrev}>
          <span aria-hidden="true">‹</span>
          <span className="fm-sr-only">Previous</span>
        </button>
        {asset.thumbnail_url ? (
          <img src={client.url(asset.thumbnail_url)} alt={asset.display_name} />
        ) : (
          <div className="fm-tile-placeholder">No preview yet</div>
        )}
        <button type="button" className="fm-viewer-nav" onClick={onNext} disabled={!hasNext}>
          <span aria-hidden="true">›</span>
          <span className="fm-sr-only">Next</span>
        </button>
      </div>

      <aside className="fm-viewer-info">
        <div className="fm-viewer-head">
          <h2>{asset.display_name}</h2>
          <button type="button" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>

        <StarRating
          value={rating}
          disabled={!detail || saving}
          onChange={(value) => save({ rating: value })}
        />

        <dl>
          <dt>Taken</dt>
          <dd>{formatDate(asset.captured_at ?? asset.sort_at)}</dd>
          {dimensions && (
            <>
              <dt>Size</dt>
              <dd>{dimensions}</dd>
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
          <dd>{asset.availability}</dd>
        </dl>

        {state.kind === "loading" && <p className="fm-muted">Loading details…</p>}
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
            <h3>Tags</h3>
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
                    ×
                  </button>
                </li>
              ))}
            </ul>
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
                list="fm-viewer-tags"
                maxLength={100}
                value={newTag}
                onChange={(e) => setNewTag(e.target.value)}
              />
              <datalist id="fm-viewer-tags">
                {tagSuggestions.map((t) => (
                  <option key={t} value={t} />
                ))}
              </datalist>
              <button type="submit" disabled={saving || !newTag.trim()}>
                Add
              </button>
            </form>

            <h3>Albums</h3>
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

            <h3>Files</h3>
            <ul className="fm-files">
              {detail.files.map((file) => (
                <li key={file.id}>
                  <code>
                    {file.storage_root_label}/{file.relative_path}
                  </code>
                  <span className="fm-muted">
                    {" "}
                    · {formatBytes(file.size_bytes)} · {file.role.replace("_", " ")}
                    {file.availability !== "online" && ` · ${file.availability}`}
                  </span>
                </li>
              ))}
            </ul>
            <p className="fm-muted fm-small">
              Originals stay on the PC; this is a preview. Ratings, tags and albums live in the
              catalogue and never modify the files.
            </p>
          </>
        )}
      </aside>
    </div>
  );
}
