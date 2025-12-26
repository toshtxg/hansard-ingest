import json, re, csv, os
import requests
from datetime import datetime, date, timedelta
import pandas as pd
from bs4 import BeautifulSoup
from typing import Optional, List, Tuple, Dict
from supabase import create_client, Client

from dotenv import load_dotenv
load_dotenv()

# ---------------------------
# Version stamp so you can confirm you are running the file you just edited.
# Bump this when you make changes.
SCRIPT_VERSION = "2025-12-25.1"

# --------- CONFIG ----------
BASE_URL = "https://sprs.parl.gov.sg/search/getHansardReport/"

def env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return str(v).strip().lower() in {"1", "true", "yes", "y"}

def env_str(name: str, default: str = "") -> str:
    v = os.getenv(name)
    return default if v is None else str(v)

def env_int(name: str, default: int) -> int:
    v = os.getenv(name)
    try:
        return int(v) if v is not None and str(v).strip() != "" else default
    except ValueError:
        return default

DEBUG = env_bool("DEBUG", False)
SAVE_JSON = env_bool("SAVE_JSON", False) if DEBUG else False

# Optional override range (ISO: YYYY-MM-DD)
START_DATE_ISO = env_str("START_DATE", "")
END_DATE_ISO = env_str("END_DATE", "")

# Optional safety cap per run (good for GitHub Actions). Set to 0 to disable.
MAX_DAYS_PER_RUN = env_int("MAX_DAYS_PER_RUN", 0)

# Supabase
SUPABASE_URL = env_str("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = env_str("SUPABASE_SERVICE_ROLE_KEY", "")

# If true, parse + write CSV/JSON locally but do NOT talk to Supabase
SKIP_DB = env_bool("SKIP_DB", False)

# Optional single-run date override (accepts YYYY-MM-DD or DD-MM-YYYY)
RUN_DATE = env_str("RUN_DATE", "")

# ---------------------------

HONORIFICS_RE = r"(?:Mr|Ms|Mrs|Mdm|Madam|Miss|Dr|Prof|Professor|Er\s+Dr|Assoc\s*Prof\.?\s*Dr\.?|Assoc\s*Prof\.?)"

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

# Names that the Chair calls out (not substantive speeches)
CHAIR_CALL_HONORIFICS_RE = r"(?:Mr|Ms|Mrs|Mdm|Madam|Miss|Dr|Assoc\s+Prof\s+Dr|Assoc\s+Prof|Professor|Prof|Er)"

def word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text or ""))

def chair_role(chair_raw: str):
    if not chair_raw:
        return None
    u = chair_raw.upper()
    if "DEPUTY SPEAKER" in u:
        return "deputy_speaker"
    if "SPEAKER" in u:
        return "speaker"
    return None

def strip_trailing_chair_call(text: str) -> str:
    if not text:
        return text
    return re.sub(r"\s+(Mr|Madam)\s+Speaker\.?\s*$", "", text, flags=re.I).rstrip()

def name_key(name_raw: str) -> str:
    """Stable key for matching person names across decorated labels."""
    if not name_raw:
        return ""
    s = str(name_raw).strip()
    s = re.sub(r"^(%s)\s+" % HONORIFICS_RE, "", s, flags=re.I)
    s = re.sub(r"\([^)]*\)", "", s)      # remove constituency etc
    s = s.split(",")[0]                  # remove roles/portfolios
    s = re.sub(r"\s+", " ", s).strip(" .")
    return s.upper()

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

def ptba_overlaps_sitting(rec: dict, sitting_dt: date, default_year: int) -> bool:
    start = parse_day_month(rec.get("from"), default_year)
    end = parse_day_month(rec.get("to"), default_year)
    if start is None or end is None:
        return False
    if end < start:  # cross-year edge case
        end = date(default_year + 1, end.month, end.day)
    return start <= sitting_dt <= end

def extract_chair_marker(text: str):
    t = (text or "").strip()
    if "in the Chair" not in t or not t.startswith("[") or "SPEAKER" not in t.upper():
        return None
    m = re.match(r"^\[(.+?)\s+in\s+the\s+Chair\.?\]\s*$", t, flags=re.I)
    return m.group(1).strip() if m else None

