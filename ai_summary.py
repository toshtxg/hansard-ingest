from datetime import datetime
from typing import Optional

import pandas as pd
import requests

from .config import (
    AI_ENABLED,
    AI_MAX_CHARS,
    AI_PROVIDER,
    OPENAI_API_KEY,
    OPENAI_MODEL,
)


def build_ai_summary_prompt(sitting_date_iso: str, speech_df: pd.DataFrame) -> str:
    """Build a prompt from raw speeches. Keep it deterministic and compact."""
    if speech_df is None or speech_df.empty:
        return (
            f"Sitting date: {sitting_date_iso}.\n"
            "No speech content was parsed for this sitting.\n\n"
            "Write a 3-sentence summary:\n"
            "1) What topics were talked about\n"
            "2) How it impacts Singapore\n"
            "3) Why we should care\n"
        )

    # Keep only substantive fields; concatenate in order
    parts = []
    for _, r in speech_df.sort_values(["row_num"]).iterrows():
        speaker = str(r.get("mp_name_fuzzy_matched") or r.get("mp_name_raw") or "").strip()
        speech = str(r.get("speech_details") or "").strip()
        if not speech:
            continue
        # Keep it readable but compact
        parts.append(f"{speaker}: {speech}")

    raw_text = "\n".join(parts)

    # Hard cap to avoid runaway prompt sizes
    if AI_MAX_CHARS and AI_MAX_CHARS > 0 and len(raw_text) > AI_MAX_CHARS:
        raw_text = raw_text[:AI_MAX_CHARS] + "\n...[truncated]"

    return (
        "You are summarizing a Singapore Parliament sitting transcript.\n"
        "Write exactly 3 sentences, no bullet points.\n"
        "Sentence 1: what topics were discussed.\n"
        "Sentence 2: how it impacts Singapore.\n"
        "Sentence 3: why the public should care.\n"
        "Keep it neutral and factual; do not invent details. No need to mention which date it is for.\n"
        "It should also sound natural and not robotic like how the leading words are the same for all parses\n\n"
        f"Sitting date: {sitting_date_iso}\n\n"
        "Transcript (may be truncated):\n"
        f"{raw_text}"
    )


def openai_summarize(prompt: str) -> str:
    if not OPENAI_API_KEY:
        raise RuntimeError("AI_ENABLED=true but OPENAI_API_KEY is missing")

    # Use Chat Completions-compatible request via HTTP (no extra deps)
    url = "https://api.openai.com/v1/chat/completions"
    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": "You are a careful assistant."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.5,
    }

    r = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=60,
    )

    if not r.ok:
        raise RuntimeError(f"OpenAI API error {r.status_code}: {r.text}")

    data = r.json()
    try:
        return data["choices"][0]["message"]["content"].strip()
    except Exception:
        raise RuntimeError(f"Unexpected OpenAI response: {data}")


def generate_ai_summary(sitting_date_iso: str, speech_df: pd.DataFrame) -> Optional[dict]:
    """Return a row dict suitable for upsert into hansard_ai_summaries."""
    if not AI_ENABLED:
        return None
    if AI_PROVIDER != "openai":
        raise RuntimeError(f"Unsupported AI_PROVIDER: {AI_PROVIDER}")

    prompt = build_ai_summary_prompt(sitting_date_iso, speech_df)
    summary = openai_summarize(prompt)

    return {
        "sitting_date": sitting_date_iso,
        "provider": AI_PROVIDER,
        "model": OPENAI_MODEL,
        "summary_3_sentences": summary,
        "updated_at": datetime.utcnow().isoformat(),
    }
