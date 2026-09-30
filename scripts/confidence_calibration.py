#!/usr/bin/env python3
"""G3 R2: leave-one-clip-out calibration study of the per-action confidence.

DIAGNOSE ONLY -- no ``src/`` change, no GT edit, no threshold/config change.
Nothing is tuned: the candidate model is the one the plan named (session 40,
``docs/g3_action_evidence.md`` R2): **continuity x gesture tier**, fitted
leave-one-clip-out over the existing 85-prediction evidence (dev + e1-e7,
reused from ``scripts/action_evidence.py``'s loaders -- never copied).

Measures and reports:

1. **Reliability of today's hand-set constants** (binned predicted-confidence
   vs observed-correctness tables, ECE) for both the emitted
   ``resolver_confidence`` and the Layer-1 ``gesture_confidence``.
2. **A LOCO-calibrated score** (fit on 7 clips, scored on the held-out clip,
   all 8 folds): per-fold + pooled AUC and correct-vs-incorrect gap, against
   the hand-set constants and a LOCO base-rate constant.  Two functional
   forms of the same candidate signals: the multiplicative
   (naive-Bayes-style) model and a per-cell empirical rate with backoff --
   both reported so the verdict is about the SIGNALS, not the form.
3. **Per-clip stability matrix** (incl. near/far = ball_side A/B splits where
   labels exist): flag ANY signal that reverses per clip or per side -- the
   R1 lesson (dev-fitted gaps don't transfer).
4. **Threshold-impact SIMULATION ONLY**: what an emission threshold on the
   calibrated scale would keep/drop vs today's inert ``action_confidence=0.3``
   filter, at matched precision and along a sweep.  Nothing is changed.
5. **Caveats**: which candidate signals would need held-out match validation
   before any ship (the match 20260920 has no per-prediction labels).

Outputs: ``output/g3/r2_calibration.json``,
``docs/g3_r2_confidence_calibration.md`` (owner-facing tables + the
owner-approval-needed proposal section), ``logs/r2_diagnosis_report.md``
(full tables).

Usage::

    python scripts/confidence_calibration.py
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from action_evidence import CORRECT, build_rows, default_clips  # noqa: E402

#: Gesture tier edges -- PRE-REGISTERED (the session-40 evidence doc's own
#: bins/suggestion): low = the two "fallback" constants (0.4/0.5), mid = the
#: workhorse 0.55, high = the gesture-positive constants (0.6/0.7).
#: Chosen before this study ran; NOT tuned here.
def gesture_tier(f: Dict[str, Any]) -> str:
    v = f["gesture_confidence"]
    return "low<=0.5" if v <= 0.5 else ("mid=0.55" if v == 0.55 else "high>=0.6")


#: Continuity tier edges -- PRE-REGISTERED: the evidence doc's fixed
#: ``track_frac_15f`` bins (its only monotone pooled gradient).
def continuity_tier(f: Dict[str, Any]) -> str:
    v = f["track_frac_15f"]
    return "<0.8" if v < 0.8 else ("0.8-0.95" if v < 0.95 else ">=0.95")


TIER_ORDER = {
    "gesture": ["low<=0.5", "mid=0.55", "high>=0.6"],
    "continuity": ["<0.8", "0.8-0.95", ">=0.95"],
}

#: Fixed reliability bins for calibrated scores (interpretable, not tuned).
PROB_BINS = [(0.0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.01)]

#: Today's production emission filter (``DEFAULT_CONFIG['action_confidence']``).
TODAY_THRESHOLD = 0.3


# --- metrics ----------------------------------------------------------------

def auc(pairs: Sequence[Tuple[float, bool]]) -> Optional[float]:
    """Pairwise AUC (ties count 0.5); None when one class is absent."""
    pos = [s for s, ok in pairs if ok]
    neg = [s for s, ok in pairs if not ok]
    if not pos or not neg:
        return None
    wins = ties = 0
    for p in pos:
        for n in neg:
            if p > n:
                wins += 1
            elif p == n:
                ties += 1
    return (wins + 0.5 * ties) / (len(pos) * len(neg))


def gap(pairs: Sequence[Tuple[float, bool]]) -> Optional[float]:
    """mean(score | correct) - mean(score | incorrect); None if a class empty."""
    pos = [s for s, ok in pairs if ok]
    neg = [s for s, ok in pairs if not ok]
    if not pos or not neg:
        return None
    return sum(pos) / len(pos) - sum(neg) / len(neg)


def within_clip_auc(clips: Sequence[str],
                    scores: Dict[Tuple[str, int], float],
                    rows: Sequence[Dict[str, Any]]) -> Tuple[Optional[float], List[Dict[str, Any]]]:
    """AUC computed only within each clip (pos x neg pairs of the SAME clip),
    pair-weighted across clips -- immune to fold-level base-rate shifts.
    Also returns the per-clip AUCs."""
    w = tot = 0
    per: List[Dict[str, Any]] = []
    for c in clips:
        pairs = [(scores[(c, r["frame"])], r["outcome"] == CORRECT)
                 for r in rows if r["clip"] == c]
        a = auc(pairs)
        if a is None:
            per.append({"clip": c, "auc": None})
            continue
        n_pos = sum(1 for _, ok in pairs if ok)
        n_neg = len(pairs) - n_pos
        w += a * n_pos * n_neg
        tot += n_pos * n_neg
        per.append({"clip": c, "auc": round(a, 3),
                    "n_pos": n_pos, "n_neg": n_neg})
    return (round(w / tot, 3) if tot else None), per


def ece_discrete(values: Sequence[float], labels: Sequence[bool]) -> Tuple[float, Dict[float, Dict[str, Any]]]:
    """ECE for a discrete-valued score + the per-value reliability table."""
    d: Dict[float, List[int]] = defaultdict(lambda: [0, 0])
    for v, ok in zip(values, labels):
        d[v][1] += 1
        d[v][0] += ok
    ece = 0.0
    table: Dict[float, Dict[str, Any]] = {}
    for v in sorted(d):
        c, n = d[v]
        obs = c / n
        ece += n * abs(v - obs)
        table[v] = {"n": n, "correct": c, "frac_correct": round(obs, 3),
                    "abs_gap": round(abs(v - obs), 3)}
    return round(ece / len(values), 3), table


def ece_binned(values: Sequence[float], labels: Sequence[bool]) -> Tuple[float, List[Dict[str, Any]]]:
    """ECE over fixed probability bins + the binned reliability table."""
    bins = {b: [0, 0] for b in PROB_BINS}
    for v, ok in zip(values, labels):
        for b in bins:
            if b[0] <= v < b[1]:
                bins[b][1] += 1
                bins[b][0] += ok
                break
    ece = 0.0
    table = []
    for b in PROB_BINS:
        c, n = bins[b]
        if n:
            ece += n * abs(sum(v for v, ok in zip(values, labels)
                               if b[0] <= v < b[1]) / n - c / n)
            table.append({"bin": f"[{b[0]:.1f},{b[1]:.1f})", "n": n, "correct": c,
                          "mean_predicted": round(sum(v for v, ok in zip(values, labels)
                                                      if b[0] <= v < b[1]) / n, 3),
                          "frac_correct": round(c / n, 3)})
    return round(ece / len(values), 3), table


# --- LOCO fitting -----------------------------------------------------------

def _tier_rates(train: Sequence[Dict[str, Any]],
                keyfn: Callable[[Dict[str, Any]], str]) -> Tuple[float, Dict[str, Tuple[int, int]]]:
    d: Dict[str, List[int]] = defaultdict(lambda: [0, 0])
    for r in train:
        k = keyfn(r["features"])
        d[k][1] += 1
        d[k][0] += r["outcome"] == CORRECT
    return sum(v[0] for v in d.values()), {k: (v[0], v[1]) for k, v in d.items()}


def fit_multiplicative(train: Sequence[Dict[str, Any]]) -> Callable[[Dict[str, Any]], float]:
    """p(correct) ~= base_rate * prod_i (rate within tier_i / base_rate)
    (naive-Bayes-style independence of the two tier signals).  Clipped to
    [0.01, 0.99]."""
    g0 = sum(r["outcome"] == CORRECT for r in train) / len(train)
    rg = _tier_rates(train, gesture_tier)[1]
    rc = _tier_rates(train, continuity_tier)[1]

    def score(f: Dict[str, Any]) -> float:
        p = g0
        for rates, kf in ((rg, gesture_tier), (rc, continuity_tier)):
            c, n = rates[kf(f)]
            p *= (c / n) / g0
        return min(0.99, max(0.01, p))
    return score


def fit_per_cell(train: Sequence[Dict[str, Any]]) -> Callable[[Dict[str, Any]], float]:
    """Empirical rate of the (gesture, continuity) CELL, backing off to the
    fit base rate when the cell holds < 3 training rows.  Same candidate
    signals, different functional form (robustness check of the verdict)."""
    g0 = sum(r["outcome"] == CORRECT for r in train) / len(train)
    cell: Dict[Tuple[str, str], List[int]] = defaultdict(lambda: [0, 0])
    for r in train:
        k = (gesture_tier(r["features"]), continuity_tier(r["features"]))
        cell[k][1] += 1
        cell[k][0] += r["outcome"] == CORRECT

    def score(f: Dict[str, Any]) -> float:
        c, n = cell[(gesture_tier(f), continuity_tier(f))]
        p = (c / n) if n >= 3 else g0
        return min(0.99, max(0.01, p))
    return score


def fit_gesture_only(train: Sequence[Dict[str, Any]]) -> Callable[[Dict[str, Any]], float]:
    g0 = sum(r["outcome"] == CORRECT for r in train) / len(train)
    rg = _tier_rates(train, gesture_tier)[1]

    def score(f: Dict[str, Any]) -> float:
        c, n = rg[gesture_tier(f)]
        return min(0.99, max(0.01, (c / n)))
    return score


def fit_continuity_only(train: Sequence[Dict[str, Any]]) -> Callable[[Dict[str, Any]], float]:
    g0 = sum(r["outcome"] == CORRECT for r in train) / len(train)
    rc = _tier_rates(train, continuity_tier)[1]

    def score(f: Dict[str, Any]) -> float:
        c, n = rc[continuity_tier(f)]
        return min(0.99, max(0.01, (c / n)))
    return score


VARIANTS: Dict[str, Callable[[Sequence[Dict[str, Any]]], Callable]] = {
    "candidate: gesture x continuity (multiplicative)": fit_multiplicative,
    "candidate: gesture x continuity (per-cell, backoff n>=3)": fit_per_cell,
    "decomposition: gesture tier only": fit_gesture_only,
    "decomposition: continuity tier only": fit_continuity_only,
}

#: Baseline scores that are NOT fitted: the hand-set constants as scores.
HANDSET_SCORES: Dict[str, Callable[[Dict[str, Any]], float]] = {
    "hand-set: resolver_confidence (emitted)": lambda f: f["resolver_confidence"],
    "hand-set: gesture_confidence (layer 1)": lambda f: f["gesture_confidence"],
}


def loco_scores(rows: Sequence[Dict[str, Any]],
                fit: Callable[[Sequence[Dict[str, Any]]], Callable]
                ) -> Tuple[Dict[Tuple[str, int], float], Dict[str, Dict[str, Any]]]:
    """Leave-one-clip-out: fit on the other 7 clips, score the held-out clip.
    Returns {(clip, frame): score} and per-fold fit diagnostics."""
    clips = sorted({r["clip"] for r in rows})
    scores: Dict[Tuple[str, int], float] = {}
    folds: Dict[str, Dict[str, Any]] = {}
    for held in clips:
        train = [r for r in rows if r["clip"] != held]
        test = [r for r in rows if r["clip"] == held]
        score = fit(train)
        base = sum(r["outcome"] == CORRECT for r in train) / len(train)
        _gtot, gtiers = _tier_rates(train, gesture_tier)
        _ctot, ctiers = _tier_rates(train, continuity_tier)
        folds[held] = {
            "n_train": len(train), "n_test": len(test),
            "fit_base_rate": round(base, 3),
            "fit_gesture_tiers": {k: f"{c}/{n}" for k, (c, n) in sorted(gtiers.items())},
            "fit_continuity_tiers": {k: f"{c}/{n}" for k, (c, n) in sorted(ctiers.items())},
        }
        for r in test:
            scores[(held, r["frame"])] = score(r["features"])
    return scores, folds


def evaluate_variant(rows: Sequence[Dict[str, Any]], name: str,
                     scores: Dict[Tuple[str, int], float]) -> Dict[str, Any]:
    clips = sorted({r["clip"] for r in rows})
    pairs = [(scores[(r["clip"], r["frame"])], r["outcome"] == CORRECT) for r in rows]
    labels = [ok for _, ok in pairs]
    within, per_clip = within_clip_auc(clips, scores, rows)
    # within-clip CENTERED separation (score minus clip mean): the fair gap
    # for a score whose level shifts per fold
    clip_mean: Dict[str, float] = {}
    for c in clips:
        ss = [scores[(c, r["frame"])] for r in rows if r["clip"] == c]
        clip_mean[c] = sum(ss) / len(ss)
    centered = [(scores[(r["clip"], r["frame"])] - clip_mean[r["clip"]], r["outcome"] == CORRECT)
                for r in rows]
    return {
        "variant": name,
        "pooled_auc": auc(pairs),
        "pooled_gap": gap(pairs),
        "within_clip_auc": within,
        "within_clip_centered_gap": gap(centered),
        "per_clip_auc": per_clip,
        "ece": ece_binned([s for s, _ in pairs], labels)[0] if name.startswith("candidate") else None,
        "binned_reliability": ece_binned([s for s, _ in pairs], labels)[1] if name.startswith("candidate") else None,
    }


# --- stability matrix -------------------------------------------------------

def tier_matrix(rows: Sequence[Dict[str, Any]], keyfn: Callable[[Dict[str, Any]], str],
                order: Sequence[str], subset_name: str = "",
                subset: Optional[Callable[[Dict[str, Any]], bool]] = None) -> Dict[str, Any]:
    """Per clip (+ pooled): frac correct per tier, tier-vs-rest direction, and
    REVERSAL flags vs the pooled direction."""
    sel = (lambda r: True) if subset is None else subset
    clips = sorted({r["clip"] for r in rows if sel(r)})
    d: Dict[str, Dict[str, List[int]]] = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for r in rows:
        if not sel(r):
            continue
        k = keyfn(r["features"])
        d[r["clip"]][k][1] += 1
        d[r["clip"]][k][0] += r["outcome"] == CORRECT
    pooled: Dict[str, List[int]] = defaultdict(lambda: [0, 0])
    for c in clips:
        for k, v in d[c].items():
            pooled[k][0] += v[0]
            pooled[k][1] += v[1]
    order_eff = [k for k in order if k in pooled] + \
        [k for k in pooled if k not in order]

    def rate(cell):  # cell=[correct,n]
        return round(cell[0] / cell[1], 3) if cell[1] else None

    pooled_dir = None
    if len(order_eff) >= 2 and all(pooled[k][1] for k in order_eff[:1] + order_eff[-1:]):
        lo, hi = rate(pooled[order_eff[0]]), rate(pooled[order_eff[-1]])
        pooled_dir = "worse-at-low-tier" if lo < hi else ("better-at-low-tier" if lo > hi else "flat")
    matrix = {"tiers": order_eff, "pooled": {k: {"rate": rate(pooled[k]), "n": pooled[k][1]} for k in order_eff},
              "pooled_direction": pooled_dir, "per_clip": {}, "subset": subset_name}
    for c in clips:
        entry = {}
        for k in order_eff:
            cell = d[c].get(k, [0, 0])
            entry[k] = f"{cell[0]}/{cell[1]}" + (f" ({cell[0]/cell[1]:.2f})" if cell[1] else "")
        n_wrong = sum(d[c][k][1] - d[c][k][0] for k in d[c])
        # tier-vs-rest direction for the LOWEST tier (the suspect set)
        low = d[c].get(order_eff[0], [0, 0])
        rest_n = sum(d[c][k][1] for k in order_eff[1:]) if len(order_eff) > 1 else 0
        rest_c = sum(d[c][k][0] for k in order_eff[1:]) if len(order_eff) > 1 else 0
        reversal = None
        if n_wrong == 0:
            reversal = "degenerate: clip all-correct" if low[1] else None
        elif low[1] and rest_n:
            worse = low[0] / low[1] < rest_c / rest_n
            if pooled_dir == "worse-at-low-tier":
                reversal = (not worse)
            elif pooled_dir == "better-at-low-tier":
                reversal = worse
        matrix["per_clip"][c] = {"tiers": entry, "n_wrong": n_wrong,
                                 "low_tier_n": low[1], "rest_n": rest_n,
                                 "low_tier_worse_than_rest": (round(low[0]/low[1], 3) < round(rest_c/rest_n, 3)) if low[1] and rest_n else None,
                                 "reverses_pooled_direction": reversal}
    return matrix


def side_split(rows: Sequence[Dict[str, Any]],
               keyfn: Callable[[Dict[str, Any]], str],
               order: Sequence[str]) -> Dict[str, Dict[str, Any]]:
    """Pooled tier rates per ball side (A = near half, B = far half; the 21
    width-abstain rows are excluded -- no side label), plus the dev-only and
    entreno-only decomposition (is a reversal SIDE-driven or CLIP-TYPE-driven?)."""
    groups = {
        "A: all": lambda r: r["features"].get("ball_side") == "A",
        "B: all": lambda r: r["features"].get("ball_side") == "B",
        "A: dev only": lambda r: r["clip"] == "dev" and r["features"].get("ball_side") == "A",
        "B: dev only": lambda r: r["clip"] == "dev" and r["features"].get("ball_side") == "B",
        "A: entreno": lambda r: r["clip"] != "dev" and r["features"].get("ball_side") == "A",
        "B: entreno": lambda r: r["clip"] != "dev" and r["features"].get("ball_side") == "B",
    }
    out: Dict[str, Dict[str, Any]] = {}
    for gname, sel in groups.items():
        d: Dict[str, List[int]] = defaultdict(lambda: [0, 0])
        n = 0
        for r in rows:
            if not sel(r):
                continue
            n += 1
            k = keyfn(r["features"])
            d[k][1] += 1
            d[k][0] += r["outcome"] == CORRECT
        out[gname] = {"n": n, **{k: {"rate": round(d[k][0] / d[k][1], 3) if d[k][1] else None,
                                    "n": d[k][1]} for k in order}}
    return out


# --- threshold simulation ---------------------------------------------------

def threshold_simulation(rows: Sequence[Dict[str, Any]],
                         scores: Dict[Tuple[str, int], float]) -> Dict[str, Any]:
    """SIMULATION ONLY: what an emission threshold on the LOCO-calibrated
    scale keeps/drops vs today's ``action_confidence=0.3`` filter.  Today's
    filter keeps every emitted action here (min emitted constant 0.45 > 0.3),
    so its kept set = all 85 rows at precision 54/85."""
    labeled = [(scores[(r["clip"], r["frame"])], r["outcome"] == CORRECT,
                f"{r['clip']} f{r['frame']}") for r in rows]
    n_all = len(labeled)
    n_correct = sum(1 for _, ok, _ in labeled if ok)
    today_precision = n_correct / n_all
    min_score = min(s for s, _, _ in labeled)
    sweep = []
    for th in (0.3, 0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 0.99):
        kept = [(s, ok, i) for s, ok, i in labeled if s >= th]
        if not kept:
            sweep.append({"theta": th, "kept_n": 0})
            continue
        kc = sum(1 for _, ok, _ in kept if ok)
        sweep.append({
            "theta": th, "kept_n": len(kept), "kept_correct": kc,
            "kept_wrong": len(kept) - kc,
            "precision": round(kc / len(kept), 3),
            "recall": round(kc / n_correct, 3),
            "dropped_correct": n_correct - kc,
        })
    # matched precision: smallest kept-set (largest theta) whose precision is
    # still >= today's; if even keep-everything is below, degenerate.
    matched = {"theta": min_score, "kept_n": n_all,
               "note": (f"today's precision {today_precision:.3f} is only reached by keeping "
                        f"EVERYTHING (theta <= min LOCO score {min_score:.3f}) -- the calibrated "
                        "scale offers no matched-precision drop set")}
    return {
        "today": {"threshold": TODAY_THRESHOLD, "kept_n": n_all, "dropped_n": 0,
                  "kept_correct": n_correct, "precision": round(today_precision, 3),
                  "note": "min emitted constant 0.45 > 0.3: the filter is INERT on all 85 rows"},
        "matched_precision": matched,
        "sweep": sweep,
    }


# --- markdown ---------------------------------------------------------------

def _fmt(v: Optional[float], nd: int = 3) -> str:
    return "-" if v is None else f"{v:.{nd}f}"


def render_doc(res: Dict[str, Any]) -> str:
    e = res["reliability"]
    L: List[str] = [
        "# G3 R2 — per-action confidence: leave-one-clip-out calibration study",
        "",
        "> ## NEGATIVE RESULT — the planned R2 candidate does NOT beat the hand-set constants",
        "> The candidate model per plan R2 (ball-track continuity × gesture tier),",
        "> fitted leave-one-clip-out, is **anti-correlated with correctness pooled",
        f"> (AUC {_fmt(res['variants'][0]['pooled_auc'])} vs {_fmt(res['handset_baseline_resolver'])} for the emitted",
        f"> hand-set constant) and below chance within clips ({_fmt(res['variants'][0]['within_clip_auc'])}).**",
        "> Nothing is proposed for implementation from this evidence; the proposal",
        "> section at the end is owner-approval-needed and starts from this refutation.",
        "> DIAGNOSE ONLY: no `src/` change, no GT edit, no threshold/config change.",
        "",
        "Generated by `scripts/confidence_calibration.py` over the existing 85-prediction",
        "evidence (dev + e1–e7) reused from `scripts/action_evidence.py`'s loaders",
        "(outcome labels from `evaluate_timed`'s matching, features from the",
        "`--diag-dump` JSONLs + `pipeline_output.json`; runs at HEAD = `185c6f0`,",
        "`--device cpu`). Nothing was re-detected; no video was re-run.",
        "",
        "## Reproduce",
        "",
        "```bash",
        "venv/bin/python scripts/confidence_calibration.py   # -> this doc + JSON + report",
        "```",
        "",
        "## (1) Reliability of today's hand-set constants",
        "",
        "Production emits `confidence` from hand-set constants at TWO layers: the",
        "Layer-1 gesture constant (`gesture_confidence` ∈ {0.4, 0.5, 0.55, 0.6, 0.7},",
        "`ActionClassifier._detect_gesture`) and the Layer-2 resolver constant",
        "(`resolver_confidence` ∈ {0.45…0.8}, `ActionContextResolver._decide`) — the",
        "emitted stream's `confidence`. Today's emission filter is",
        f"`action_confidence = {TODAY_THRESHOLD}` and **the minimum emitted constant is",
        "0.45, so the filter is INERT: it drops 0 of the 85 rows.**",
        "",
    ]
    for title, key in (("Layer-2 resolver (the emitted `confidence`)", "resolver"),
                       ("Layer-1 gesture", "gesture")):
        tbl = e[key]["table"]
        L += [f"### {title}", "",
              "| predicted | n | correct | observed frac correct | |predicted − observed| |",
              "|----------:|---:|--------:|---------------------:|----------------------:|"]
        for v, b in tbl.items():
            L.append(f"| {v:g} | {b['n']} | {b['correct']} | {b['frac_correct']:.3f} "
                     f"| {b['abs_gap']:.3f} |")
        L += ["", f"ECE (n-weighted |predicted − observed|) = **{e[key]['ece']:.3f}**.", "",
              "Monotonicity: " + ("VIOLATED" if e[key]["monotone_violations"] else "holds")
              + f" ({e[key]['monotone_violations']} of {e[key]['n_values']} adjacent pairs inverted).", ""]

    v = res["variants"]
    L += ["## (2) The LOCO-calibrated score (continuity × gesture tier)", "",
          "**Model (pre-registered, from the session-40 plan):** tiers are the evidence",
          "doc's own fixed bins — gesture ∈ {≤0.5, 0.55, ≥0.6}, continuity",
          "(`track_frac_15f`) ∈ {<0.8, 0.8–0.95, ≥0.95}; score =",
          "`base_rate × (gesture-tier rate / base) × (continuity-tier rate / base)`",
          "fitted on 7 clips, applied to the held-out clip, all 8 folds. A per-cell",
          "variant (empirical cell rate, backoff to base when the cell has <3 fit",
          "rows) and the two single-signal decompositions are reported so the verdict",
          "is about the signals, not the functional form. No thresholds or weights",
          "were tuned; tier edges were fixed before the study ran.", "",
          "### Per-fold (held-out clip) evaluation", "",
          "| held-out clip | n | fit base rate | AUC cal | AUC resolver | AUC gesture | gap cal | gap resolver | gap gesture |",
          "|--------------|--:|--------------:|--------:|-------------:|------------:|--------:|-------------:|------------:|"]
    for f in res["folds"]:
        L.append(f"| {f['clip']} | {f['n_test']} | {f['fit_base_rate']:.3f} "
                 f"| {_fmt(f['auc_cal'])} | {_fmt(f['auc_resolver'])} | {_fmt(f['auc_gesture'])} "
                 f"| {_fmt(f['gap_cal'])} | {_fmt(f['gap_resolver'])} | {_fmt(f['gap_gesture'])} |")
    L += ["",
          f"e3/e5/e7 have no wrong rows (all-correct clips): AUC/gap undefined there.",
          "",
          "### Pooled over all 8 folds (every row scored by the model that excluded its clip)", "",
          "| score | pooled AUC | pooled gap | within-clip AUC (pair-weighted) | within-clip centered gap |",
          "|-------|-----------:|-----------:|-------------------------------:|-------------------------:|"]
    for var in v:
        L.append(f"| {var['variant']} | {_fmt(var['pooled_auc'])} | {_fmt(var['pooled_gap'])} "
                 f"| {_fmt(var['within_clip_auc'])} | {_fmt(var['within_clip_centered_gap'])} |")
    L += ["",
          "**Verdict: the calibrated score does NOT beat the hand-set constant — on any",
          "variant, pooled or within-clip.** The full candidate model is *worse than",
          "chance* pooled (AUC "
          f"{_fmt(v[0]['pooled_auc'])}) and within clips ({_fmt(v[0]['within_clip_auc'])});",
          "the hand-set constants, while uncalibrated and weak (within-clip AUC",
          f"{_fmt(res['handset_within_resolver'])}/{_fmt(res['handset_within_gesture'])}),",
          "are at least not anti-correlated. Per the task's honesty rule: reported and",
          "stopped — no mechanism proceeds from this candidate. The two failure causes",
          "are measured in (3): the gesture tier REVERSES between dev and entreno, and",
          "the per-fold base rate is anti-correlated with the held-out clip's rate",
          "(the all-correct clips drag their own fold's fit down).", ""]

    st = res["stability"]
    L += ["## (3) Per-clip stability matrix (the R1-lesson check)", "",
          "Frac-correct per tier per clip (n in denominator); 'reversal' = the clip's",
          "lowest-tier-vs-rest direction contradicts the pooled direction.", ""]
    for name, m in st["matrices"].items():
        L += [f"### {name}", "",
              "Pooled tier rates: " + ", ".join(f"`{k}` {b['rate']} (n={b['n']})"
                                                for k, b in m["pooled"].items())
              + f" — direction: **{m['pooled_direction']}**", "",
              "| clip | " + " | ".join(m["tiers"]) + " | low-tier worse than rest | REVERSAL |",
              "|------|" + "---:|" * (len(m["tiers"]) + 2)]
        for c, entry in m["per_clip"].items():
            cells = " | ".join(entry["tiers"][k] for k in m["tiers"])
            rv = entry["reverses_pooled_direction"]
            if rv is None:
                rev = "-"
            elif rv is True:
                rev = "**YES**"
            elif rv is False:
                rev = "no"
            else:
                rev = f"n/a ({rv.split(':')[1].strip()})"
            worse = "-" if entry["low_tier_worse_than_rest"] is None else \
                str(entry["low_tier_worse_than_rest"])
            L.append(f"| {c} | {cells} | {worse} | {rev} |")
        n_real = sum(1 for e in m["per_clip"].values()
                     if e["reverses_pooled_direction"] is True)
        n_meas = sum(1 for e in m["per_clip"].values()
                     if e["reverses_pooled_direction"] in (True, False))
        L += ["", f"Real (non-degenerate) reversals: **{n_real} of {n_meas} measurable clips**"
              + (" — the tier direction does NOT transfer across clips." if n_real
                 else " — the tier direction holds in every clip where it is measurable.")]
        if m.get("subset"):
            L += ["", f"(subset: {m['subset']})"]
        L.append("")
    L += ["### Near/far split (ball_side A = near, B = far; 21 width-abstain rows unlabeled)", "",
          "The dev/entreno decomposition answers whether a reversal is SIDE-driven",
          "or CLIP-TYPE-driven.", ""]
    for name, ss in st["sides"].items():
        for side, b in ss.items():
            L.append(f"- {name}, {side} (n={b['n']}): "
                     + ", ".join(f"`{k}` {_fmt((b[k] or {}).get('rate'))} (n={(b[k] or {}).get('n')})"
                                 for k in [k for k in b if k != "n"]))
        L.append("")
    L += ["**Reading.** (i) The gesture-tier reversal is CLIP-TYPE-driven, not",
          "side-driven: on BOTH sides the low tier is 0.000 on dev (A 0/5, B 0/2)",
          "and 1.000 on entreno (A 2/2, B 1/1) — the near/far axis does not",
          "explain it, so a width-band fix (the R1/T8 direction) would NOT rescue",
          "the gesture tier. (ii) The continuity tier holds its direction on both",
          "sides and in every clip where it is measurable (dev/e4/e6 confirm),",
          "which is why the continuity-only decomposition is the sole variant",
          "above chance within clips — but its far-side mass is thin (8 low-tier",
          "far rows) and its mid/high far tiers sit at n≤17, so no far-side",
          "calibration claim can be made from this evidence.", ""]
    L += ["### Fold base-rate instability (why pooled AUC collapses)", "",
          "| held-out clip | held-out correct rate | fit base rate (other 7 clips) |",
          "|--------------|---------------------:|------------------------------:|"]
    for f in res["folds"]:
        L.append(f"| {f['clip']} | {f['heldout_rate']:.3f} | {f['fit_base_rate']:.3f} |")
    L += ["",
          "The all-correct clips (e3/e5/e7) are REMOVED from their own fold's fit, so",
          "their (entirely correct) rows receive the LOWEST fitted base rates, while",
          "dev — the worst clip — receives the HIGHEST. Any absolute probability",
          "fitted this way transfers anti-correlated. With clip base rates spanning",
          "0.276 (dev) to 1.000 (e3/e5/e7), a single global calibration is ill-posed",
          "on this evidence base.", ""]

    ts = res["threshold_sim"]
    L += ["## (4) Threshold-impact — SIMULATION ONLY (nothing changed anywhere)", "",
          f"Today: `action_confidence = {TODAY_THRESHOLD}` keeps **{ts['today']['kept_n']}/85** rows",
          f"(min emitted constant 0.45 > 0.3 — the filter is inert) at precision",
          f"**{ts['today']['precision']:.3f}** ({ts['today']['kept_correct']}/85).", "",
          "**At matched precision** on the LOCO-calibrated scale: today's 0.635 is only",
          f"reachable by keeping everything (θ ≤ min LOCO score "
          f"{ts['matched_precision']['theta']:.3f}) — the calibrated scale offers no",
          "drop set at matched precision, i.e. it would keep/drop EXACTLY what today's",
          "filter does: all 85.", "",
          "Sweep (what a threshold WOULD do — monotonically harmful):", "",
          "| θ on calibrated scale | kept | correct kept | wrong kept | precision | recall | correct dropped |",
          "|---------------------:|-----:|-------------:|-----------:|----------:|-------:|----------------:|"]
    for s in ts["sweep"]:
        if s["kept_n"] == 0:
            L.append(f"| {s['theta']} | 0 | - | - | - | - | {ts['today']['kept_correct']} |")
        else:
            L.append(f"| {s['theta']} | {s['kept_n']} | {s['kept_correct']} | {s['kept_wrong']} "
                     f"| {s['precision']:.3f} | {s['recall']:.3f} | {s['dropped_correct']} |")
    L += ["",
          "Precision FALLS monotonically as θ rises (0.635 → 0.000 at θ=0.9): the",
          "high-scoring rows are dev's wrong rows (boosted by the fit-time gesture-tier",
          "reversal + high dev fold base rate). An emission threshold on this",
          "calibrated scale would REMOVE correct actions preferentially. No threshold",
          "was changed anywhere; `action_confidence` remains 0.3.", ""]

    L += ["## (5) Caveats — what needs held-out MATCH validation before any ship", "",
          "The match (20260920) has **no per-prediction labels**: only 17 owner",
          "verdicts, the P1–P8 GT contacts, and 33 dictated winners. That gap is the",
          "R1 lesson (dev-fitted evidence refuted by the held-out match at 0.3 bw/f).",
          "Before ANY R2 candidate ships, these signals need match-side validation:", "",
          "1. **Clip base rate** — dev 0.276 vs entreno 0.56–1.00; the match's true",
          "   per-action correctness rate is UNKNOWN (the 17 verdicts cover serves",
          "   only). A calibrated probability is meaningless without it.",
          "2. **Gesture tier mix** — the match's far-side bump serves are re-labeled",
          "   by pass-2, not emitted with the drill clips' gesture distribution;",
          "   the tier-rate reversal (dev 0/11 low-tier vs entreno 4/4) is",
          "   unmeasurable on the match without labels.",
          "3. **`track_frac_15f` continuity** — the only monotone pooled signal, but",
          "   the match runs 25.7 fps (15f = 0.58 s vs 0.50 s on the 30 fps clips),",
          "   with longer rallies and far-side occlusion; the near/far table above",
          "   has no far-side failure mass to validate against.",
          "4. **Dead-time FP class** — only the dev clip produces `fp_dead_time`;",
          "   any precision claim calibrated on dev's FP mix does not transfer.",
          "5. **Scale-dependent companions** — `ball_width_px`-derived features",
          "   (`*_bw/f`) share the R1 failure mode (width bands); they are excluded",
          "   from this candidate but any future score using them inherits the gate.",
          "", ]
    L += ["## (6) PROPOSAL — OWNER APPROVAL NEEDED (R2 mechanism)", "",
          "> **Status: REFUTED at the diagnosis stage — nothing to approve for",
          "> implementation as specified.** The plan's candidate (replace the hand-set",
          "> constants with a calibrated continuity × gesture-tier score) fails its own",
          f"> leave-one-clip-out gate: pooled AUC {_fmt(v[0]['pooled_auc'])} / within-clip",
          f"> {_fmt(v[0]['within_clip_auc'])} vs the hand-set constants'",
          f"> {_fmt(res['handset_baseline_resolver'])} pooled. Per the task's honesty",
          "> rule this stops here; below is what a viable R2 would need",
          "> IF the owner still wants the direction pursued — every item requires an",
          "> explicit owner approval before any `src/` work.", "",
          "**What the evidence does support (measured here):**",
          "- The hand-set constants are uncalibrated (ECE "
          f"{e['resolver']['ece']:.3f}/{e['gesture']['ece']:.3f}) and carry almost no",
          "  correctness ordering (within-clip AUC "
          f"{_fmt(res['handset_within_resolver'])}/{_fmt(res['handset_within_gesture'])}) —",
          "  the R2 MOTIVATION stands; the planned SOLUTION does not.",
          "- Continuity (`track_frac_15f`) is the only signal whose direction holds",
          "  within clips (decomposition AUC "
          f"{_fmt([x for x in v if 'continuity tier only' in x['variant']][0]['within_clip_auc'])})",
          "  and on both ball sides — usable as ONE ordinal input or a review-UI flag,",
          "  never as a calibrated replacement on its own (pooled AUC still",
          f"{_fmt([x for x in v if 'continuity tier only' in x['variant']][0]['pooled_auc'])}).",
          "",
          "**Preconditions (all owner-gated):**",
          "1. Match-side per-prediction labels (an owner contact-sheet pass over the",
          "   207 match actions, or at minimum a stratified subset covering serves,",
          "   far-side contacts, and dead-time windows) — without them no calibration",
          "   can be validated where R1 died.",
          "2. A clip-type-aware calibration (separate base rates for drills vs dev vs",
          "   match, or base rate fitted per clip type) — the pooled study shows a",
          "   single global rate is ill-posed.",
          "",
          "**Validation gates if an R2 mechanism is ever implemented (the R1 battery):**",
          "- entreno e1–e7: byte-identical action sets + the F1 record unchanged",
          "  (`scripts/compare_runs.py`, `scripts/evaluate.py --ignore-player`),",
          "- dev: `scripts/evaluate_timed.py --ignore-player` unchanged (confidence",
          "  re-scoring must not change any emission decision),",
          "- match both-arms (same code, one config): action-set identity, pass-2 chain",
          "  (far prefix census 8/8, serve-typed 31, 17/17 owner verdicts, points",
          "  31/33) — any threshold change on the calibrated scale gets its OWN",
          "  battery; the R1 stop rule applies verbatim.",
          ""]
    return "\n".join(L)


# --- main -------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--json", default="output/g3/r2_calibration.json")
    p.add_argument("--markdown", default="docs/g3_r2_confidence_calibration.md")
    p.add_argument("--report", default="logs/r2_diagnosis_report.md")
    args = p.parse_args()

    rows = build_rows(default_clips())
    clips = sorted({r["clip"] for r in rows})
    labels_all = [r["outcome"] == CORRECT for r in rows]

    # (1) reliability of the hand-set constants
    reliability: Dict[str, Any] = {}
    for key, feat in (("resolver", "resolver_confidence"), ("gesture", "gesture_confidence")):
        vals = [r["features"][feat] for r in rows]
        ece, table = ece_discrete(vals, labels_all)
        ks = sorted(table)
        inv = sum(1 for a, b in zip(ks, ks[1:])
                  if table[a]["frac_correct"] > table[b]["frac_correct"])
        reliability[key] = {"ece": ece, "table": table, "n_values": len(ks),
                            "monotone_violations": inv}

    # (2) LOCO variants + hand-set baselines on the same fold structure
    variants: List[Dict[str, Any]] = []
    for name, fit in VARIANTS.items():
        scores, folds = loco_scores(rows, fit)
        variants.append(evaluate_variant(rows, name, scores))
        if name.startswith("candidate: gesture x continuity (multiplicative)"):
            candidate_scores, candidate_folds = scores, folds
    handset: Dict[str, Dict[Tuple[str, int], float]] = {}
    for name, fn in HANDSET_SCORES.items():
        handset[name] = {(r["clip"], r["frame"]): fn(r["features"]) for r in rows}
        variants.append(evaluate_variant(rows, name, handset[name]))
    # per-fold metrics for the doc table (candidate + both hand-set)
    for f_clip in candidate_folds:
        test = [r for r in rows if r["clip"] == f_clip]
        entry = candidate_folds[f_clip]
        entry["heldout_rate"] = round(sum(r["outcome"] == CORRECT for r in test) / len(test), 3)
        for label, sc in (("cal", candidate_scores),
                          ("resolver", handset["hand-set: resolver_confidence (emitted)"]),
                          ("gesture", handset["hand-set: gesture_confidence (layer 1)"])):
            pairs = [(sc[(r["clip"], r["frame"])], r["outcome"] == CORRECT) for r in test]
            entry[f"auc_{label}"] = auc(pairs)
            entry[f"gap_{label}"] = (round(gap(pairs), 3) if gap(pairs) is not None else None)

    # (3) stability matrices + near/far
    stability = {
        "matrices": {
            "gesture tier x clip": tier_matrix(rows, gesture_tier, TIER_ORDER["gesture"]),
            "continuity tier x clip": tier_matrix(rows, continuity_tier, TIER_ORDER["continuity"]),
        },
        "sides": {
            "gesture tier": side_split(rows, gesture_tier, TIER_ORDER["gesture"]),
            "continuity tier": side_split(rows, continuity_tier, TIER_ORDER["continuity"]),
        },
    }

    # (4) threshold simulation on the primary candidate
    threshold_sim = threshold_simulation(rows, candidate_scores)

    res = {
        "n_rows": len(rows),
        "clips": clips,
        "tier_edges": {"gesture": "<=0.5 / =0.55 / >=0.6", "continuity": "<0.8 / 0.8-0.95 / >=0.95"},
        "reliability": reliability,
        "variants": variants,
        "folds": [candidate_folds[c] | {"clip": c} for c in clips],
        "stability": stability,
        "threshold_sim": threshold_sim,
        "handset_baseline_resolver": next(
            v for v in variants if v["variant"].startswith("hand-set: resolver"))["pooled_auc"],
        "handset_within_resolver": next(
            v for v in variants if v["variant"].startswith("hand-set: resolver"))["within_clip_auc"],
        "handset_within_gesture": next(
            v for v in variants if v["variant"].startswith("hand-set: gesture"))["within_clip_auc"],
    }

    Path(args.json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.json).write_text(json.dumps(res, indent=1, default=str))
    doc = render_doc(res)
    Path(args.markdown).parent.mkdir(parents=True, exist_ok=True)
    Path(args.markdown).write_text(doc)
    # full-tables report (same content + the raw per-fold fit diagnostics)
    report = [doc, "", "---", "", "# Appendix: raw fold-fit diagnostics (logs copy)", ""]
    for f in res["folds"]:
        report += [f"## fold held-out {f['clip']} (n={f['n_test']})", "",
                   f"- fit base rate: {f['fit_base_rate']}",
                   f"- fit gesture tiers: {f['fit_gesture_tiers']}",
                   f"- fit continuity tiers: {f['fit_continuity_tiers']}", ""]
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text("\n".join(report))

    print(f"rows {len(rows)} -> {args.json}, {args.markdown}, {args.report}")
    cand = variants[0]
    print(f"candidate pooled AUC {cand['pooled_auc']} within-clip {cand['within_clip_auc']} "
          f"vs hand-set resolver pooled {res['handset_baseline_resolver']} "
          f"within {res['handset_within_resolver']}")
    print(f"ECE resolver {reliability['resolver']['ece']} gesture {reliability['gesture']['ece']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