def infer_chair_from_speaker_label(speaker_raw: str) -> Optional[str]:
    """If the speaker label itself indicates the Chair, return an appropriate chair_name_raw."""
    if not speaker_raw:
        return None
    s = str(speaker_raw).strip()
    u = s.upper()
    # Common Hansard labels
    if "DEPUTY SPEAKER" in u:
        return s  # e.g. 'Mr Deputy Speaker' or 'Mr Deputy Speaker (Mr X...)'
    if u in {"MR SPEAKER", "MADAM SPEAKER", "SPEAKER"} or "SPEAKER" in u:
        # Avoid catching 'Deputy Speaker' which is handled above
        if "DEPUTY" not in u:
            return s
    return None

def is_question_paper_item(speaker_raw: str, speech: str) -> bool:
    """
    Detect non-spoken Question Time listings like:
      '1 Mr X asked the Minister ...'
    These are not debate speeches.
    """
    if not speaker_raw or not speech:
        return False
    s = re.sub(r"\s+", " ", speech.replace("\xa0", " ")).strip()
    sp = re.sub(r"\s+", " ", speaker_raw).strip()

    # Must start with a question number, then the same speaker name, then "asked"
    pat = re.compile(rf"^\d+\s+{re.escape(sp)}\s+asked\b", flags=re.I)
    if not pat.search(s):
        return False

    # Usually directed at Minister/PM/etc
    return re.search(
        r"\basked\s+(?:the\s+)?(?:minister|prime minister|deputy prime minister|parliamentary secretary)\b",
        s, flags=re.I
    ) is not None


# Detect procedural Chair call-outs like 'Mr Patrick Tay.' or 'Er Dr Lee Bee Wah.'
def is_chair_call_to_member(text: str) -> bool:
    """Detect Chair call-outs like 'Mr Patrick Tay.' or 'Er Dr Lee Bee Wah.'

    These are procedural (Chair calling the next Member), not substantive speeches.
    """
    if not text:
        return False
    t = re.sub(r"\s+", " ", str(text).replace("\xa0", " ")).strip()
    # Common formats end with a period; keep this conservative
    if not t.endswith("."):
        return False
    # Very short and looks like a name with honorific
    words = re.findall(r"\b\w+\b", t)
    if len(words) > 7:
        return False
    if not re.match(rf"^({CHAIR_CALL_HONORIFICS_RE})\b", t, flags=re.I):
        return False
    # Avoid treating actual sentences as call-outs
    if re.search(r"\b(thank|ask|welcome|move|agree|urge|request|clarif|supplementary|question)\b", t, flags=re.I):
        return False
    return True


def extract_person_from_speaker_attendance(mp_name_raw: str) -> Optional[str]:
    """Extract person name from strings like: 'Mr SPEAKER (Mr Seah Kian Peng (Marine Parade)).'"""
    if not mp_name_raw:
        return None
    s = str(mp_name_raw).strip()

    # Take the substring inside the OUTERMOST parentheses (handles nested parentheses)
    l = s.find("(")
    r = s.rfind(")")
    if l == -1 or r == -1 or r <= l:
        return None

    inner = s[l + 1 : r].strip().strip(".")

    # Drop trailing constituency parentheses if present
    inner = re.sub(r"\s*\([^)]*\)\s*$", "", inner).strip(" .")

    # Drop honorific for chair_name output
    inner = re.sub(r"^(%s)\s+" % HONORIFICS_RE, "", inner, flags=re.I)

    return inner.strip() or None



