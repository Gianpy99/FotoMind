# ADR-0002: Storage model

- Status: Accepted (schema lands in EPIC 2)
- Date: 2026-11-02

## Context

The PRD (LIB, VID, STO) needs photos, videos, RAW+JPEG pairs, sidecars and multiple disks
that may be offline. The PRD §8 table is photo-centric, but its text requires a generic
media asset that covers both photos and videos.

## Decision

- `storage_root`: a registered root folder on the PC (label, volume serial or ID, last
  seen path). Paths are always stored **relative to a root**, so a disk can be remounted
  under a different letter.
- `media_asset`: the logical item the user sees (`AssetType` photo/video), with capture
  time, rating, flags and `Availability`.
- `media_file`: the physical files behind an asset (`MediaFileRole`: original, raw, jpeg
  pair, sidecar, live-photo video, …). Each file has a content hash, size and mtime, which
  are used for duplicate detection and move tracking.
- Derived files (thumbnails, previews and renders) are addressed by
  `(asset_id, kind, edit_version)` and stored outside the original roots (Pi data volume
  for previews, PC cache for large renders).
- Edits are stored as versioned recipes on the asset, never as pixels (ADR-0007).
- `BackupState` is tracked per original file.

## Consequences

- Moving or renaming files only updates `media_file` rows when the hashes match.
- Offline disks don't delete anything. Assets are marked `Availability.offline`.
- The baseline migration only enables `pg_trgm`, and the tables above arrive in EPIC 2.
