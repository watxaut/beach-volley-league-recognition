"""Post-run identity read (src/postrun/identity.py): who is who per rally.

The synthetic stream (tests/postrun_sim.py) knows who every body is. Each
body gets the similarities the causal resolver would have measured against
the four enrolled players -- squad A enrolled on the near half, squad B on
the far half, levels taken from the 20261010 match -- and then the labels are
overwritten with what a resolver that MISSED the side switch stamps. The read
has to give the people back from the similarities alone:

* one orientation per rally, at two levels the match itself shows (the unseen
  orientation is not a mirror image of the enrolled one);
* a body's half from its squad, not from feet that stand on the net line;
* a track id that moved to the teammate is followed;
* teammates that look alike get no label -- and a dump without identity
  observations is left exactly as it was.
"""

import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tests"))

import postrun_sim as sim  # noqa: E402
from src.postrun import identity  # noqa: E402
from src.postrun.reconstruct import reconstruct  # noqa: E402

PLAYERS = ["P1A", "P2A", "P1B", "P2B"]

#: (who, half seen on) -> similarity to the anchors of P1A, P2A, P1B, P2B.
#: Squad A was enrolled near and squad B far, so those rows are same-view
#: (own anchor high). The other four are cross-view: lower, and P2B seen near
#: looks more like squad A than like herself -- the bias that makes the unseen
#: orientation read about zero instead of the mirror of the enrolled one.
VIEW_SIMS = {
    ("P1A", "near"): (0.95, 0.91, 0.56, 0.43),
    ("P2A", "near"): (0.83, 0.93, 0.60, 0.50),
    ("P1B", "far"): (0.20, 0.30, 0.81, 0.25),
    ("P2B", "far"): (0.49, 0.59, 0.47, 0.77),
    ("P1B", "near"): (0.41, 0.46, 0.63, 0.28),
    ("P2B", "near"): (0.80, 0.84, 0.48, 0.63),
    ("P1A", "far"): (0.69, 0.72, 0.53, 0.43),
    ("P2A", "far"): (0.36, 0.66, 0.53, 0.57),
}


def _stale(label):
    """What a resolver that never saw the switch calls this body: the squad
    letter of the half it was enrolled on."""
    return label[:2] + ("A" if label[2] == "B" else "B")


def observe(stream, table=VIEW_SIMS, noise=0.03, missed_switch=True, seed=0):
    """Give every body its similarities; leave the labels a causal resolver
    that missed every switch would have left. Returns frame -> {track id:
    true label}."""
    rng = np.random.default_rng(seed)
    stream.identity_players = list(PLAYERS)
    truth = {}
    for f, row in enumerate(stream.players):
        for p in row:
            who = p.label
            truth.setdefault(f, {})[p.track_id] = who
            base = np.array(table[(who, p.court_side)])
            p.id_sims = tuple(float(v) for v in np.clip(base + rng.normal(0, noise, 4), 0, 1))
            switched = (who[2] == "B") == (p.court_side == "near")
            if missed_switch and switched:
                p.label = _stale(who)
                p.squad = 1 if p.label[2] == "A" else 2
    return truth


def _match(serving_sides, switch_after=()):
    b = sim.StreamBuilder(12.0 * len(serving_sides) + 5.0)
    positions = sim.NEAR_A
    for i, side in enumerate(serving_sides):
        if i in switch_after:
            positions = sim.NEAR_B if positions is sim.NEAR_A else sim.NEAR_A
        b.rally(sim.standard_rally(2.0 + 12.0 * i, side, positions))
    return b


def _labels_right(stream, truth, read):
    """Share of labelled bodies inside the rally windows that carry their own
    label, and how many were labelled."""
    ok = n = 0
    for r in read.rallies:
        for f in range(r.lo, r.hi + 1):
            for p in stream.players[f]:
                if p.label:
                    n += 1
                    ok += p.label == truth[f][p.track_id]
    return ok / max(n, 1), n


def _read(stream, geometry, spans):
    read, reader = identity.read_identities(stream, geometry, spans)
    if reader is not None:
        for r in read.rallies:
            reader.apply(r)
    return read


def _spans(result):
    return [(p["start_frame"], p["end_frame"]) for p in result["points"]]


# --------------------------------------------------------------------------- #
# which squad is near
# --------------------------------------------------------------------------- #

def test_a_switch_the_causal_labels_missed_is_read_per_rally():
    b = _match(["near", "far", "near", "far"], switch_after=(2,))
    stream = b.build()
    truth = observe(stream)
    result = reconstruct(stream, b.g, points_to_win=21, switch_every=2)
    points = result["points"]
    assert result["identity"]["applied"] and result["identity"]["two_orientations"]
    assert [r["near_squad"] for r in result["identity"]["rallies"]] == [1, 1, 2, 2]
    assert [p["near_team"] for p in points] == ["A", "A", "B", "B"]
    # the same squads serve from the other end after the switch
    assert [p["serve"]["team"] for p in points] == ["A", "B", "B", "A"]
    assert result["checks"]["side_switch_after_point"] == [2]
    # every touch is credited to the person who played it
    for p in points:
        for t in p["touches"]:
            if t["player"]:
                tid = next(o.track_id for o in stream.players[t["frame"]]
                           if o.label == t["player"])
                assert truth[t["frame"]][tid] == t["player"]
                assert t["team"] == t["player"][2]