def extract_person_from_name(raw: str) -> Optional[str]:
    """Best-effort extraction of a person's name from a label; keeps it deterministic (no web/LLM)."""
    if not raw:
        return None
    s = str(raw).strip()
    # Match a person name inside parentheses, including multi-token honorifics like 'Assoc Prof Dr'
    m = re.search(r"\((%s)\s+[^)]+\)" % HONORIFICS_RE, s, flags=re.I)
    if m:
        inner = m.group(0).strip("() ")
        # Remove any trailing constituency parentheses within the captured text
        inner = re.sub(r"\s*\([^)]*\)\s*$", "", inner).strip(" .")
        # Remove leading honorific(s)
        inner = re.sub(r"^(?:(%s)\s+)+" % HONORIFICS_RE, "", inner, flags=re.I).strip()
        inner = re.sub(r"\s+", " ", inner).strip(" .")
        return inner.strip() or None

    # If label is 'Mr Speaker' or 'Mr Deputy Speaker' etc, return None (resolved via attendance map)
    if re.search(r"\bSPEAKER\b", s, flags=re.I):
        return None

    # Otherwise treat it as already a person name; remove honorific, any parentheses, and trailing roles
    s2 = re.sub(r"^(%s)\s+" % HONORIFICS_RE, "", s, flags=re.I)
    s2 = s2.split(",", 1)[0].strip()
    s2 = re.sub(r"\([^)]*\)", " ", s2)  # remove any parentheses anywhere
    s2 = re.sub(r"\s+", " ", s2).strip(" .")
    return s2.strip() or None


# ----------- Fallback extractor for parenthesized person names -----------
def extract_last_parenthesized_text(s: str) -> Optional[str]:
    """Return the last parenthesized chunk as a name-like string.

    Useful when speaker_raw is a role title like:
      'The Minister for ... (Assoc Prof Dr Yaacob Ibrahim)'
    where the parentheses may not be captured by stricter patterns.
    """
    if not s:
        return None
    parts = re.findall(r"\(([^()]*)\)", str(s))
    if not parts:
        return None
    last = parts[-1].strip().strip(".")
    # Must look name-like (at least 2 alphabetic tokens)
    if len(re.findall(r"[A-Za-z]+", last)) < 2:
        return None
    # Strip leading honorific tokens if present
    last = re.sub(r"^(?:(%s)\s+)+" % HONORIFICS_RE, "", last, flags=re.I).strip()
    last = re.sub(r"\s+", " ", last).strip(" .")
    return last or None


# ----------- Name cleaning and fuzzy matching helpers -----------
def clean_mp_name_from_attendance(raw: str) -> Optional[str]:
    """Return the person's name (no honorific, no constituency, no portfolios).

    Examples:
      - 'Mr Chan Chun Sing (Tanjong Pagar), Coordinating Minister ...' -> 'Chan Chun Sing'
      - 'Miss Rachel Ong (West Coast).' -> 'Rachel Ong'
      - 'Mr SPEAKER (Mr Seah Kian Peng (Marine Parade)).' -> 'Seah Kian Peng'
    """
    if not raw:
        return None
    s = str(raw).strip().rstrip(".")

    # Special case: 'Mr SPEAKER (Mr Seah Kian Peng (Marine Parade)).'
    # IMPORTANT: do NOT trigger for 'Deputy Speaker' attendance lines.
    u = s.upper()
    if "DEPUTY SPEAKER" not in u and re.search(r"\bSPEAKER\s*\(", s, flags=re.I):
        sp = extract_person_from_speaker_attendance(s)
        if sp:
            return sp

    # If the label contains a person's name in parentheses (e.g. role titles in speech list), extract it
    # Examples: 'The Minister for Foreign Affairs (Dr Vivian Balakrishnan)'
    if re.search(r"\((%s)\s+[^)]+\)" % HONORIFICS_RE, s, flags=re.I):
        person = extract_person_from_name(s)
        if person:
            return person

    # Remove everything after the first comma (portfolios, roles)
    s = s.split(",", 1)[0].strip()

    # Remove trailing constituency parentheses
    s = re.sub(r"\s*\([^)]*\)\s*$", "", s).strip(" .")

    # Remove one or more leading honorific tokens (e.g. 'Assoc Prof Dr', 'Dr', etc.)
    s = re.sub(r"^(?:(%s)\s+)+" % HONORIFICS_RE, "", s, flags=re.I).strip()

    # Remove any lingering all-caps SPEAKER tokens (rare)
    s = re.sub(r"\bSPEAKER\b", "", s, flags=re.I).strip()
    s = re.sub(r"\s+", " ", s).strip()

    return s or None


