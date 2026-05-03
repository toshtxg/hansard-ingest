"""HTTP fetch for the public Hansard JSON endpoint."""

import requests

from .config import BASE_URL


def fetch_hansard_json(sitting_ddmmyyyy: str) -> dict:
    """Fetch the raw Hansard JSON for a single sitting date.

    The Parliament API expects ``DD-MM-YYYY``. Non-sitting days return an
    empty payload, which the parser handles by emitting empty DataFrames.
    """
    url = f"{BASE_URL}?sittingDate={sitting_ddmmyyyy}"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.json()
