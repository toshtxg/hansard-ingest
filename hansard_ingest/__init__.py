"""Singapore Hansard ingestion package.

Pulls Hansard JSON from the Parliament API, parses HTML sections into
attendance / PTBA / speech tables, optionally generates AI summaries,
and upserts everything into Supabase.

Entrypoint: ``python ingest.py`` (which calls :func:`main.ingest`).
"""
