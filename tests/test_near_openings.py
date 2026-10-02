"""SR4a -- unit tests for the near-opening window builder and its buckets.

Synthetic rows only: no artifact is read, no frame is decoded.  What is being
pinned is the card's DECISION RULE (STATUS.md card SR4a step 4), so that a later
re-run of ``scripts/probe_near_openings.py`` cannot quietly move a serve from
one bucket to another by editing a threshold.  ``GAP_SERVE_MIN`` is asserted to
be the imported constant, not a copy that can drift.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import probe_near_openings as P  # noqa: E402
import relabel_serves  # noqa: E402
import score_serves  # noqa: E402


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def act(frame, action="dig", team="A", touch=1, rally=1, track=1, gap="auto"):
    """One synthetic emitted action in the probe's own shape."""
    return {"index": None, "frame_number": frame, "action": action, "team": team,
            "side": P._side_of_team(team), "touch_number": touch,
            "rally_id": rally, "track_id": track, "gap_prev": None}


def chain(*actions):
    """Index + fill ``gap_prev`` the way ``sorted_actions`` does (video start None)."""
    ordered = sorted(actions, key=lambda a: a["frame_number"])
    for i, a in enumerate(ordered):
        a["index"] = i
        a["gap_prev"] = None if i == 0 else a["frame_number"] - ordered[i - 1]["frame_number"]
    return ordered


def serve(frame, side="near", point=None):
    return {"frame": frame, "side": side, "point": point, "squad": None,
            "split": "dev", "tolerance": P.TOLERANCE}


# ---------------------------------------------------------------------------
# the imported constant
# ---------------------------------------------------------------------------

def test_gap_serve_min_is_imported_from_relabel_serves():
    """The window threshold is relabel_serves', not a private copy."""
    assert P.GAP_SERVE_MIN is relabel_serves.GAP_SERVE_MIN


def test_gap_serve_min_value_is_143():
    """143 sits in the dead-ball-gap chasm (opener >= 153 f, non-opening <= 134 f)."""
    assert relabel_serves.GAP_SERVE_MIN == 143


def test_probe_redefines_no_gap_constant():
    """A module-level re-definition of the threshold would be a silent re-tune."""
    tree = ast.parse((REPO / "scripts" / "probe_near_openings.py").read_text())
    offenders = []
    for node in tree.body:
        targets = ([t.id for t in node.targets if isinstance(t, ast.Name)]
                   if isinstance(node, ast.Assign) else [])
        if "GAP_SERVE_MIN" in targets:
            offenders.append(getattr(node, "lineno", "?"))
    assert offenders == []


def test_probe_imports_cvv_never():
    """Card step 1: this probe decodes nothing, so it must not import cv2."""
    tree = ast.parse((REPO / "scripts" / "probe_near_openings.py").read_text())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert "cv2" not in imported


# ---------------------------------------------------------------------------
# the window builder
# ---------------------------------------------------------------------------

def test_window_starts_at_the_last_action_reaching_the_chasm():
    """A below-threshold t1 gap is NOT an opener: f110 (gap 10) does not open."""
    actions = chain(act(100), act(110), act(300))
    span = P.window_for_serve_on_side(actions, 320, "near")
    assert span is not None
    assert actions[span[0]]["frame_number"] == 300
    # the LAST qualifier wins, not the first: an anchor behind a chasm gap
    # is superseded by the action the chasm actually precedes
    actions2 = chain(act(100), act(110), act(300), act(312))
    span2 = P.window_for_serve_on_side(actions2, 320, "near")
    assert actions2[span2[0]]["frame_number"] == 300


def test_window_starts_at_video_start_when_it_is_the_only_candidate():
    """``gap_prev is None`` is an anchor (video start), per the card's rule."""
    actions = chain(act(100))
    span = P.window_for_serve_on_side(actions, 120, "near")
    assert actions[span[0]]["frame_number"] == 100


def test_window_is_none_when_nothing_before_the_serve_opens():
    """A stream with NO actions at all has no window (not a fabricated one)."""
    assert P.window_for_serve_on_side([], 130, "near") is None


def test_clip_opening_serve_opens_the_window_at_the_first_action():
    """A serve with nothing before it is its OWN window: video start is the anchor.

    ``relabel_serves`` measures openers from "the previous action (anchored
    prefix: ... or video start)", so the first action of a stream qualifies;
    dropping it would read every clip-opening serve as never emitted.
    """
    actions = chain(act(29, "serve"), act(74, "dig", team="B"))
    span = P.window_for_serve_on_side(actions, 29, "near")
    assert actions[span[0]]["frame_number"] == 29
    window = P.window_actions(actions, span)
    assert P.bucket_of(29, "near", window)[0] == "hit"


