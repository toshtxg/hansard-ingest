import os
from dotenv import load_dotenv

load_dotenv()

# ---------------------------
# Version stamp so you can confirm you are running the file you just edited.
# Bump this when you make changes.
SCRIPT_VERSION = "2025-12-29.1"

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

# ---- AI summary (optional) ----
AI_ENABLED = env_bool("AI_ENABLED", False)
AI_PROVIDER = env_str("AI_PROVIDER", "openai").strip().lower()
OPENAI_API_KEY = env_str("OPENAI_API_KEY", "")
OPENAI_MODEL = env_str("OPENAI_MODEL", "gpt-4o-mini")
AI_MAX_CHARS = env_int("AI_MAX_CHARS", 12000)
AI_DRY_RUN = env_bool("AI_DRY_RUN", False)  # if true, generate summary but don't write to DB
