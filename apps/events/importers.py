"""Parses the 'minuto a minuto' (run-of-show) spreadsheets planners already use
into plain dicts, so a view can turn them into EventSession rows.

Kept framework-free (no Django imports) so it can be unit-tested with just openpyxl.
"""
import re
from datetime import datetime, time as dt_time

import openpyxl


def _norm(value):
    return re.sub(r"\s+", " ", str(value or "")).strip().lower()


def _locate_header(ws, required_keywords, max_scan=10):
    best = (None, {})
    for row in ws.iter_rows(min_row=1, max_row=min(max_scan, ws.max_row)):
        cols = {}
        for cell in row:
            val = _norm(cell.value)
            if not val:
                continue
            for kw in required_keywords:
                if kw in val and kw not in cols:
                    cols[kw] = cell.column
        if len(cols) > len(best[1]):
            best = (row[0].row, cols)
    if best[0] is not None and len(best[1]) >= 2:
        return best
    return None, None


_AMPM_RE = re.compile(r"^\s*(\d{1,2}):(\d{2})\s*([AaPp][Mm])\s*$")
_HHMM_RE = re.compile(r"^\s*(\d{1,2}):(\d{2})\s*$")


def _parse_time_text(text):
    text = str(text).strip()
    m = _AMPM_RE.match(text)
    if m:
        hour, minute, ampm = int(m.group(1)), int(m.group(2)), m.group(3).lower()
        if ampm == "pm" and hour != 12:
            hour += 12
        if ampm == "am" and hour == 12:
            hour = 0
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return dt_time(hour, minute)
        return None
    m = _HHMM_RE.match(text)
    if m:
        hour, minute = int(m.group(1)), int(m.group(2))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return dt_time(hour, minute)
    return None


def _cell_time(value):
    if isinstance(value, dt_time):
        return value
    if isinstance(value, datetime):
        return value.time()
    if isinstance(value, str) and value.strip():
        return _parse_time_text(value)
    return None


class ParsedSessionRow:
    def __init__(self, title, notes="", venue_name="", start_time=None, time_is_carried_over=False):
        self.title = title
        self.notes = notes
        self.venue_name = venue_name
        self.start_time = start_time
        self.time_is_carried_over = time_is_carried_over


TITLE_MAX_LEN = 150


def parse_minuto_a_minuto(file_obj):
    """Format: columns 'place', 'hour', 'details'. HOUR is often blank on rows that
    belong to the same moment as the row above (carried forward here); PLACE is
    used as given. Time text like '7:35PM' or a stray '?' is handled leniently."""
    wb = openpyxl.load_workbook(file_obj, data_only=True)
    ws = wb.worksheets[0]
    header_row, cols = _locate_header(ws, ["place", "hour", "detail"])
    if header_row is None:
        raise ValueError(
            "No se encontró una fila de encabezado con las columnas 'place', 'hour' y 'details'."
        )

    place_col = cols.get("place")
    hour_col = cols.get("hour")
    details_col = cols.get("detail")

    rows = []
    last_time = None
    last_place = ""
    for row_num in range(header_row + 1, ws.max_row + 1):
        details = ws.cell(row=row_num, column=details_col).value if details_col else None
        details = str(details).strip() if details is not None else ""
        if not details:
            continue

        place_val = ws.cell(row=row_num, column=place_col).value if place_col else None
        place = str(place_val).strip() if place_val is not None else ""
        if place:
            last_place = place

        hour_val = ws.cell(row=row_num, column=hour_col).value if hour_col else None
        parsed_time = _cell_time(hour_val)
        carried_over = parsed_time is None
        if parsed_time is not None:
            last_time = parsed_time

        title = details if len(details) <= TITLE_MAX_LEN else details[: TITLE_MAX_LEN - 1] + "…"
        notes = details if len(details) > TITLE_MAX_LEN else ""

        rows.append(ParsedSessionRow(
            title=title,
            notes=notes,
            venue_name=last_place,
            start_time=last_time,
            time_is_carried_over=carried_over,
        ))
    return rows