def test_clip_opening_serve_after_its_gt_frame_still_opens_at_the_first_action():
    """e6's shape: the first emitted action is 1 f AFTER the GT serve frame."""
    actions = chain(act(35, "serve"), act(73, "dig", team="B"))
    span = P.window_for_serve_on_side(actions, 34, "near")
    assert actions[span[0]]["frame_number"] == 35
    assert P.bucket_of(34, "near", P.window_actions(actions, span))[0] == "hit"


def test_window_ends_at_the_first_other_team_action_after_the_serve():
    actions = chain(act(300, "dig", team="A"), act(320, "dig", team="A"),
                    act(340, "dig", team="B"), act(360, "dig", team="A"))
    span = P.window_for_serve_on_side(actions, 320, "near")
    window = P.window_actions(actions, span)
    # inclusive of the reply: "ends AT the first action on the other team"
    assert [a["frame_number"] for a in window] == [300, 320, 340]


def test_window_is_open_ended_when_no_other_team_action_follows():
    actions = chain(act(300, "dig", team="A"), act(320, "dig", team="A"),
                    act(340, "dig", team="A"))
    span = P.window_for_serve_on_side(actions, 320, "near")
    window = P.window_actions(actions, span)
    assert [a["frame_number"] for a in window] == [300, 320, 340]


def test_window_empty_when_no_opener_exists():
    assert P.window_actions(chain(act(100), act(110)), None) == []


def test_gap_prev_is_the_gap_to_the_previous_action_of_any_kind():
    """A window opener is a dead-ball gap, not a gap inside one gesture."""
    actions = chain(act(100, "dig"), act(112, "set"), act(300, "serve"))
    assert actions[1]["gap_prev"] == 12
    assert actions[2]["gap_prev"] == 188


# ---------------------------------------------------------------------------
# the four buckets
# ---------------------------------------------------------------------------

def test_bucket_hit_is_a_serve_as_the_window_first_action():
    """The card's own example: a right-label serve opening the window."""
    actions = chain(act(300, "dig"), act(320, "serve"))
    window = P.window_actions(actions, P.window_for_serve_on_side(actions, 320, "near"))
    bucket, deciding = P.bucket_of(320, "near", window)
    assert bucket == "hit"
    assert [a["frame_number"] for a in deciding] == [320]


def test_bucket_hit_beats_a_non_opener_on_the_same_side():
    """Bucket precedence is the card's: a serve in tolerance is a ``hit``."""
    actions = chain(act(300, "dig"), act(316, "serve"), act(322, "dig"))
    window = P.window_actions(actions, P.window_for_serve_on_side(actions, 320, "near"))
    bucket, _ = P.bucket_of(320, "near", window)
    assert bucket == "hit"


def test_bucket_mislabeled_opener_is_a_wrong_label_on_the_own_side_as_first():
    """The card's own example: a ``dig`` first action -> emitted_mislabeled_opener."""
    actions = chain(act(100), act(110), act(318, "dig"), act(340, "dig", team="B"))
    window = P.window_actions(actions, P.window_for_serve_on_side(actions, 320, "near"))
    assert window[0]["frame_number"] == 318     # the 208 f gap opens the window
    bucket, deciding = P.bucket_of(320, "near", window)
    assert bucket == "emitted_mislabeled_opener"
    assert [a["frame_number"] for a in deciding] == [318]


def test_bucket_not_opener_is_an_own_side_action_inside_an_earlier_rally():
    """The card's own example: a ``dig`` third action inside an existing rally."""
    actions = chain(act(300, "dig"), act(310, "dig"), act(320, "dig"),
                    act(340, "dig", team="B"))
    window = P.window_actions(actions, P.window_for_serve_on_side(actions, 320, "near"))
    bucket, deciding = P.bucket_of(320, "near", window)
    assert bucket == "emitted_not_opener"
    assert 320 in [a["frame_number"] for a in deciding]
    # and the window's first action (300) is NOT what decided it
    assert window[0]["frame_number"] not in [a["frame_number"] for a in deciding]


def test_bucket_not_emitted_is_an_empty_own_side_neighbourhood():
    """The card's own example: an empty window -> not_emitted."""
    actions = chain(act(100, "dig", team="B"))
    window = P.window_actions(actions, P.window_for_serve_on_side(actions, 500, "near"))
    bucket, deciding = P.bucket_of(500, "near", window)
    assert bucket == "not_emitted"
    assert deciding == []


def test_bucket_not_emitted_when_only_the_other_side_is_emitted():
    """Own side matters: a far-side action near a near serve is not a near emission."""
    actions = chain(act(300, "dig", team="A"), act(320, "dig", team="B"))
    window = P.window_actions(actions, P.window_for_serve_on_side(actions, 320, "near"))
    assert P.bucket_of(320, "near", window)[0] == "not_emitted"