def test_the_unseen_orientation_is_not_assumed_to_mirror_the_enrolled_one():
    b = _match(["near", "far", "near", "far"], switch_after=(2,))
    stream = b.build()
    observe(stream)
    levels = _read(stream, b.g, _spans(reconstruct(b.build(), b.g))).levels
    # enrolled layout ~ +0.36; the other one sits near zero, not at -0.36
    assert levels["squad_1_near"] > 0.3
    assert -0.2 < levels["squad_2_near"] < 0.1


def test_one_level_means_nobody_switched():
    b = _match(["near", "far", "far", "near"])
    stream = b.build()
    truth = observe(stream, missed_switch=False)
    read = _read(stream, b.g, _spans(reconstruct(b.build(), b.g)))
    assert read.applied and not read.two_levels
    assert [r.near_squad for r in read.rallies] == [1, 1, 1, 1]
    assert _labels_right(stream, truth, read)[0] == 1.0


def test_one_odd_rally_is_not_two_switches():
    b = _match(["near", "far", "near", "far", "near", "far"], switch_after=(4,))
    stream = b.build()
    observe(stream)
    spans = _spans(reconstruct(b.build(), b.g))
    # rally 2 reads half way between the two levels (bad light, a stranger in
    # a box): the rallies around it keep it where it is.
    lo, hi = stream.rally_window(*spans[1])
    for f in range(lo, hi + 1):
        for p in stream.players[f]:
            p.id_sims = (0.70, 0.70, 0.55, 0.52) if p.court_side == "near" else (
                0.52, 0.55, 0.60, 0.60)
    read = _read(stream, b.g, spans)
    assert [r.near_squad for r in read.rallies] == [1, 1, 1, 1, 2, 2]


def test_a_dump_without_identity_observations_is_left_alone():
    b = _match(["near", "far", "near", "far"], switch_after=(2,))
    plain = reconstruct(b.build(), b.g, points_to_win=21, switch_every=2)
    assert plain["identity"] == {"applied": False, "levels": None, "rallies": [],
                                 "reason": identity.REASON_NO_OBSERVATIONS,
                                 "two_orientations": False}
    # the simulator's own labels are right, and they are what was used
    assert [p["near_team"] for p in plain["points"]] == ["A", "A", "B", "B"]


# --------------------------------------------------------------------------- #
# who is who
# --------------------------------------------------------------------------- #

def test_labels_follow_the_people_across_the_switch():
    b = _match(["near", "far", "near", "far"], switch_after=(2,))
    stream = b.build()
    truth = observe(stream)
    read = _read(stream, b.g, _spans(reconstruct(b.build(), b.g)))
    share, n = _labels_right(stream, truth, read)
    assert share == 1.0 and n > 1000
    assert all(not r.withheld for r in read.rallies)


def test_a_blocker_on_the_net_line_takes_the_half_of_its_squad():
    positions = dict(sim.NEAR_A, P1B=(2.5, 7.9))        # far blocker, feet at the net
    b = sim.StreamBuilder(17.0)
    b.rally(sim.standard_rally(2.0, "near", positions))
    stream = b.build()
    truth = observe(stream, missed_switch=False)
    for row in stream.players:                          # the tracker reads his feet near
        for p in row:
            if p.label == "P1B":
                p.court_side = "near"
    spans = _spans(reconstruct(b.build(), b.g))
    read = _read(stream, b.g, spans)
    r = read.rallies[0]
    blocker = [p for f in range(r.lo, r.hi + 1) for p in stream.players[f]
               if truth[f][p.track_id] == "P1B"]
    assert blocker and all(p.label == "P1B" and p.court_side == "far" for p in blocker)


def test_a_track_id_that_moves_to_the_teammate_is_followed():
    b = sim.StreamBuilder(17.0)
    b.rally(sim.standard_rally(2.0, "near", sim.NEAR_A, exchanges=2))
    stream = b.build()
    spans = _spans(reconstruct(b.build(), b.g))
    lo, hi = stream.rally_window(*spans[0])
    mid = (lo + hi) // 2
    for f in range(mid, stream.n_frames):               # ids of the near pair swap
        near = [p for p in stream.players[f] if p.court_side == "near"]
        if len(near) == 2:
            near[0].track_id, near[1].track_id = near[1].track_id, near[0].track_id
    truth = observe(stream, missed_switch=False)
    read = _read(stream, b.g, spans)
    share, n = _labels_right(stream, truth, read)
    # all but the frames around the swap, where the path changes over
    assert share > 0.97 and n > 500
    assert read.rallies[0].id_changes == 1


