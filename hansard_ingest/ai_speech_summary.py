import json
import random
import time
from datetime import datetime
from typing import Any, Dict, Optional

import requests

from .config import AI_ENABLED, AI_PROVIDER, OPENAI_API_KEY, OPENAI_MODEL
from .utils import normalize_ws


SUMMARY_VERSION = "v3"
MIN_TEXT_CHARS = 30

ALLOWED_SEGMENT_TYPES = [
    "question",
    "answer",
    "supplementary_question",
    "supplementary_answer",
    "statement",
    "procedural",
    "other",
]

SYSTEM_PROMPT = (
    "You are extracting structured evidence from Singapore parliamentary speech excerpts. "
    "Each excerpt may be a question, answer, statement, or procedural line. "
    "Output valid JSON only matching the provided schema. "
    "Do not infer beyond what is explicitly stated. "
    "Keep language neutral and literal."
)

GUIDANCE_PROMPT = (
    "Guidance:\n"
    "- one_liner must be specific and literal; avoid generic phrasing like 'supports the Bill' without details.\n"
    "- Do not name people unless the name appears in the text; do not infer names from metadata.\n"
    "- Ignore salutations and formalities.\n"
    "- If the text is procedural (calls next speaker, asks for clarification, order/adjournment), "
    "set segment_type=procedural and use a short literal one_liner.\n"
)

JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "segment_type": {"type": "string", "enum": ALLOWED_SEGMENT_TYPES},
        "one_liner": {"type": "string"},
        "themes": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 6,
        },
        "key_claims": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 5,
        },
    },
    "required": ["segment_type", "one_liner", "themes", "key_claims"],
}


def needs_summary(one_liner: Optional[str], summary_version: Optional[str]) -> bool:
    return not one_liner or summary_version != SUMMARY_VERSION


def _trim_words(text: str, max_words: int) -> str:
    words = str(text or "").strip().split()
    if len(words) <= max_words:
        return " ".join(words)
    return " ".join(words[:max_words])


def _short_summary_from_text(text: str) -> Dict[str, Any]:
    cleaned = normalize_ws(text or "")
    if cleaned:
        one_liner = _trim_words(cleaned, 30)
        segment_type = "procedural"
    else:
        one_liner = "Procedural line."
        segment_type = "other"
    return {
        "segment_type": segment_type,
        "one_liner": one_liner,
        "themes": [],
        "key_claims": [],
    }


def build_user_content(text: str, metadata: Dict[str, str]) -> str:
    lines = []
    lines.append(GUIDANCE_PROMPT.strip())
    if metadata:
        lines.append("Metadata:")
        speaker_name = (metadata.get("speaker_name") or "").strip()
        role = (metadata.get("role") or "").strip()
        sitting_date = (metadata.get("sitting_date") or "").strip()
        if speaker_name:
            lines.append(f"- speaker_name: {speaker_name}")
        if role:
            lines.append(f"- role: {role}")
        if sitting_date:
            lines.append(f"- sitting_date: {sitting_date}")
    lines.append("Text:")
    lines.append(text or "")
    return "\n".join(lines).strip()


def build_fix_prompt(raw_output: str) -> str:
    return (
        "Fix to schema. Output valid JSON only matching the provided schema.\n\n"
        f"Schema:\n{json.dumps(JSON_SCHEMA, ensure_ascii=True)}\n\n"
        f"Invalid output:\n{raw_output}\n"
    )


def infer_role_from_label(label: str) -> str:
    u = normalize_ws(label or "").upper()
    if not u:
        return ""
    if "DEPUTY SPEAKER" in u:
        return "chair"
    if "SPEAKER" in u:
        return "chair"
    if "CHAIRMAN" in u or "CHAIR" in u:
        return "chair"
    return ""


def short_circuit_summary(text: str, metadata: Dict[str, str]) -> Optional[Dict[str, Any]]:
    cleaned = normalize_ws(text or "")
    if (metadata or {}).get("role") == "chair" and len(cleaned) < 180:
        return _short_summary_from_text(cleaned)
    if len(cleaned) < MIN_TEXT_CHARS:
        return _short_summary_from_text(cleaned)
    return None


def extract_output_text(data: Dict[str, Any]) -> str:
    if isinstance(data.get("output_text"), str) and data["output_text"].strip():
        return data["output_text"].strip()
    outputs = data.get("output") or []
    for item in outputs:
        content = item.get("content") or []
        for part in content:
            if part.get("type") in {"output_text", "text"} and part.get("text"):
                return str(part["text"]).strip()
    raise RuntimeError(f"Unexpected OpenAI response: {data}")


