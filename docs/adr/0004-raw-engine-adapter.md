# ADR-0004: RAW engine behind an adapter

- Status: Proposed
- Date: 2026-11-02

## Decision

RAW decoding and development (DEV requirements) live behind an `imaging` module port
(`RawDecoder` / `Renderer`). The first adapter will be LibRaw (via `rawpy`) on the Windows
worker. Edit recipes are engine-agnostic parameters (exposure, white balance, tone,
crop, …) plus an engine id and version. When an engine changes its output, the recipe
version changes too.

## Consequences

- The engine can be swapped for darktable-cli, RawTherapee or a GPU pipeline without
  changing the stored recipes.
- Renders are reproducible only for the same engine version, so previews record which
  engine version produced them.
- RAW work never runs on the Pi.
