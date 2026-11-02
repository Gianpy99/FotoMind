import { useEffect, useRef } from "react";
import { ChevronLeft, ChevronRight, X } from "lucide-react";
import type { Album, AssetSummary, FotoMindClient } from "@fotomind/api-client";
import { AssetInspector, isTyping } from "./AssetInspector";

export interface AssetViewerProps {
  client: FotoMindClient;
  asset: AssetSummary;
  hasPrev: boolean;
  hasNext: boolean;
  onPrev(): void;
  onNext(): void;
  onClose(): void;
  albums?: Album[];
  tagSuggestions?: string[];
  onChanged?(asset: AssetSummary): void;
}

export function AssetViewer({
  client,
  asset,
  hasPrev,
  hasNext,
  onPrev,
  onNext,
  onClose,
  albums,
  tagSuggestions,
  onChanged,
}: AssetViewerProps) {
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    dialogRef.current?.focus();
    function onKey(event: KeyboardEvent) {
      if (isTyping(event.target)) return;
      if (event.key === "Escape") onClose();
      else if (event.key === "ArrowLeft" && hasPrev) onPrev();
      else if (event.key === "ArrowRight" && hasNext) onNext();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [hasPrev, hasNext, onPrev, onNext, onClose]);

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
        <button
          type="button"
          className="fm-viewer-nav"
          onClick={onPrev}
          disabled={!hasPrev}
          aria-label="Previous"
        >
          <ChevronLeft aria-hidden="true" />
        </button>
        {asset.thumbnail_url ? (
          <img src={client.url(asset.thumbnail_url)} alt={asset.display_name} />
        ) : (
          <div className="fm-tile-placeholder">No preview yet</div>
        )}
        <button
          type="button"
          className="fm-viewer-nav"
          onClick={onNext}
          disabled={!hasNext}
          aria-label="Next"
        >
          <ChevronRight aria-hidden="true" />
        </button>
      </div>

      <aside className="fm-inspector fm-viewer-inspector" aria-label="Details">
        <AssetInspector
          client={client}
          asset={asset}
          albums={albums}
          tagSuggestions={tagSuggestions}
          onChanged={onChanged}
          hotkeys
          actions={
            <button type="button" className="fm-icon-btn" onClick={onClose} aria-label="Close">
              <X aria-hidden="true" />
            </button>
          }
        />
      </aside>
    </div>
  );
}