def norm_for_match(s: str) -> str:
    if not s:
        return ""
    x = str(s)
    x = x.replace("\u00a0", " ")
    x = re.sub(r"\([^)]*\)", " ", x)  # drop parentheses chunks
    x = x.split(",", 1)[0]
    x = re.sub(r"^(%s)\s+" % HONORIFICS_RE, "", x, flags=re.I)
    x = re.sub(r"\b(MINISTER|PRIME|DEPUTY|PARLIAMENTARY|SECRETARY|SPEAKER)\b", " ", x, flags=re.I)
    x = re.sub(r"[^A-Za-z\s]", " ", x)
    x = re.sub(r"\s+", " ", x).strip().upper()
    return x



def best_fuzzy_match(query: str, choices: List[str]) -> Tuple[Optional[str], float]:
    """Return (best_choice, score) using difflib; score in [0,1]."""
    from difflib import SequenceMatcher

    q = norm_for_match(query)
    if not q:
        return None, 0.0

    best = None
    best_score = 0.0
    for c in choices:
        cs = norm_for_match(c)
        if not cs:
            continue
        sc = SequenceMatcher(None, q, cs).ratio()
        if sc > best_score:
            best_score = sc
            best = c
    return best, best_score


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


# -------------- Parliament No inference helper --------------
def infer_parliament_no_from_metadata(data: dict) -> Optional[int]:
    """Infer Singapore Parliament number from Hansard JSON metadata.

    NOTE: The API uses a misspelled key: 'parlimentNO'.
    """
    md = (data or {}).get("metadata") or {}
    val = md.get("parlimentNO")
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None

def fetch_hansard_json(sitting_ddmmyyyy: str) -> dict:
    url = f"{BASE_URL}?sittingDate={sitting_ddmmyyyy}"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.json()

def ddmmyyyy_from_date(d: date) -> str:
    return d.strftime("%d-%m-%Y")

def require_env():
    if SKIP_DB:
        return
    missing = []
    if not SUPABASE_URL:
        missing.append("SUPABASE_URL")
    if not SUPABASE_SERVICE_ROLE_KEY:
        missing.append("SUPABASE_SERVICE_ROLE_KEY")
    if missing:
        raise RuntimeError("Missing required env vars: " + ", ".join(missing))

def supabase_client() -> Client:
    require_env()
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

def get_latest_sitting(sb: Client) -> Optional[date]:
    resp = sb.table("hansard_sittings").select("sitting_date").order("sitting_date", desc=True).limit(1).execute()
    if resp.data:
        return datetime.fromisoformat(resp.data[0]["sitting_date"]).date()
    return None

def chunk_records(records: List[dict], n: int):
    for i in range(0, len(records), n):
        yield records[i:i+n]

