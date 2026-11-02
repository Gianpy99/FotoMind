"""Windows PC worker (ADR-0001 hybrid topology).

Runs next to the original media disks and the GPU: scanning/import, checksums, metadata,
thumbnails/previews, RAW development and AI jobs. It talks to the FotoMind API on the Pi over
HTTPS through the Family Portal and never connects to PostgreSQL directly.
"""
