from datetime import date, datetime, timedelta

from .ai_summary import generate_ai_summary
from .config import (
    AI_DRY_RUN,
    AI_ENABLED,
    DEBUG,
    SAVE_JSON,
    END_DATE_ISO,
    MAX_DAYS_PER_RUN,
    RUN_DATE,
    SCRIPT_VERSION,
    SKIP_DB,
    START_DATE_ISO,
)
from .db import get_latest_sitting, supabase_client, upsert_all
from .fetch import fetch_hansard_json
from .parse import parse_one_sitting
from .utils import ddmmyyyy_from_date, maybe_write_csv, maybe_write_json, parse_run_date


def ingest():
    sb = None if SKIP_DB else supabase_client()

    today = date.today()

    run_dt = parse_run_date(RUN_DATE)
    if run_dt is not None:
        # Single-date test run
        start_dt = run_dt
        end_dt = run_dt
    else:
        end_dt = datetime.strptime(END_DATE_ISO, "%Y-%m-%d").date() if END_DATE_ISO else today

        if START_DATE_ISO:
            start_dt = datetime.strptime(START_DATE_ISO, "%Y-%m-%d").date()
        else:
            latest = get_latest_sitting(sb) if sb is not None else None
            start_dt = (latest + timedelta(days=1)) if latest else date(2020, 1, 1)

        # Optional cap per run (GitHub Actions friendly). Set MAX_DAYS_PER_RUN=0 to disable.
        if MAX_DAYS_PER_RUN and MAX_DAYS_PER_RUN > 0:
            if (end_dt - start_dt).days + 1 > MAX_DAYS_PER_RUN:
                end_dt = start_dt + timedelta(days=MAX_DAYS_PER_RUN - 1)

    print(
        "Ingest range: "
        f"{start_dt.isoformat()} -> {end_dt.isoformat()} "
        f"(ver={SCRIPT_VERSION}, RUN_DATE={RUN_DATE or 'auto'}, "
        f"DEBUG={DEBUG}, SAVE_JSON={SAVE_JSON}, SKIP_DB={SKIP_DB})"
    )

    d = start_dt
    while d <= end_dt:
        ddmmyyyy = ddmmyyyy_from_date(d)

        try:
            data = fetch_hansard_json(ddmmyyyy)
        except Exception as e:
            print(f"Fetch failed for {ddmmyyyy}: {e}")
            d += timedelta(days=1)
            continue

        if DEBUG and SAVE_JSON:
            maybe_write_json(data, f"hansard_{ddmmyyyy}.json")

        try:
            df_att, df_ptba, df_speech, source_url, parliament_no, sitting_dt = parse_one_sitting(data)
        except Exception as e:
            print(f"Parse failed for {ddmmyyyy}: {e}")
            d += timedelta(days=1)
            continue

        # ---- AI summary (optional) ----
        ai_row = None
        if AI_ENABLED:
            try:
                ai_row = generate_ai_summary(d.isoformat(), df_speech)
                if DEBUG and ai_row:
                    preview = ai_row.get("summary_3_sentences", "")[:120]
                    print(f"[DEBUG] AI summary generated for {ddmmyyyy}: {preview}...")
                if AI_DRY_RUN and ai_row:
                    print(f"[AI_DRY_RUN] {d.isoformat()} summary:\n{ai_row.get('summary_3_sentences','')}")
            except Exception as e:
                print(f"AI summary failed for {ddmmyyyy}: {e}")

        if DEBUG:
            maybe_write_csv(df_att, f"attendance_list_{ddmmyyyy}.csv")
            maybe_write_csv(df_ptba, f"ptba_list_{ddmmyyyy}.csv")
            maybe_write_csv(df_speech, f"speech_list_{ddmmyyyy}.csv")

        if len(df_att) == 0 and len(df_speech) == 0:
            print(f"No sitting detected for {ddmmyyyy}; skipping insert")
            d += timedelta(days=1)
            continue

        if sb is None:
            print(f"SKIP_DB=true; parsed {ddmmyyyy}: att={len(df_att)} ptba={len(df_ptba)} speech={len(df_speech)}")
        else:
            try:
                if AI_DRY_RUN:
                    # Prevent AI summary DB writes during dry run
                    ai_row = None
                upsert_all(sb, df_att, df_ptba, df_speech, d.isoformat(), source_url, ai_summary_row=ai_row)
                print(f"Inserted {ddmmyyyy}: att={len(df_att)} ptba={len(df_ptba)} speech={len(df_speech)}")
            except Exception as e:
                print(f"DB insert failed for {ddmmyyyy}: {e}")

        d += timedelta(days=1)