def upsert_all(sb: Client, df_att: pd.DataFrame, df_ptba: pd.DataFrame, df_speech: pd.DataFrame, sitting_iso: str, source_url: str):
    """Upsert parsed data into Supabase.

    Postgres raises `ON CONFLICT DO UPDATE command cannot affect row a second time`
    when a *single upsert statement* contains multiple rows with the same conflict key.
    This usually means our parsed payload contains duplicates for the table's PK.

    We therefore:
      1) normalize PK fields (strip whitespace; stable string conversion)
      2) drop duplicates on the real PK
      3) upsert in batches with explicit on_conflict targets
    """

    # Attendance PK: (sitting_date, mp_name_raw)
    df_att_u = df_att
    if df_att_u is not None and not df_att_u.empty and {"sitting_date", "mp_name_raw"}.issubset(df_att_u.columns):
        df_att_u = normalize_df_pk_cols(df_att_u, ["sitting_date", "mp_name_raw"])
        if DEBUG:
            dup_mask = df_att_u.duplicated(subset=["sitting_date", "mp_name_raw"], keep=False)
            if dup_mask.any():
                print("[DEBUG] Duplicate attendance PK rows BEFORE de-dup:")
                print(df_att_u.loc[dup_mask, ["sitting_date", "mp_name_raw"]].value_counts().head(50))
        df_att_u = df_att_u.drop_duplicates(subset=["sitting_date", "mp_name_raw"], keep="first")

    # PTBA PK: (sitting_date, mp_name_raw, ptba_from, ptba_to)
    df_ptba_u = df_ptba
    if df_ptba_u is not None and not df_ptba_u.empty and {"sitting_date", "mp_name_raw", "ptba_from", "ptba_to"}.issubset(df_ptba_u.columns):
        df_ptba_u = normalize_df_pk_cols(df_ptba_u, ["sitting_date", "mp_name_raw", "ptba_from", "ptba_to"])
        if DEBUG:
            dup_mask = df_ptba_u.duplicated(subset=["sitting_date", "mp_name_raw", "ptba_from", "ptba_to"], keep=False)
            if dup_mask.any():
                print("[DEBUG] Duplicate PTBA PK rows BEFORE de-dup:")
                print(df_ptba_u.loc[dup_mask, ["sitting_date", "mp_name_raw", "ptba_from", "ptba_to"]].value_counts().head(50))
        df_ptba_u = df_ptba_u.drop_duplicates(subset=["sitting_date", "mp_name_raw", "ptba_from", "ptba_to"], keep="first")

    # Speeches PK: (sitting_date, row_num)
    df_speech_u = df_speech
    if df_speech_u is not None and not df_speech_u.empty and {"sitting_date", "row_num"}.issubset(df_speech_u.columns):
        df_speech_u = normalize_df_pk_cols(df_speech_u, ["sitting_date"])
        if DEBUG:
            dup_mask = df_speech_u.duplicated(subset=["sitting_date", "row_num"], keep=False)
            if dup_mask.any():
                print("[DEBUG] Duplicate speeches PK rows BEFORE de-dup:")
                print(df_speech_u.loc[dup_mask, ["sitting_date", "row_num"]].value_counts().head(50))
        df_speech_u = df_speech_u.drop_duplicates(subset=["sitting_date", "row_num"], keep="first")

    # Upsert batches with explicit conflict targets
    try:
        for batch in chunk_records(df_att_u.to_dict("records"), 500):
            sb.table("hansard_attendance").upsert(batch, on_conflict="sitting_date,mp_name_raw").execute()
    except Exception as e:
        raise RuntimeError(f"Upsert failed for hansard_attendance ({sitting_iso}): {e}")

    try:
        for batch in chunk_records(df_ptba_u.to_dict("records"), 500):
            sb.table("hansard_ptba").upsert(batch, on_conflict="sitting_date,mp_name_raw,ptba_from,ptba_to").execute()
    except Exception as e:
        raise RuntimeError(f"Upsert failed for hansard_ptba ({sitting_iso}): {e}")

    try:
        for batch in chunk_records(df_speech_u.to_dict("records"), 300):
            sb.table("hansard_speeches").upsert(batch, on_conflict="sitting_date,row_num").execute()
    except Exception as e:
        raise RuntimeError(f"Upsert failed for hansard_speeches ({sitting_iso}): {e}")

    try:
        sb.table("hansard_sittings").upsert(
            {"sitting_date": sitting_iso, "source_url": source_url},
            on_conflict="sitting_date",
        ).execute()
    except Exception as e:
        raise RuntimeError(f"Upsert failed for hansard_sittings ({sitting_iso}): {e}")



