#!/usr/bin/env python3
"""Replay the identity decision offline from a probe feature dump.

``scripts/probe_identity_switches.py`` saves, next to its record, every
MEASURED body per frame (``identity_features.npz``: descriptor, side,
eligibility, height, plus the enrollment samples) -- exactly what
``TeamIdentityResolver.update_observed`` reads. This script re-runs that
decision layer over the dump, so the resolver can be changed and re-tuned
without the video, the detector weights or a 30-minute production pass, and
scores the replay with the probe's own scorer (orientation at GT contacts,
flips per switch window, action attribution vs the legacy labels the probe
recorded).

The tracker is not replayed (it is unchanged by the resolver), so the
track ids, actions and legacy labels of the probe record stay valid.

Usage::

    venv/bin/python scripts/replay_identity.py \\
        output/identity_probe/20260920_match_ari_joan_lost/identity_features.npz \\
        --contacts-gt ground_truth/20260920_match_contacts.json \\
        --set switch_threshold=12 --set LEVEL_ALPHA=0.001
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import probe_identity_switches as probe  # noqa: E402
from src.tracking.identity_resolver import TeamIdentityResolver  # noqa: E402

_CTOR_KWARGS = ("switch_threshold", "switch_temper", "min_switch_interval_frames",
                "court_slack_px", "serve_zone_eligible")


def parse_overrides(items: Sequence[str]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """``NAME=VALUE`` -> (constructor kwargs, class-constant overrides)."""
    kwargs: Dict[str, Any] = {}
    consts: Dict[str, Any] = {}
    for item in items or []:
        name, _, raw = item.partition("=")
        name = name.strip()
        try:
            value = ast.literal_eval(raw.strip())
        except (ValueError, SyntaxError):
            value = raw.strip()
        if name in _CTOR_KWARGS:
            kwargs[name] = value
        elif name.isupper() and hasattr(TeamIdentityResolver, name):
            consts[name] = value
        else:
            raise SystemExit(f"unknown override {name!r}")
    return kwargs, consts


def build_resolver(refs, kwargs: Dict[str, Any], consts: Dict[str, Any]) -> TeamIdentityResolver:
    cls = type("TunedResolver", (TeamIdentityResolver,), dict(consts)) if consts else TeamIdentityResolver
    return cls(refs, None, **kwargs)


def replay(features_path, record: Optional[Dict[str, Any]] = None,
           kwargs: Optional[Dict[str, Any]] = None, consts: Optional[Dict[str, Any]] = None,
           ) -> Tuple[Dict[str, Any], TeamIdentityResolver]:
    """Re-run the decision over a dump; returns (probe-format record, resolver)."""
    meta, refs, frames = probe.load_features(features_path)
    res = build_resolver(refs, kwargs or {}, consts or {})
    legacy: Dict[Tuple[int, int], Optional[str]] = {}
    for f in (record or {}).get("frames", []):
        for body in f["bodies"]:
            legacy[(int(f["frame"]), body[0])] = body[2]
    out: Dict[str, Any] = {"video": (record or {}).get("video"), "fps": meta["fps"],
                           "frames": [], "actions": [], "flips": [],
                           "enrolled": [r["label"] for r in meta["refs"]]}
    labels_at: List[Dict[int, Optional[str]]] = []
    for frame in range(int(meta["n_frames"])):
        obs = frames.get(frame, [])
        labels = res.update_observed(frame, obs)
        st = res.state()
        labels_at.append({tid: lab[0] for tid, lab in labels.items()})
        bodies = []
        for o in obs:
            if o.predicted:
                continue
            lab = labels.get(o.tid)
            side = {"near": "A", "far": "B"}.get(o.side)
            bodies.append([o.tid, lab[0] if lab else None, legacy.get((frame, o.tid)), side,
                           *[int(round(v)) for v in o.bbox]])
        out["frames"].append({
            "frame": frame, "near_squad": st["near_squad"], "cusum": st["cusum"],
            "x_near": st["x_near"], "x_far": st["x_far"], "doubt": st["doubt"],
            "bodies": bodies,
        })
    for a in (record or {}).get("actions", []):
        tid, f, seen = a.get("track_id"), int(a["frame"]), int(a.get("seen_at", a["frame"]))
        lab = None
        for at in (f, seen):   # the contact frame, then the emission frame
            if 0 <= at < len(labels_at) and labels_at[at].get(tid):
                lab = labels_at[at][tid]
                break
        out["actions"].append(dict(a, label=lab))
    out["flips"] = list(res.flips)
    out["learned"] = res.state()["learned"]
    out["separability"] = res.state()["separability"]
    return out, res


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("features", help="identity_features.npz from the probe")
    ap.add_argument("--record", default=None,
                    help="the probe's identity_probe.json (default: next to the dump)")
    ap.add_argument("--contacts-gt", default=None, help="match-contacts-v1 GT JSON")
    ap.add_argument("--set", action="append", default=[], metavar="NAME=VALUE",
                    help="override a resolver kwarg or class constant (repeatable)")
    ap.add_argument("--out", default=None, help="write the replay report JSON here")
    args = ap.parse_args(argv)

    features = Path(args.features)
    record_path = Path(args.record) if args.record else features.parent / "identity_probe.json"
    record = json.loads(record_path.read_text()) if record_path.exists() else None
    if record is None:
        print(f"note: no probe record at {record_path} -- actions/legacy not scored")
    kwargs, consts = parse_overrides(args.set)
    if kwargs or consts:
        print(f"overrides: {kwargs} {consts}")
    replayed, _ = replay(features, record, kwargs, consts)
    gt = json.loads(Path(args.contacts_gt).read_text()) if args.contacts_gt else None
    report = probe.print_report(replayed, gt)
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=1))
        print(f"\nreport: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
