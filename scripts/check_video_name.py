"""Exit 1 unless the video's file name is YYYYMMDD_HHMM_<venue>_<text> (the match key).

Called by `make calibrate` and `make run-match` (so `make process`, `make inbox`).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.publish.naming import MatchKeyError, require_match_name  # noqa: E402

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: check_video_name.py <video>")
    try:
        require_match_name(sys.argv[1])
    except MatchKeyError as exc:
        sys.exit(f"error: {exc}")