def parse_one_sitting(data: dict) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, str, Optional[int], date]:
    """Parse one Hansard JSON payload into attendance/PTBA/speech DataFrames."""
    sitting_dt = parse_sitting_date(data["metadata"]["sittingDate"])
    sitting_date = sitting_dt.strftime("%Y-%m-%d")
    default_year = extract_year((data.get("metadata") or {}).get("ptbaFrom"), sitting_dt.year)
    parliament_no = infer_parliament_no_from_metadata(data)
    source_url = f"{BASE_URL}?sittingDate={data['metadata']['sittingDate']}"

    # Map chair titles to actual person names using attendance list
    speaker_person: Optional[str] = None
    deputy_display: Dict[str, str] = {}
    deputy_by_honorific: Dict[str, str] = {}

    for item in data.get("attendanceList", []):
        raw_att = (item.get("mpName") or "").strip()
        u_att = raw_att.upper()
        if "SPEAKER" in u_att and "DEPUTY" not in u_att and speaker_person is None:
            speaker_person = extract_person_from_speaker_attendance(raw_att)
        if "DEPUTY SPEAKER" in u_att:
            k = name_key(raw_att)
            disp = extract_person_from_name(raw_att)
            if k and disp:
                deputy_display[k] = disp
            m = re.match(r"^(Mr|Ms|Mdm|Madam|Miss|Dr)\b", raw_att.strip(), flags=re.I)
            if m and disp:
                deputy_by_honorific[m.group(1).upper()] = disp

    # Build attendance name mappings for cleaning + fuzzy matching
    attendance_choices_clean: List[str] = []
    _seen_clean: set = set()
    for item in data.get("attendanceList", []):
        raw_att = (item.get("mpName") or "").strip()
        cleaned = clean_mp_name_from_attendance(raw_att)
        if cleaned and cleaned not in _seen_clean:
            attendance_choices_clean.append(cleaned)
            _seen_clean.add(cleaned)

    attendance_norm_to_clean: Dict[str, str] = {}
    for nm in attendance_choices_clean:
        nn = norm_for_match(nm)
        if nn and nn not in attendance_norm_to_clean:
            attendance_norm_to_clean[nn] = nm

    def canonicalize_to_attendance(name: Optional[str]) -> Optional[str]:
        if not name:
            return None
        nn = norm_for_match(name)
        return attendance_norm_to_clean.get(nn, name)

    def chair_display_name(chair_label: str) -> str:
        if not chair_label:
            return ""
        role = chair_role(chair_label)
        explicit = extract_person_from_name(chair_label)
        if explicit:
            return explicit
        if role == "speaker" and speaker_person:
            return speaker_person
        if role == "deputy_speaker":
            lab = chair_label.strip()
            m = re.match(r"^(Mr|Ms|Mdm|Madam|Miss|Dr)\b", lab, flags=re.I)
            if m:
                h = m.group(1).upper()
                if h in deputy_by_honorific:
                    return deputy_by_honorific[h]
                if h in {"MDM", "MADAM", "MS", "MISS"}:
                    for hh in ["MDM", "MADAM", "MS", "MISS"]:
                        if hh in deputy_by_honorific:
                            return deputy_by_honorific[hh]
                if "MR" in deputy_by_honorific:
                    return deputy_by_honorific["MR"]
            if len(deputy_display) == 1:
                return list(deputy_display.values())[0]
        return chair_label

    # -------- PTBA --------
    ptba_rows: List[dict] = []
    current_mp: Optional[str] = None
    for rec in data.get("ptbaList", []):
        mp = rec.get("mpName")
        if mp is not None and str(mp).strip():
            current_mp = str(mp).strip()
        if current_mp is None:
            continue
        ptba_rows.append({
            "sitting_date": sitting_date,
            "parliament_no": parliament_no,
            "mp_name_raw": current_mp,
            "mp_name_cleaned": clean_mp_name_from_attendance(current_mp),
            "ptba_from": rec.get("from"),
            "ptba_to": rec.get("to"),
            "dim_overlaps_sitting_date": 1 if ptba_overlaps_sitting(rec, sitting_dt, default_year) else 0,
        })

    df_ptba_all = pd.DataFrame(ptba_rows)
    if not df_ptba_all.empty:
        df_ptba = df_ptba_all[df_ptba_all["dim_overlaps_sitting_date"] == 1][[
            "parliament_no","sitting_date","mp_name_raw","mp_name_cleaned","ptba_from","ptba_to"
        ]].reset_index(drop=True)

        # De-dup on the actual table PK so CSVs (and any non-upsert insertion path) stay safe.
        # PK: (sitting_date, mp_name_raw, ptba_from, ptba_to)
        df_ptba = normalize_df_pk_cols(df_ptba, ["sitting_date", "mp_name_raw", "ptba_from", "ptba_to"])
        before_n = len(df_ptba)
        df_ptba = df_ptba.drop_duplicates(
            subset=["sitting_date","mp_name_raw","ptba_from","ptba_to"],
            keep="first",
        ).reset_index(drop=True)
        after_n = len(df_ptba)
        if DEBUG and before_n != after_n:
            print(f"[DEBUG] PTBA de-dup removed {before_n - after_n} rows (kept {after_n}).")
    else:
        df_ptba = pd.DataFrame(columns=["parliament_no","sitting_date","mp_name_raw","mp_name_cleaned","ptba_from","ptba_to"])

    # -------- Attendance --------
    att_rows: List[dict] = []
    for item in data.get("attendanceList", []):
        raw = (item.get("mpName") or "").strip()
        if not raw:
            # Skip blank/separator rows to avoid creating duplicate keys
            continue
        u = raw.upper()
        present = 1 if item.get("attendance") else 0

        cleaned = clean_mp_name_from_attendance(raw)

        att_rows.append({
            "sitting_date": sitting_date,
            "parliament_no": parliament_no,
            "mp_name_raw": raw,
            "mp_name_cleaned": cleaned,
            "dim_is_speaker": 1 if ("SPEAKER" in u and "DEPUTY" not in u) else 0,
            "dim_is_deputy_speaker": 1 if ("DEPUTY SPEAKER" in u) else 0,
            "dim_is_present": present,
        })

    df_att = pd.DataFrame(att_rows)[[
        "parliament_no","sitting_date","mp_name_raw","mp_name_cleaned","dim_is_speaker","dim_is_deputy_speaker","dim_is_present"
    ]]

    # -------- Speeches --------
    speech_rows: List[dict] = []
    row_num = 0
    # Start with metadata speaker if provided
    current_chair = (data.get("metadata") or {}).get("speaker") or "Mr Speaker"

    wa_skipped = 0

    def append_continuation(text: str):
        if not speech_rows:
            return
        text2 = strip_trailing_chair_call(text).strip()
        if not text2:
            return
        speech_rows[-1]["speech_details"] = (speech_rows[-1]["speech_details"] + "\n\n" + text2).strip()
        speech_rows[-1]["word_count"] = word_count(speech_rows[-1]["speech_details"])

    for sec in data.get("takesSectionVOList", []):
        # Exclude Question-Time written answers listings (not actually spoken in the chamber)
        sec_type_raw = (sec.get("sectionType") or "")
        # Normalize aggressively: strip, uppercase, then keep only letters (handles hidden chars / BOM / NBSP)
        sec_type = re.sub(r"[^A-Z]", "", sec_type_raw.strip().upper())
        sec_title = (sec.get("title") or "").strip().upper()
        html = sec.get("content", "") or ""

        # 'WA' (Written Answers) and 'WANA' (Written Answers Not Answered) are not spoken in the chamber.
        # Use prefix match to catch future variants like 'WA*'.
        if sec_type.startswith("WA"):
            wa_skipped += 1
            continue

        if not html:
            continue
        soup = BeautifulSoup(html, "html.parser")

        for tag in soup.find_all(["p","h6","h5","h4","h3","h2","h1"]):
            text = tag.get_text(" ", strip=True)
            if not text:
                continue

            cm = extract_chair_marker(text)
            if cm:
                current_chair = cm
                continue

            if tag.name == "h6" and re.match(r"^\d{1,2}\.\d{2}\s*(am|pm)$", text, flags=re.I):
                continue
            if tag.name != "p":
                continue

            strong = tag.find("strong")
            if strong:
                full = tag.get_text(" ", strip=True)

                # Speaker labels sometimes have split <strong> tags (e.g. '<strong>Mr </strong><strong>Ong Ye Kung</strong>:').
                # Use the visible text up to the first ':' as the speaker label when available.
                if ":" in full:
                    speaker_raw = full.split(":", 1)[0].strip()
                else:
                    speaker_raw = strong.get_text(" ", strip=True)

                speaker_raw = (speaker_raw or "").rstrip(":").strip()

                if not speaker_raw:
                    append_continuation(full)
                    continue

                inferred = infer_chair_from_speaker_label(speaker_raw)
                if inferred:
                    inferred_explicit = extract_person_from_name(inferred)
                    current_explicit = extract_person_from_name(current_chair)
                    if inferred_explicit:
                        current_chair = inferred
                    elif current_explicit:
                        pass
                    else:
                        current_chair = inferred

                # Prefer splitting speech at first colon for robustness
                if ":" in full:
                    speech = full.split(":", 1)[1].strip()
                else:
                    speech = re.sub(r"^\s*%s\s*" % re.escape(speaker_raw), "", full).lstrip(" :").strip()

                speech = strip_trailing_chair_call(speech).strip()
                if not speech:
                    continue

                if is_question_paper_item(speaker_raw, speech):
                    continue

                role_as_speaker = chair_role(speaker_raw)

                # Drop procedural Chair call-outs (e.g. 'Mr Patrick Tay.')
                if role_as_speaker is not None and is_chair_call_to_member(speech):
                    continue

                if role_as_speaker is not None:
                    # Chair speaking: map to whoever is currently in the Chair
                    mp_fuzzy = canonicalize_to_attendance(chair_display_name(current_chair))
                else:
                    # Non-Chair: speaker_raw may be a role title with the person in parentheses.
                    # Prefer extracting the actual person name for matching.
                    extracted_person = extract_person_from_name(speaker_raw) or extract_last_parenthesized_text(speaker_raw)
                    q_clean = extracted_person or clean_mp_name_from_attendance(speaker_raw) or speaker_raw

                    q_norm = norm_for_match(q_clean)
                    if q_norm and q_norm in attendance_norm_to_clean:
                        mp_fuzzy = canonicalize_to_attendance(attendance_norm_to_clean[q_norm])
                    else:
                        best, score = best_fuzzy_match(q_clean, attendance_choices_clean)
                        # Slightly looser threshold to reduce false negatives for older Hansards
                        mp_fuzzy = canonicalize_to_attendance(best) if score >= 0.75 else None

                row_num += 1
                speech_rows.append({
                    "sitting_date": sitting_date,
                    "parliament_no": parliament_no,
                    "row_num": row_num,
                    "mp_name_raw": speaker_raw,
                    "mp_name_fuzzy_matched": mp_fuzzy,
                    "speech_details": speech,
                    "word_count": word_count(speech),
                    "dim_speaker": chair_role(current_chair),
                    "chair_name_raw": chair_display_name(current_chair),
                })
            else:
                append_continuation(text)

    if speech_rows:
        df_speech = pd.DataFrame(speech_rows)[[
            "parliament_no","sitting_date","row_num","mp_name_raw","mp_name_fuzzy_matched",
            "speech_details","word_count","dim_speaker","chair_name_raw"
        ]]
    else:
        df_speech = pd.DataFrame(columns=[
            "parliament_no","sitting_date","row_num","mp_name_raw","mp_name_fuzzy_matched",
            "speech_details","word_count","dim_speaker","chair_name_raw"
        ])

    if DEBUG:
        print(f"parse_one_sitting: skipped {wa_skipped} WA/WANA sections")

    return df_att, df_ptba, df_speech, source_url, parliament_no, sitting_dt


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

    print(f"Ingest range: {start_dt.isoformat()} -> {end_dt.isoformat()} (ver={SCRIPT_VERSION}, RUN_DATE={RUN_DATE or 'auto'}, DEBUG={DEBUG}, SAVE_JSON={SAVE_JSON}, SKIP_DB={SKIP_DB})")

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
                upsert_all(sb, df_att, df_ptba, df_speech, d.isoformat(), source_url)
                print(f"Inserted {ddmmyyyy}: att={len(df_att)} ptba={len(df_ptba)} speech={len(df_speech)}")
            except Exception as e:
                print(f"DB insert failed for {ddmmyyyy}: {e}")

        d += timedelta(days=1)


if __name__ == "__main__":
    ingest()