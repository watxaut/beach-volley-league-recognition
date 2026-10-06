"""Bit-exact, cheaper execution of an ultralytics detection model.

Why this exists (measured 2026-10-06, M3 Pro / MPS, imgsz 1280): the network
forward of one detector is ~11 ms, yet ``model(frame)`` costs 20-28 ms. The
rest is per-call source setup and, above all, post-processing: ultralytics
runs NMS and box rescaling as a few dozen tiny device ops that each force a
GPU sync (10-20 ms/frame for the two detectors), where the same code takes
3 ms on the CPU.

``YoloInference`` returns exactly the boxes the public call returns. It runs
the predictor's OWN stage methods (preprocess -> forward -> postprocess;
nothing is re-implemented) and changes one thing: on MPS the head output is
copied to the CPU and post-processed there -- but only on frames where that
provably cannot change the answer:

* Box arithmetic (xywh -> xyxy, un-letterbox, clip) is elementwise IEEE
  float32. The device is checked once per geometry, bit for bit, against the
  CPU on a fixed probe; a mismatch keeps post-processing on the device.
* Which boxes survive is decided by comparisons, which are device-independent
  unless one sits on a rounding boundary. A frame takes the CPU path only when
  no candidate pair's IoU is within ``IOU_MARGIN`` of the NMS threshold
  (float32 IoU error is ~1e-6) and no score or class maximum is tied. Every
  other frame (~0.6 %) is post-processed on the device, as the public call does.

Anything else -- another backend or task, an ultralytics release this was not
verified on, predict arguments changed behind our back -- runs the plain public
call. ``tests/test_yolo_inference.py`` pins the equivalence.
"""

import logging
from typing import Any, Dict, Optional, Tuple

import numpy as np
import torch
import ultralytics
from ultralytics.models.yolo.detect import DetectionPredictor
from ultralytics.utils import ops

logger = logging.getLogger(__name__)

# The stage methods are ultralytics internals: the fast path is enabled only on
# releases where it has been shown bit-identical to the public call.
VERIFIED_ULTRALYTICS = ("8.3.169",)
# Distance from the NMS IoU threshold under which a suppress decision is not
# trusted across implementations (~100x the float32 error of an IoU).
IOU_MARGIN = 1e-4
# ops.non_max_suppression's class offset (its ``max_wh`` default).
NMS_CLASS_OFFSET = 7680.0
# Above this many candidates the pairwise check is not worth its cost.
MAX_CHECKED_CANDIDATES = 512
_PROBE_BOXES = 4096


def boxes_array(results) -> np.ndarray:
    """ultralytics ``Results`` -> (N, 6) float32 rows ``x1, y1, x2, y2, conf, cls``."""
    rows = [r.boxes.data for r in results if r.boxes is not None]
    if not rows:
        return np.empty((0, 6), dtype=np.float32)
    data = rows[0] if len(rows) == 1 else torch.cat(rows)
    return data.cpu().numpy()


def device_arithmetic_matches_cpu(device, input_shape: Tuple[int, int],
                                  frame_shape: Tuple[int, ...]) -> bool:
    """Does the device compute the post-processing box arithmetic bit-for-bit
    like the CPU, for this letterbox geometry?"""
    height, width = input_shape
    rng = np.random.RandomState(0)
    xywh = (rng.uniform(0.0, 1.0, size=(_PROBE_BOXES, 4))
            * [width, height, width, height]).astype(np.float32)
    probe = torch.from_numpy(xywh)

    def box_math(boxes):
        return ops.scale_boxes(input_shape, ops.xywh2xyxy(boxes), frame_shape)

    return torch.equal(box_math(probe), box_math(probe.to(device)).cpu())


def selection_is_implementation_independent(head: torch.Tensor, conf_thres: float,
                                            iou_thres: float) -> bool:
    """True when NMS over this head output keeps the same boxes, in the same
    order, on any correct implementation.

    ``head`` is the raw detection head on the CPU, shape (1, 4 + classes,
    anchors), boxes still ``cx, cy, w, h``. Conservative: False means "not
    proven", never "different".
    """
    scores = head[0, 4:]
    best = scores.amax(0)
    candidates = best > conf_thres
    n = int(candidates.sum())
    if n == 0:
        return True
    if n > MAX_CHECKED_CANDIDATES:
        return False
    class_scores = scores[:, candidates].numpy()
    conf = best[candidates].numpy()
    if int((class_scores == conf).sum(0).max()) > 1:
        return False  # tied class maximum: argmax is implementation-defined
    if n == 1:
        return True
    if np.unique(conf).size != n:
        return False  # tied scores: NMS visiting order is implementation-defined
    # The boxes exactly as NMS sees them (float32 xyxy + per-class offset),
    # then IoU in float64 as the reference value of what it computes.
    cxcywh = head[0, :4][:, candidates].numpy()
    half = cxcywh[2:] / np.float32(2)
    offset = class_scores.argmax(0).astype(np.float32) * np.float32(NMS_CLASS_OFFSET)
    x1, y1 = (cxcywh[:2] - half + offset).astype(np.float64)
    x2, y2 = (cxcywh[:2] + half + offset).astype(np.float64)
    area = (x2 - x1) * (y2 - y1)
    inter = (
        np.clip(np.minimum(x2[:, None], x2) - np.maximum(x1[:, None], x1), 0.0, None)
        * np.clip(np.minimum(y2[:, None], y2) - np.maximum(y1[:, None], y1), 0.0, None)
    )
    with np.errstate(divide="ignore", invalid="ignore"):
        iou = inter / (area[:, None] + area - inter)
    pairs = np.triu_indices(n, 1)
    # A degenerate pair (0/0 -> NaN) compares False here, i.e. "not proven".
    return bool(np.all(np.abs(iou[pairs] - iou_thres) > IOU_MARGIN))