def _post_with_backoff(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not OPENAI_API_KEY:
        raise RuntimeError("AI_ENABLED=true but OPENAI_API_KEY is missing")
    if AI_PROVIDER != "openai":
        raise RuntimeError(f"Unsupported AI_PROVIDER: {AI_PROVIDER}")

    url = "https://api.openai.com/v1/responses"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=60)
        except requests.RequestException as e:
            if attempt == max_attempts - 1:
                raise RuntimeError(f"OpenAI request failed: {e}")
            time.sleep(0.5 * (2 ** attempt) + random.random() * 0.2)
            continue

        if r.status_code in {429, 500, 502, 503, 504}:
            if attempt == max_attempts - 1:
                raise RuntimeError(f"OpenAI API error {r.status_code}: {r.text}")
            time.sleep(0.5 * (2 ** attempt) + random.random() * 0.2)
            continue

        if not r.ok:
            raise RuntimeError(f"OpenAI API error {r.status_code}: {r.text}")

        return r.json()

    raise RuntimeError("OpenAI request failed after retries")


def build_responses_payload(user_content: str) -> Dict[str, Any]:
    return {
        "model": OPENAI_MODEL,
        "input": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.2,
        "text": {
            "format": {
                "type": "json_schema",
                "name": "hansard_speech_summary",
                "schema": JSON_SCHEMA,
                "strict": True,
            }
        },
    }


def _call_responses_api(user_content: str) -> str:
    payload = build_responses_payload(user_content)
    data = _post_with_backoff(payload)
    return extract_output_text(data)


def _validate_payload(obj: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(obj, dict):
        return None

    for k in ("segment_type", "one_liner", "themes", "key_claims"):
        if k not in obj:
            return None

    segment_type = obj.get("segment_type")
    if segment_type not in ALLOWED_SEGMENT_TYPES:
        return None

    one_liner = obj.get("one_liner")
    if not isinstance(one_liner, str):
        return None
    one_liner = _trim_words(one_liner.strip(), 30)
    if not one_liner:
        one_liner = "Procedural line."

    themes_in = obj.get("themes")
    if not isinstance(themes_in, list):
        return None
    themes = []
    for t in themes_in:
        if not isinstance(t, str):
            continue
        s = t.strip()
        if not s:
            continue
        if len(s.split()) > 4:
            s = " ".join(s.split()[:4])
        themes.append(s)
        if len(themes) >= 6:
            break

    claims_in = obj.get("key_claims")
    if not isinstance(claims_in, list):
        return None
    key_claims = []
    for c in claims_in:
        if not isinstance(c, str):
            continue
        s = c.strip()
        if not s:
            continue
        key_claims.append(s)
        if len(key_claims) >= 5:
            break

    return {
        "segment_type": segment_type,
        "one_liner": one_liner,
        "themes": themes,
        "key_claims": key_claims,
    }


def parse_summary_output(raw_output: str) -> Optional[Dict[str, Any]]:
    if not raw_output or not str(raw_output).strip():
        return None
    try:
        parsed = json.loads(raw_output)
    except json.JSONDecodeError:
        return None
    return _validate_payload(parsed)


def repair_summary_output(raw_output: str, text: str, metadata: Dict[str, str]) -> Optional[Dict[str, Any]]:
    fix_prompt = build_fix_prompt(raw_output)
    retry_user = f"{fix_prompt}\n\n{build_user_content(text, metadata)}"
    raw_retry = _call_responses_api(retry_user)
    return parse_summary_output(raw_retry)


def summarize_row(text: str, metadata: Dict[str, str]) -> Optional[Dict[str, Any]]:
    if not AI_ENABLED:
        return None

    cleaned = normalize_ws(text or "")
    short_circuit = short_circuit_summary(cleaned, metadata or {})
    if short_circuit:
        return short_circuit

    user_content = build_user_content(cleaned, metadata or {})
    raw = _call_responses_api(user_content)
    validated = parse_summary_output(raw)
    if validated:
        return validated

    return repair_summary_output(raw, cleaned, metadata or {})


def build_summary_update(payload: Dict[str, Any]) -> Dict[str, Any]:
    if payload.get("segment_type") == "procedural":
        return {
            "segment_type": payload["segment_type"],
            "one_liner": None,
            "themes": [],
            "key_claims": [],
            "summary_version": SUMMARY_VERSION,
            "summarized_at": datetime.utcnow().isoformat(),
        }
    return {
        "segment_type": payload["segment_type"],
        "one_liner": payload["one_liner"],
        "themes": payload["themes"],
        "key_claims": payload["key_claims"],
        "summary_version": SUMMARY_VERSION,
        "summarized_at": datetime.utcnow().isoformat(),
    }
