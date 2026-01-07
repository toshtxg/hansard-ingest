import csv
import json
import re
from datetime import date, datetime
from typing import List, Optional

import pandas as pd

from .config import DEBUG, SAVE_JSON


def normalize_ws(s: str) -> str:
    """Normalize whitespace to reduce invisible-difference dupes (NBSP, multiple spaces)."""
    if s is None:
        return ""
    x = str(s).replace("\u00a0", " ")
    x = re.sub(r"\s+", " ", x)
    return x.strip()


def normalize_df_pk_cols(df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
    """Normalize PK columns in-place-safe copy (strip + collapse ws) for de-dup/upsert."""
    if df is None or df.empty:
        return df
    out = df.copy()
    for c in cols:
        if c in out.columns:
            out[c] = out[c].astype(str).map(normalize_ws)
    return out


def word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text or ""))


def parse_sitting_date(s: str) -> date:
    return datetime.strptime(s, "%d-%m-%Y").date()


def parse_run_date(s: str) -> Optional[date]:
    """Parse RUN_DATE in either YYYY-MM-DD or DD-MM-YYYY."""
    if not s:
        return None
    t = str(s).strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(t, fmt).date()
        except ValueError:
            continue
    return None


def parse_day_month(text: str, year: int) -> Optional[date]:
    if not text:
        return None
    t = re.sub(r"\s+", " ", str(text).strip())
    for fmt in ("%d %b", "%d %B"):
        try:
            dt = datetime.strptime(t, fmt).date()
            return date(year, dt.month, dt.day)
        except ValueError:
            continue
    return None


def extract_year(value: object, fallback: int) -> int:
    """Extract a 4-digit year from year-like metadata fields.

    Handles: 2024, '2024', '2017/2018', 'FY2017/2018', etc.
    Returns fallback if no year is found.
    """
    if value is None:
        return fallback
    if isinstance(value, int):
        return value
    s = str(value).strip()
    if not s:
        return fallback
    m = re.search(r"(19\d{2}|20\d{2})", s)
    return int(m.group(1)) if m else fallback


def ddmmyyyy_from_date(d: date) -> str:
    return d.strftime("%d-%m-%Y")


# ---------- Output helpers ----------

def maybe_write_csv(df: pd.DataFrame, path: str):
    if not DEBUG:
        return
    df.to_csv(path, index=False, encoding="utf-8", quoting=csv.QUOTE_ALL, escapechar="\\")


def maybe_write_json(data: dict, path: str):
    if not (DEBUG and SAVE_JSON):
        return
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def chunk_records(records: List[dict], n: int):
    for i in range(0, len(records), n):
        yield records[i : i + n]
