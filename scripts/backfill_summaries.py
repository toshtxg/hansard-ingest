import argparse
import sys
from datetime import datetime

from hansard_ingest.ai_speech_summary import build_summary_update, needs_summary, summarize_row
from hansard_ingest.config import AI_DRY_RUN, AI_ENABLED, DEBUG, SKIP_DB, SCRIPT_VERSION
from hansard_ingest.db import supabase_client


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Backfill AI summaries for hansard_speeches.")
    p.add_argument("--start_date", required=True, help="YYYY-MM-DD")
    p.add_argument("--end_date", required=True, help="YYYY-MM-DD")
    p.add_argument("--limit", type=int, default=500, help="Max rows to process (default: 500)")
    p.add_argument("--batch_size", type=int, default=50, help="Fetch batch size (default: 50)")
    p.add_argument("--progress_every", type=int, default=10, help="Print progress every N rows (default: 10)")
    return p.parse_args()


def _validate_date(s: str) -> str:
    try:
        datetime.fromisoformat(s)
    except ValueError:
        raise RuntimeError(f"Invalid date: {s} (expected YYYY-MM-DD)")
    return s


def main() -> None:
    args = _parse_args()
    start_date = _validate_date(args.start_date)
    end_date = _validate_date(args.end_date)
    limit = args.limit if args.limit > 0 else 0
    batch_size = max(1, args.batch_size)
    progress_every = max(1, args.progress_every)

    if SKIP_DB:
        raise RuntimeError("SKIP_DB=true; set SKIP_DB=false for backfill.")
    if not AI_ENABLED or AI_DRY_RUN:
        print("AI summarization disabled (AI_ENABLED=false or AI_DRY_RUN=true); exiting.")
        return

    sb = supabase_client()

    processed = 0
    succeeded = 0
    failed = 0
    skipped = 0
    offset = 0

    print(
        f"Backfill speech summaries: {start_date} -> {end_date} "
        f"(limit={limit or 'all'}, batch_size={batch_size}, ver={SCRIPT_VERSION})"
    )

    while True:
        if limit and processed >= limit:
            break

        to_fetch = batch_size
        if limit:
            to_fetch = min(to_fetch, limit - processed)

        resp = (
            sb.table("hansard_speeches")
            .select(
                "sitting_date,row_num,speech_details,mp_name_fuzzy_matched,mp_name_raw,dim_speaker,summary_version,one_liner"
            )
            .gte("sitting_date", start_date)
            .lte("sitting_date", end_date)
            .order("sitting_date")
            .order("row_num")
            .range(offset, offset + to_fetch - 1)
            .execute()
        )

        rows = resp.data or []
        if not rows:
            break

        for row in rows:
            if limit and processed >= limit:
                break
            processed += 1

            if not needs_summary(row.get("one_liner"), row.get("summary_version")):
                skipped += 1
                if processed % progress_every == 0:
                    print(
                        f"Progress: processed={processed} succeeded={succeeded} failed={failed} skipped={skipped}"
                    )
                continue
            if not row.get("sitting_date") or row.get("row_num") is None:
                skipped += 1
                if processed % progress_every == 0:
                    print(
                        f"Progress: processed={processed} succeeded={succeeded} failed={failed} skipped={skipped}"
                    )
                continue

            speech = str(row.get("speech_details") or "")
            metadata = {
                "speaker_name": row.get("mp_name_fuzzy_matched") or row.get("mp_name_raw") or "",
                "role": row.get("dim_speaker") or "",
                "sitting_date": row.get("sitting_date") or "",
            }

            try:
                summary = summarize_row(speech, metadata)
                if not summary:
                    skipped += 1
                    continue
                update = build_summary_update(summary)
                (
                    sb.table("hansard_speeches")
                    .update(update)
                    .eq("sitting_date", row["sitting_date"])
                    .eq("row_num", row["row_num"])
                    .execute()
                )
                succeeded += 1
            except Exception as e:
                failed += 1
                print(f"Summary failed for {row.get('sitting_date')} row {row.get('row_num')}: {e}")
            finally:
                if processed % progress_every == 0:
                    print(
                        f"Progress: processed={processed} succeeded={succeeded} failed={failed} skipped={skipped}"
                    )

        offset += to_fetch
        print(f"Progress: processed={processed} succeeded={succeeded} failed={failed} skipped={skipped}")

    attempted = succeeded + failed
    if attempted > 0 and (failed / attempted) > 0.3:
        print("Failure rate exceeded 30%; exiting non-zero.")
        sys.exit(1)

    print(f"Done: processed={processed} succeeded={succeeded} failed={failed} skipped={skipped}")


if __name__ == "__main__":
    main()