def test_bucket_respects_the_tolerance_around_the_gt_frame():
    """An own-side action 16 f away is outside +-15 f, so it cannot decide.

    The window still exists in both cases (the late action reaches the chasm and
    opens it); what the tolerance removes is its power to DECIDE the bucket.
    """
    outside = chain(act(100), act(110), act(334, "dig"))
    win_out = P.window_actions(outside, P.window_for_serve_on_side(outside, 350, "near"))
    assert win_out[0]["frame_number"] == 334
    assert P.bucket_of(350, "near", win_out)[0] == "not_emitted"
    inside = chain(act(100), act(110), act(335, "dig"))
    win_in = P.window_actions(inside, P.window_for_serve_on_side(inside, 350, "near"))
    assert win_in[0]["frame_number"] == 335
    assert P.bucket_of(350, "near", win_in)[0] == "emitted_mislabeled_opener"


def test_buckets_partition_the_near_serves():
    """Every near serve lands in exactly one of the four buckets, no fifth."""
    actions = chain(act(300, "serve"), act(310, "dig"), act(320, "dig"))
    window = P.window_actions(actions, P.window_for_serve_on_side(actions, 320, "near"))
    seen = {P.bucket_of(320, "near", window)[0]}
    assert seen <= set(P.BUCKETS)


# ---------------------------------------------------------------------------
# the far-serve trap guard
# ---------------------------------------------------------------------------

def test_far_trap_flags_a_near_action_with_no_onset():
    """The card's own example: a far serve, a near action, no onset -> the trap."""
    actions = chain(act(300, "serve", team="B"), act(320, "dig", team="A"))
    window = P.window_actions(actions, P.window_for_serve_on_side(actions, 320, "far"))
    assert P.far_trap(320, window, [])["flagged"] is True


def test_far_trap_not_flagged_when_a_onset_is_near():
    actions = chain(act(300, "serve", team="B"), act(320, "dig", team="A"))
    window = P.window_actions(actions, P.window_for_serve_on_side(actions, 320, "far"))
    assert P.far_trap(320, window, [{"frame": 318}])["flagged"] is False


def test_far_trap_not_flagged_without_a_near_action():
    actions = chain(act(300, "serve", team="B"), act(330, "dig", team="B"))
    window = P.window_actions(actions, P.window_for_serve_on_side(actions, 320, "far"))
    assert P.far_trap(320, window, [])["flagged"] is False


# ---------------------------------------------------------------------------
# G2's pre-registered rules
# ---------------------------------------------------------------------------

def _table(rows):
    buckets = {b: 0 for b in P.BUCKETS}
    for row in rows:
        buckets[row["bucket"]] += 1
    return {"rows": rows, "buckets": buckets}


def test_g2_sr4_needs_four_repairable_misses():
    """The rule is a COUNT (>= 4 of 8), evaluated on the misses only."""
    base = [{"side": "near", "bucket": "hit", "frame": 1, "point": 1}]
    misses = [{"side": "near", "bucket": "emitted_mislabeled_opener",
               "frame": 10 + i, "point": 2 + i} for i in range(3)]
    rows = base + misses + [{"side": "near", "bucket": "not_emitted",
                             "frame": 50 + i, "point": 10 + i} for i in range(4)]
    verdict = P.g2(_table(rows), [])
    assert verdict["miss_near"] == 7
    assert verdict["repairable"] == 3
    assert verdict["sr4_near_proceeds_after_the_fact"] is False


def test_g2_mb_reopens_only_with_three_never_emitted_and_two_coasting():
    rows = [{"side": "near", "bucket": "hit", "frame": 1, "point": 1}]
    rows += [{"side": "near", "bucket": "not_emitted", "frame": 20 + i, "point": 3 + i}
             for i in range(3)]
    two_coasting = [{"diag": "ok", "predicted": True}, {"diag": "ok", "predicted": True}]
    assert P.g2(_table(rows), two_coasting)["mb_reopened"] is True
    one_coasting = [{"diag": "ok", "predicted": True}]
    assert P.g2(_table(rows), one_coasting)["mb_reopened"] is False


def test_g2_counts_coasting_only_when_predicted_is_true():
    """``predicted: false`` at the lowest foot is NOT coasting."""
    rows = [{"side": "near", "bucket": "not_emitted", "frame": 20 + i, "point": 3 + i}
            for i in range(3)]
    not_coasting = [{"diag": "ok", "predicted": False}] * 3
    assert P.g2(_table(rows), not_coasting)["coasting_predicted_true"] == 0
    assert P.g2(_table(rows), not_coasting)["mb_reopened"] is False


