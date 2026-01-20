import re
from datetime import date
from typing import Dict, List, Optional, Tuple

import pandas as pd
from bs4 import BeautifulSoup

from .config import BASE_URL, DEBUG
from .names import (
    HONORIFICS_RE,
    best_fuzzy_match,
    chair_role,
    clean_mp_name_from_attendance,
    extract_chair_marker,
    extract_last_parenthesized_text,
    extract_person_from_name,
    extract_person_from_speaker_attendance,
    infer_chair_from_speaker_label,
    is_chair_call_to_member,
    is_question_paper_item,
    name_key,
    norm_for_match,
    strip_trailing_chair_call,
)
from .utils import extract_year, parse_day_month, parse_sitting_date, word_count


def ptba_overlaps_sitting(rec: dict, sitting_dt: date, default_year: int) -> bool:
    start = parse_day_month(rec.get("from"), default_year)
    end = parse_day_month(rec.get("to"), default_year)
    if start is None or end is None:
        return False
    if end < start:  # cross-year edge case
        end = date(default_year + 1, end.month, end.day)
    return start <= sitting_dt <= end


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
        from .utils import normalize_df_pk_cols
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

    def append_continuation(text: str):
        if not speech_rows:
            return
        text2 = strip_trailing_chair_call(text).strip()
        if not text2:
            return
        speech_rows[-1]["speech_details"] = (speech_rows[-1]["speech_details"] + "\n\n" + text2).strip()
        speech_rows[-1]["word_count"] = word_count(speech_rows[-1]["speech_details"])

    def strip_question_number(text: str) -> str:
        if not text:
            return text
        # Remove leading question numbers like "1 Mr ..." or "2 To ask ...", even mid-sentence.
        pat = r"(^|\s)\d{1,3}\s+(?=(?:%s)\b|To ask\b)" % HONORIFICS_RE
        cleaned = re.sub(pat, " ", str(text), flags=re.I)
        return re.sub(r"\s+", " ", cleaned).strip()

    for sec in data.get("takesSectionVOList", []):
        sec_type_raw = (sec.get("sectionType") or "")
        # Normalize aggressively: strip, uppercase, then keep only letters (handles hidden chars / BOM / NBSP)
        sec_type = re.sub(r"[^A-Z]", "", sec_type_raw.strip().upper())
        discussion_title = (sec.get("title") or "").strip() or None
        is_written_section = sec_type in {"WA", "WANA"}
        html = sec.get("content", "") or ""

        dim_is_written_answer_to_questions = 1 if sec_type == "WA" else 0
        dim_is_written_answer_not_answered = 1 if sec_type == "WANA" else 0

        if not html:
            continue
        soup = BeautifulSoup(html, "html.parser")

        for tag in soup.find_all(["p","h6","h5","h4","h3","h2","h1"]):
            raw_text = tag.get_text(" ", strip=True)
            text = strip_question_number(raw_text)
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
                full_raw = raw_text
                full = text

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

                # Non-spoken Question Time question listings like:
                #   '13 Mr X asked the Minister ...'
                # We want to keep these rows for metadata, but mark them as non-oral-speech.
                if ":" not in full and is_question_paper_item(speaker_raw, full_raw):
                    out_speaker_raw = speaker_raw
                    out_mp_fuzzy = canonicalize_to_attendance(clean_mp_name_from_attendance(speaker_raw) or speaker_raw)
                    out_dim_speaker = None if is_written_section else chair_role(current_chair)
                    out_chair_name = None if is_written_section else chair_display_name(current_chair)
                    row_num += 1
                    speech_rows.append({
                        "sitting_date": sitting_date,
                        "parliament_no": parliament_no,
                        "row_num": row_num,
                        "discussion_title": discussion_title,
                        "section_type": sec_type,
                        "mp_name_raw": out_speaker_raw,
                        "mp_name_fuzzy_matched": out_mp_fuzzy,
                        "speech_details": full,
                        "word_count": word_count(full),
                        "dim_speaker": out_dim_speaker,
                        "chair_name_raw": out_chair_name,
                        "dim_is_question_for_oral_answer": 1 if sec_type == "OA" else 0,
                        "dim_is_oral_speech": 0,
                        "dim_is_written_answer_not_answered": dim_is_written_answer_not_answered,
                        "dim_is_written_answer_to_questions": dim_is_written_answer_to_questions,
                    })
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
                out_dim_speaker = None if is_written_section else chair_role(current_chair)
                out_chair_name = None if is_written_section else chair_display_name(current_chair)

                row_num += 1
                dim_is_oral_speech = 0 if (dim_is_written_answer_to_questions or dim_is_written_answer_not_answered) else 1
                speech_rows.append({
                    "sitting_date": sitting_date,
                    "parliament_no": parliament_no,
                    "row_num": row_num,
                    "discussion_title": discussion_title,
                    "section_type": sec_type,
                    "mp_name_raw": speaker_raw,
                    "mp_name_fuzzy_matched": mp_fuzzy,
                    "speech_details": speech,
                    "word_count": word_count(speech),
                    "dim_speaker": out_dim_speaker,
                    "chair_name_raw": out_chair_name,
                    "dim_is_question_for_oral_answer": 0,
                    "dim_is_oral_speech": dim_is_oral_speech,
                    "dim_is_written_answer_not_answered": dim_is_written_answer_not_answered,
                    "dim_is_written_answer_to_questions": dim_is_written_answer_to_questions,
                })
            else:
                append_continuation(text)

    if speech_rows:
        df_speech = pd.DataFrame(speech_rows)[[
            "parliament_no","sitting_date","row_num","discussion_title","section_type",
            "mp_name_raw","mp_name_fuzzy_matched","speech_details","word_count",
            "dim_speaker","chair_name_raw",
            "dim_is_question_for_oral_answer","dim_is_oral_speech",
            "dim_is_written_answer_not_answered","dim_is_written_answer_to_questions",
        ]]
    else:
        df_speech = pd.DataFrame(columns=[
            "parliament_no","sitting_date","row_num","discussion_title","section_type",
            "mp_name_raw","mp_name_fuzzy_matched","speech_details","word_count",
            "dim_speaker","chair_name_raw",
            "dim_is_question_for_oral_answer","dim_is_oral_speech",
            "dim_is_written_answer_not_answered","dim_is_written_answer_to_questions",
        ])

    return df_att, df_ptba, df_speech, source_url, parliament_no, sitting_dt
