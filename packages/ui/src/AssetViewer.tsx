import { useEffect, useRef, useState } from "react";
import type { AssetDetail, AssetSummary, FotoMindClient } from "@fotomind/api-client";
import { errorMessage, formatBytes, formatDate, formatDuration } from "./format";

export interface AssetViewerProps {
  client: FotoMindClient;
  asset: AssetSummary;
  hasPrev: boolean;
  hasNext: boolean;
  onPrev(): void;
  onNext(): void;
  onClose(): void;
}

type DetailState =
  { kind: "loading" } | { kind: "ready"; detail: AssetDetail } | { kind: "error"; message: string };

export function AssetViewer({
  client,
  asset,
  hasPrev,
  hasNext,
  onPrev,
  onNext,
  onClose,
}: AssetViewerProps) {
  const [loaded, setLoaded] = useState<{ id: string; state: DetailState } | null>(null);
  // Derived, so switching assets shows "loading" without resetting state inside an effect.
  const state: DetailState = loaded?.id === asset.id ? loaded.state : { kind: "loading" };
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    const id = asset.id;
    client
      .getAsset(id)
      .then((detail) => !cancelled && setLoaded({ id, state: { kind: "ready", detail } }))
      .catch(
        (err: unknown) =>
          !cancelled && setLoaded({ id, state: { kind: "error", message: errorMessage(err) } }),
      );
    return () => {
      cancelled = true;
    };
  }, [client, asset.id]);

  useEffect(() => {
    dialogRef.current?.focus();
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
      else if (event.key === "ArrowLeft" && hasPrev) onPrev();
      else if (event.key === "ArrowRight" && hasNext) onNext();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [hasPrev, hasNext, onPrev, onNext, onClose]);

  const detail = state.kind === "ready" ? state.detail : null;
  const dimensions = asset.width && asset.height ? `${asset.width} × ${asset.height}` : null;
  const camera = detail
    ? [detail.camera_make, detail.camera_model].filter(Boolean).join(" ") || null
    : null;

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
          <dt>Status</dt>
          <dd>{asset.availability}</dd>
        </dl>

        {state.kind === "loading" && <p className="fm-muted">Loading details…</p>}
        {state.kind === "error" && (
          <p role="alert" className="fm-error">
            {state.message}
          </p>
        )}
        {detail && (
          <>
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
              Originals stay on the PC; this is a preview. Full-resolution viewing comes later.
            </p>
          </>
        )}
      </aside>
    </div>
  );
}