def test_g2_counts_diag_absent_as_unreadable_not_as_coasting():
    rows = [{"side": "near", "bucket": "not_emitted", "frame": 20 + i, "point": 3 + i}
            for i in range(3)]
    absent = [{"diag": "diag_absent", "predicted": None}] * 3
    verdict = P.g2(_table(rows), absent)
    assert verdict["coasting_predicted_true"] == 0
    assert verdict["coasting_readable"] == 0


def test_g2_is_scoped_to_the_near_misses_not_the_whole_table():
    """The far table's ``not_emitted`` rows are a DIFFERENT population.

    The 17 far misses are all ``not_emitted`` by construction (far is 0/17), so
    pooling them into the misses would read ``not_emitted >= 3`` off the far
    side's blindness alone and reopen M-b for the wrong reason.  This pins the
    scope the card states: the rule reads the 8 NEAR misses.
    """
    near_rows = [{"side": "near", "bucket": "hit", "frame": 1, "point": 1}]
    near_rows += [{"side": "near", "bucket": "emitted_not_opener",
                   "frame": 10 + i, "point": 2 + i} for i in range(7)]
    far_rows = [{"side": "far", "bucket": "not_emitted",
                 "frame": 100 + i, "point": 5 + i} for i in range(17)]
    coasting = [{"diag": "ok", "predicted": False}] * 7
    verdict = P.g2(_table(near_rows + far_rows), coasting)
    assert verdict["miss_near"] == 7
    assert verdict["never_produced"] == 0
    assert verdict["mb_reopened"] is False
    # the all-serve scope is carried alongside, still visible, never mixed in
    assert verdict["all_serves_buckets"]["not_emitted"] == 17
    assert verdict["buckets_over_misses"]["not_emitted"] == 0


def test_g2_mb_counts_coasting_that_sits_on_a_not_emitted_miss():
    """A ``predicted:true`` track only supports M-b on a never-produced miss."""
    rows = [{"side": "near", "bucket": "emitted_mislabeled_opener",
             "frame": 10 + i, "point": 2 + i} for i in range(5)]
    rows += [{"side": "near", "bucket": "not_emitted", "frame": 40 + i, "point": 9 + i}
             for i in range(3)]
    coasting = [{"diag": "ok", "predicted": True, "bucket": "not_emitted"}] * 3
    verdict = P.g2(_table(rows), coasting)
    assert verdict["coasting_not_emitted"] == 3
    assert verdict["coasting_predicted_true"] == 3
    assert verdict["mb_reopened"] is True


# ---------------------------------------------------------------------------
# the coasting read
# ---------------------------------------------------------------------------

def test_coasting_read_picks_the_lowest_foot_same_team_track():
    frames = {500: {"frame": 500, "players": [
        {"track_id": 1, "team": "A", "bbox": [0, 0, 10, 600], "predicted": True},
        {"track_id": 2, "team": "A", "bbox": [0, 0, 10, 900], "predicted": False},
        {"track_id": 3, "team": "B", "bbox": [0, 0, 10, 990], "predicted": False},
    ]}}
    rows = [{"frame": 500, "point": 1, "bucket": "not_emitted",
             "side": "near", "_own_team_letter": "A"}]
    read = P.read_coasting(frames, rows)[0]
    assert read["track_id"] == 2          # the foot at 900 is nearest the camera
    assert read["predicted"] is False
    assert read["n_same_team"] == 2


def test_coasting_read_skips_hits():
    """Hits are not misses; the read covers the misses only."""
    frames = {500: {"frame": 500, "players": []}}
    rows = [{"frame": 500, "point": 1, "bucket": "hit", "side": "near",
             "_own_team_letter": "A"}]
    assert P.read_coasting(frames, rows) == []


def test_coasting_read_reports_diag_absent_for_a_missing_line():
    read = P.read_coasting({}, [{"frame": 500, "point": 1, "bucket": "not_emitted",
                                 "side": "near", "_own_team_letter": "A"}])[0]
    assert read["diag"] == "diag_absent"
    assert read["predicted"] is None


# ---------------------------------------------------------------------------
# the scorer's names are the scorer's
# ---------------------------------------------------------------------------

def test_scorer_helpers_exist_with_the_cards_signatures():
    """Card step 2: import, never re-implement."""
    for name in ("build_match_session", "build_entreno_session",
                 "serve_rows_from_contact_gt", "production_candidates",
                 "game_on_candidates", "match_candidates", "match_split",
                 "entreno_split", "entreno_squad_to_side",
                 "classify_false_positives"):
        assert callable(getattr(score_serves, name)), name


def test_tolerance_is_the_scorers_own_default():
    assert P.TOLERANCE == score_serves.DEFAULT_TOLERANCE == 15