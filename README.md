# Parse Hansard (Singapore Parliament)

## What this project does
This project ingests Singapore Parliament Hansard transcripts, parses attendance/PTBA/speeches,
optionally generates an AI summary per sitting, writes the cleaned data to Supabase, and powers
`index.html`, a small dashboard that visualizes speaking activity with charts and KPIs.
PTBA = Permission to be Absent (approved leave windows for MPs).

## How it flows to `index.html`
1) `ingest.py` calls `hansard_ingest.main.ingest()` to run an ingestion pass over one or more dates.
2) `hansard_ingest.fetch.fetch_hansard_json()` pulls the raw Hansard JSON from the Parliament API.
3) `hansard_ingest.parse.parse_one_sitting()` parses HTML sections into three DataFrames:
   attendance, PTBA, and speech rows with per-speaker metadata.
4) `hansard_ingest.db.upsert_all()` de-duplicates and upserts rows into Supabase tables:
   `hansard_attendance`, `hansard_ptba`, `hansard_speeches`, and `hansard_sittings`.
5) `hansard_ingest.ai_summary.generate_ai_summary()` (optional) adds a 3-sentence sitting summary
   into `hansard_ai_summaries`.
6) `index.html` calls Supabase RPCs (`top10_words`, `top10_times_spoken`, `wp_share`,
   `list_sittings`, `get_ai_summary`) to render charts and tables with Chart.js.

## Repository structure (high level)

### `hansard_ingest/` package
- `main.py`: orchestration for date ranges, error handling, and per-day ingestion.
- `fetch.py`: HTTP fetch for Hansard JSON by sitting date.
- `parse.py`: HTML parsing + transformation to attendance/PTBA/speeches DataFrames.
- `names.py`: name cleaning, chair inference, and fuzzy matching utilities.
- `db.py`: Supabase client + upsert logic (dedupe, batching, conflict targets).
- `ai_summary.py`: optional OpenAI-based summary generation and prompt shaping.
- `config.py`: environment-driven configuration (dates, debug, Supabase, AI).
- `utils.py`: date parsing, CSV/JSON debug outputs, de-dupe helpers.
- `__init__.py`: package marker (empty).

### Top-level entrypoints and UI
- `ingest.py`: CLI entrypoint for running the ingestion pipeline.
- `index.html`: dashboard that reads Supabase RPCs and visualizes results.
- `hansard_page.html`: saved source page snapshot for reference during parsing.
- `scripts/ingest_tasks.sh`: convenience wrapper for common ingest modes.
- `scripts/hansard_sports_job.py`: optional job to classify speeches with sports mentions.
- `requirements.txt`: Python dependencies for ingestion.

### Data outputs and samples
- `Docs/`: sample JSON/CSV outputs for specific sitting dates.
- `hansard_*.json`, `*_list_*.csv`: debug artifacts written when `DEBUG=true`.

## What ends up on `index.html`
`index.html` is the final consumer: it reads aggregated data from Supabase RPCs and renders
two charts (most words, most times spoken), a WP share KPI, and an AI summary table.
Those RPCs are backed by the tables populated via `ingest.py` and `hansard_ingest/`.
