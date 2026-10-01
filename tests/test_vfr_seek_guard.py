"""The VFR seek guard: measurement probes may not position windows by seek.

The 20260920 match is 25.67 fps content inside a 30.12 fps VFR container
(AGENTS.md §7), so ``cv2.CAP_PROP_POS_FRAMES`` seeks are FRAME-UNRELIABLE.
Measured against a full sequential decode (``docs/g4_far_serve_alignment.md``;
artifact ``output/g4/seek_offsets.json``): 13 probe points across the file land
**-28..+30 frames** from the requested index (mean +8.5) -- twice the +-15 f
tolerance every contact score uses.  A windowed probe positioned by seek
therefore measures the wrong frames while reporting exact numbers, which is
exactly how the G4 serve-event score ended up with an untrustworthy precision.

Production (``src/``) never seeks, and the discipline now applies to the probes:
a probe that needs a window decodes SEQUENTIALLY and indexes what it decoded.
This test greps the tree so a new probe cannot quietly reintroduce the defect.
Sites that genuinely cannot avoid a seek are allow-listed WITH a reason, and a
stale entry fails so the list cannot rot.
"""

import ast
import re
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

#: ``path -> why a seek is still there``.
ALLOWED: dict = {
    # Superseded by the seek-free scripts/probe_serve_events_seq.py (one
    # continuous FrameProcessor). Kept so the numbers quoted in
    # docs/g4_serve_events.md stay reproducible; its +-15 f precision is
    # known-invalid, which is what that doc now says.
    "scripts/score_serve_events.py": "legacy windowed G4 scorer, superseded",
    "scripts/probe_far_serve_tracking.py": "legacy G4 stage-waterfall probe, superseded",
    # Walks the file sequentially from a cursor and only falls back to a seek
    # when the stream ended unexpectedly.
    "scripts/annotate_video.py": "sequential cursor first; seek is a rare fallback",
    # Each (image, class) pair is read and labelled from the SAME seeked
    # position, so the mined pairs stay self-consistent; only the recorded
    # frame indices in the dataset metadata can be off.
    "scripts/mine_ball_frames.py": "image/label pairs self-consistent per seek",
    # "restart from the beginning" -- frame 0 is exact.
    "src/analysis/live_debug_processor.py": "restart to frame 0 only",
    "tests/test_live_debug_decoupling.py": "asserts on the source string, no decode",
    # KNOWN ISSUE (raised by this guard, not fixed here): the player-thumbnail
    # crops can be taken up to ~30 f away from the recorded frame, so a crop may
    # miss the player. Cosmetic (review UI), but it should become a sequential
    # cursor over sorted frame indices.
    "src/db/ingest.py": "KNOWN ISSUE: thumbnail crop may miss the player",
    # KNOWN ISSUE (raised by this guard, not fixed here): the owner-GT
    # annotator can show a frame up to ~30 f from the requested one. The GT is
    # the gold standard, so this one wants a sequential-cursor fix before the
    # next annotation pass.
    "scripts/annotate_player_gt.py": "KNOWN ISSUE: owner GT may be judged off-frame",
}

SEEK = re.compile(r"CAP_PROP_POS_FRAMES")


def _seek_lines(path: Path) -> list:
    """Lines where the code really TOUCHES cv2.CAP_PROP_POS_FRAMES.

    Parsed with ``ast`` so a docstring or a comment that *mentions* the
    constant (this file, the probe docstrings) is not an offence -- only an
    attribute access is.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    hits = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "CAP_PROP_POS_FRAMES":
            hits.add(node.lineno)
    return sorted(hits)


def _python_sources():
    for folder in ("scripts", "src", "tests"):
        for path in sorted((ROOT / folder).rglob("*.py")):
            yield path


class VfrSeekGuardTest(unittest.TestCase):
    def test_no_seeks_outside_the_allowlist(self):
        offenders = []
        for path in _python_sources():
            rel = str(path.relative_to(ROOT))
            if rel in ALLOWED:
                continue
            for lineno in _seek_lines(path):
                offenders.append(f"{rel}:{lineno}")
        self.assertEqual(
            [], offenders,
            "CAP_PROP_POS_FRAMES is frame-unreliable on the VFR match "
            "(measured -28..+30 f). Decode sequentially; if a site genuinely "
            "needs it, add it to ALLOWED with the reason.")

    def test_the_allowlist_is_honest(self):
        """No stale entries, and every exception carries a real reason."""
        for rel, reason in ALLOWED.items():
            self.assertTrue((ROOT / rel).exists(), f"allow-listed {rel} is gone")
            self.assertGreaterEqual(len(reason), 20,
                                    f"allow-list reason for {rel} is too thin")
            self.assertTrue(_seek_lines(ROOT / rel),
                            f"{rel} is allow-listed but no longer seeks")

    def test_sequential_probes_exist(self):
        """The seek-free replacements the allowlist points at must be present."""
        for rel in ("scripts/probe_serve_events_seq.py",
                    "scripts/probe_far_roi_ball.py"):
            self.assertTrue((ROOT / rel).exists(), rel)
            self.assertEqual([], _seek_lines(ROOT / rel), rel)


if __name__ == "__main__":
    unittest.main()