class YoloInference:
    """``model(frame, **predict_kwargs)`` reduced to its boxes, bit for bit.

    Not re-entrant: use one instance from one thread at a time (one worker per
    detector is what ``FramePrefetcher`` does).
    """

    def __init__(self, model, fast: bool = True):
        self.model = model
        self.fast = fast
        # Frames by route: stage methods with CPU post-processing, stage
        # methods with device post-processing, the plain public call.
        self.stats = {"cpu_post": 0, "device_post": 0, "public": 0}
        self._predictor = None
        self._predict_kwargs: Optional[Dict[str, Any]] = None
        self._predictor_args: Optional[Dict[str, Any]] = None
        self._arithmetic_ok: Dict[Tuple, bool] = {}

    def __call__(self, frame: np.ndarray, **predict_kwargs) -> np.ndarray:
        """Boxes of one BGR frame: (N, 6) float32 ``x1, y1, x2, y2, conf, cls``."""
        if self._stages_apply(frame, predict_kwargs):
            return self._run_stages(frame)
        boxes = boxes_array(self.model(frame, verbose=False, **predict_kwargs))
        self.stats["public"] += 1
        if self.fast:
            self._adopt_predictor(predict_kwargs)
        return boxes

    # -- public call -> stage methods handover -------------------------------

    def _adopt_predictor(self, predict_kwargs: Dict[str, Any]) -> None:
        """After a public call: remember the predictor it configured, if the
        stage methods are known to reproduce it."""
        self._predictor = None
        predictor = getattr(self.model, "predictor", None)
        if type(predictor) is not DetectionPredictor:
            return
        if ultralytics.__version__ not in VERIFIED_ULTRALYTICS:
            logger.info(
                "ultralytics %s is not a verified release (%s): detector fast "
                "path off, using the public call",
                ultralytics.__version__, ", ".join(VERIFIED_ULTRALYTICS))
            self.fast = False
            return
        args, backend = predictor.args, predictor.model
        plain_detect = (
            getattr(backend, "pt", False)
            and not getattr(backend, "fp16", False)
            and not getattr(backend, "end2end", False)
            and args.task == "detect"
            and not (args.augment or args.visualize or args.agnostic_nms)
            and args.embed is None
            and not (args.verbose or args.save or args.save_txt or args.show)
            and getattr(predictor, "_feats", None) is None
            and predictor.batch is not None and len(predictor.batch[0]) == 1
        )
        if plain_detect:
            self._predictor = predictor
            self._predict_kwargs = dict(predict_kwargs)
            self._predictor_args = dict(vars(args))

    def _stages_apply(self, frame, predict_kwargs: Dict[str, Any]) -> bool:
        """The predictor is still configured exactly as the public call left it."""
        predictor = self._predictor
        return (
            predictor is not None
            and predictor is getattr(self.model, "predictor", None)
            and predict_kwargs == self._predict_kwargs
            and vars(predictor.args) == self._predictor_args
            and isinstance(frame, np.ndarray) and frame.dtype == np.uint8
            and frame.ndim == 3 and frame.shape[2] == 3
        )

    # -- stage methods ---------------------------------------------------------

    def _run_stages(self, frame: np.ndarray) -> np.ndarray:
        predictor = self._predictor
        with torch.inference_mode():
            im = predictor.preprocess([frame])
            preds = predictor.inference(im)
            head = preds[0] if isinstance(preds, (list, tuple)) else preds
            if head.device.type == "mps":
                cpu_head = head.cpu()
                if self._cpu_postprocess_is_exact(cpu_head, im, frame):
                    self.stats["cpu_post"] += 1
                    return boxes_array(predictor.postprocess(cpu_head, im, [frame]))
            self.stats["device_post"] += 1
            return boxes_array(predictor.postprocess(preds, im, [frame]))

    def _cpu_postprocess_is_exact(self, cpu_head: torch.Tensor, im: torch.Tensor,
                                  frame: np.ndarray) -> bool:
        geometry = (tuple(im.shape[2:]), tuple(frame.shape))
        ok = self._arithmetic_ok.get(geometry)
        if ok is None:
            ok = self._arithmetic_ok[geometry] = device_arithmetic_matches_cpu(
                im.device, *geometry)
            if not ok:
                logger.warning(
                    "%s box arithmetic differs from the CPU for %s: detector "
                    "post-processing stays on the device", im.device, geometry)
        args = self._predictor.args
        return ok and selection_is_implementation_independent(cpu_head, args.conf, args.iou)
