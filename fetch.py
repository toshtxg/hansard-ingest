import requests

from .config import BASE_URL


def fetch_hansard_json(sitting_ddmmyyyy: str) -> dict:
    url = f"{BASE_URL}?sittingDate={sitting_ddmmyyyy}"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.json()
