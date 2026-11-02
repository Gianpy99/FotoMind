# ADR-0006: pgvector is optional

- Status: Spike needed
- Date: 2026-11-02

## Context

Semantic search and face clustering need vector similarity. The Pi runs Debian 12 with
native PostgreSQL 15, and `postgresql-15-pgvector` is **not installed and has no apt
candidate** in the current sources (checked 2026-11-02).

## Decision

- Core features must not depend on pgvector. `pg_trgm` (always available) covers text
  search.
- Embeddings are stored as `real[]` or `bytea`, together with their model id, so they are
  portable.
- The spike should evaluate: (a) adding the PGDG apt repo on the Pi to install pgvector,
  (b) a separate vector index on the Windows worker (FAISS or sqlite-vec) that serves
  similarity queries, or (c) brute-force search in the API for small libraries.

## Consequences

Vector search stays behind a `search` module port until the spike decides.
