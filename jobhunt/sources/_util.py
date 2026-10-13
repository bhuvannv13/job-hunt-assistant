"""Small helpers shared by the source parsers."""
from __future__ import annotations

from datetime import datetime, timezone


def iso_date(value) -> str:
    """Accept ISO strings, epoch seconds or epoch milliseconds; return YYYY-MM-DD or ''."""
    if value in (None, ""):
        return ""
    if isinstance(value, (int, float)):
        seconds = value / 1000 if value > 10_000_000_000 else value
        return datetime.fromtimestamp(seconds, tz=timezone.utc).date().isoformat()
    text = str(value).strip()
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        return text[:10]
    return ""


def join_locations(*parts) -> str:
    seen, out = set(), []
    for part in parts:
        if not part:
            continue
        for piece in (part if isinstance(part, (list, tuple)) else [part]):
            piece = str(piece).strip()
            if piece and piece.lower() not in seen:
                seen.add(piece.lower())
                out.append(piece)
    return "; ".join(out)
