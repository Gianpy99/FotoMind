# ADR-0007: Originals are immutable

- Status: Accepted
- Date: 2026-11-02

## Decision

FotoMind never writes to, renames, moves or deletes original files. All edits, ratings,
tags and AI results live in the database (plus optional XMP sidecars, written only when
the user explicitly asks). Exports always go to new files.

The worker opens originals read-only. Any future "move/organise files" feature needs a new
ADR, an explicit confirmation step and backup verification first (STO).

## Consequences

The library can always be rebuilt from the originals plus a database backup
([docs/operations/database-backup-restore.md](../operations/database-backup-restore.md)).
