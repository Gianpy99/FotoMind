# ADR-0005: AI providers are local-first

- Status: Proposed
- Date: 2026-11-02

## Decision

AI features (AI-LIB tagging, captions and search embeddings; AI-ENH denoise, upscale and
enhance; people/face clustering) run through provider interfaces in `modules/ai`. The
default providers run **locally on the Windows worker** (GPU). Any cloud provider must be:

- disabled by default and enabled per feature;
- given only derived images (never originals or file paths);
- recorded per result as provider, model and version (`ProcessingLocation`).

Face data is sensitive personal data (PRD §10). It stays in the local database, can be
deleted per person, and is never sent to cloud providers.

## Consequences

AI results record their model version, so they can be re-run when models change. Cloud use
can be audited.