def test_teammates_that_look_alike_get_no_label():
    twins = dict(VIEW_SIMS)
    twins[("P1A", "near")] = twins[("P2A", "near")] = (0.90, 0.90, 0.58, 0.47)
    b = _match(["near", "far"])
    stream = b.build()
    observe(stream, table=twins, missed_switch=False)
    result = reconstruct(stream, b.g)
    for r in result["identity"]["rallies"]:
        assert r["near_squad"] == 1 and r["withheld"] == ["near"]
    # the squads are still known, nobody of squad A is credited with a touch
    assert [p["near_team"] for p in result["points"]] == ["A", "A"]
    credited = {t["player"] for p in result["points"] for t in p["touches"] if t["player"]}
    assert credited and not any(c.endswith("A") for c in credited if c.startswith("P"))


def test_labels_parse_only_as_two_squads_of_two():
    assert identity.parse_players(PLAYERS) is not None
    assert identity.parse_players(["P1A", "P2A", "P1B"]) is None
    assert identity.parse_players(["P1A", "P1A", "P1B", "P2B"]) is None
    assert identity.parse_players(None) is None


# --------------------------------------------------------------------------- #
# the dump: what the causal pass leaves for this read
# --------------------------------------------------------------------------- #

def test_diag_rows_carry_the_resolvers_similarities(tmp_path):
    from types import SimpleNamespace

    from src.analysis.frame_processor import FrameProcessor
    from src.postrun.stream import load_stream
    from src.tracking.identity_resolver import BodyObs
    from src.utils.diagnostics import DiagRecorder

    box_a, box_b, box_c = [10.0, 20.0, 50.0, 120.0], [200.0, 30.0, 240.0, 130.0], [
        300.0, 30.0, 340.0, 130.0]
    resolver = SimpleNamespace(
        players=[SimpleNamespace(label=lab) for lab in PLAYERS],
        last_observations=[
            BodyObs(tid=1, bbox=box_a, side="near", anchor_sims=[0.91234, 0.8, 0.5, 0.4]),
            BodyObs(tid=2, bbox=box_b, side="far"),                    # not a clean body
            BodyObs(tid=3, bbox=[0.0, 0.0, 9.0, 9.0], side="far",      # another frame's box
                    anchor_sims=[0.1, 0.2, 0.3, 0.4]),
        ])
    fp = FrameProcessor.__new__(FrameProcessor)
    fp.diag = DiagRecorder(str(tmp_path / "diag.jsonl"), fps=30.0)
    fp.player_tracker = SimpleNamespace(team_identity=resolver)
    players = [{"track_id": 1, "bbox": box_a}, {"track_id": 2, "bbox": box_b},
               {"track_id": 3, "bbox": box_c}]
    sims = fp._identity_similarities(players)
    assert sims == {0: [0.9123, 0.8, 0.5, 0.4]}
    fp.diag.add_frame(0, {"players": [dict(p, **({"id_sims": sims[i]} if i in sims else {}))
                                      for i, p in enumerate(players)]})
    stream = load_stream(fp.diag.write())
    assert stream.schema_version == 5 and stream.identity_players == PLAYERS
    assert stream.has_identity_observations
    assert [p.id_sims for p in stream.players[0]] == [(0.9123, 0.8, 0.5, 0.4), None, None]


def test_thumbnails_take_the_box_the_read_labelled(tmp_path):
    """A slot's thumbnail is cut at the box the reconstruction credited, not
    at the one the causal pass called by that name."""
    import json

    from src.publish import thumbs

    b = _match(["near", "far", "near", "far"], switch_after=(2,))
    stream = b.build()
    truth = observe(stream)
    recon = json.loads(json.dumps(reconstruct(stream, b.g, switch_every=2)))
    calibration = tmp_path / "cal.json"
    calibration.write_text(json.dumps({"court_corners": sim.CORNERS,
                                       "net_top_points": sim.NET_TOP}))
    recon["inputs"] = {"calibration": str(calibration)}
    # a dump as the causal pass wrote it: stale labels after the switch
    raw = b.build()
    observe(raw)
    diag = tmp_path / "diag.jsonl"
    with open(diag, "w") as f:
        f.write(json.dumps({"meta": {"schema_version": 5, "fps": sim.FPS,
                                     "identity_players": PLAYERS}}) + "\n")
        for i, row in enumerate(raw.players):
            f.write(json.dumps({"frame": i, "players": [
                {"track_id": p.track_id, "bbox": list(p.bbox), "predicted": False,
                 "team": "A" if p.court_side == "near" else "B",
                 "player_label": p.label, "squad": p.squad, "slot": p.slot,
                 "id_sims": list(p.id_sims)} for p in row]}) + "\n")
    last = recon["points"][-1]
    touch = next(t for t in last["touches"] if t["player"] and t["observed"])
    boxes = thumbs._boxes(diag, {touch["player"]: [touch["frame"]]}, recon)
    frame, bbox = boxes[(touch["player"], touch["frame"])]
    owner = next(p.track_id for p in raw.players[frame] if tuple(p.bbox) == tuple(bbox))
    assert truth[frame][owner] == touch["player"]
