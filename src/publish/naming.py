"""Match identity = the video's file name (owner decision, 2026-10-06).

Convention: ``YYYYMMDD_HHMM_<venue>_<free text>``, lowercase ``[a-z0-9_]``,
e.g. ``20260920_1830_bogatell_ari_joan``. Date and local start time come
first so two matches on the same day never collide and the files sort
chronologically. The same string keys ``calibrations/<key>.json``,
``output/<key>/`` and the ``matches.match_key`` row, so it must be fixed
BEFORE calibration -- the inbox runner renames incoming files.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Optional

MATCH_KEY_RE = re.compile(r"^(\d{8})_(\d{4})_([a-z0-9]+(?:_[a-z0-9]+)*)$")
#: A stem that already starts with a date but has no time (legacy names such
#: as ``20260920_match_ari_joan``).
DATE_ONLY_RE = re.compile(r"^(\d{8})_([a-z0-9]+(?:_[a-z0-9]+)*)$")

#: A camera clock can be a little ahead; anything later than this is a typo
#: (``20290928_...`` exists in ground_truth/).
FUTURE_SLACK = timedelta(days=1)


class MatchKeyError(ValueError):
    """The name cannot identify a match."""


@dataclass(frozen=True)
class MatchKey:
    key: str
    match_date: date
    start_time: time
    slug: str


def parse_match_key(key: str, today: Optional[date] = None) -> MatchKey:
    """Validate ``key`` against the convention and return its parts."""
    m = MATCH_KEY_RE.match(key or "")
    if not m:
        raise MatchKeyError(
            f"{key!r} is not a match key: expected YYYYMMDD_HHMM_<venue>_<text> "
            f"(lowercase letters, digits, underscores), e.g. 20260920_1830_bogatell_ari_joan")
    ymd, hhmm, slug = m.groups()
    try:
        d = datetime.strptime(ymd, "%Y%m%d").date()
        t = datetime.strptime(hhmm, "%H%M").time()
    except ValueError as exc:
        raise MatchKeyError(f"{key!r}: {ymd}/{hhmm} is not a real date/time") from exc
    today = today or date.today()
    if d > today + FUTURE_SLACK:
        raise MatchKeyError(f"{key!r}: the date {d} is in the future (typo?)")
    return MatchKey(key=key, match_date=d, start_time=t, slug=slug)


def slugify(text: str) -> str:
    """ASCII lowercase ``[a-z0-9_]`` slug ("Bogatell – Ari & Joan" -> "bogatell_ari_joan")."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_text.lower()).strip("_")
    return slug or "match"


def match_key_for(stem: str, started_at: Optional[datetime]) -> str:
    """The conforming key for a video called ``stem``.

    * already ``YYYYMMDD_HHMM_<slug>``  -> unchanged
    * ``YYYYMMDD_<slug>`` (no time)    -> the time is inserted from ``started_at``
    * anything else (``IMG_1234``)      -> ``<started_at YYYYMMDD_HHMM>_<slug(stem)>``

    ``started_at`` is the recording's LOCAL start time (the inbox runner reads
    it from the file's metadata). Raises when a time is needed and unknown.
    """
    if MATCH_KEY_RE.match(stem):
        return stem
    slug = slugify(stem)
    dated = DATE_ONLY_RE.match(slug)
    if started_at is None:
        raise MatchKeyError(
            f"{stem!r} lacks the YYYYMMDD_HHMM_ prefix and the recording time is unknown; "
            f"rename it to YYYYMMDD_HHMM_<venue>_<text>")
    if dated:
        # The name's date wins (someone typed it); only the time is added.
        ymd, rest = dated.groups()
        return f"{ymd}_{started_at.strftime('%H%M')}_{rest}"
    return f"{started_at.strftime('%Y%m%d_%H%M')}_{slug}"
