# Ground Truth Annotation Format

Annotations are stored as JSON files in this directory. Each video gets one JSON file.

## Owner contact dictation (`20260920_match_ari_joan_contacts_*.txt`)

The owner dictates rally CONTACTS in plain text; the file is the source of
truth and `scripts/build_dev_clip_gt.py::parse_contact_gt` transcribes it.
**The 20260920 match file carries the WHOLE match (P1–P33) in TWO line
dialects** — the P1–P8 dialect (session 33) and the P9–P33 dialect (owner,
2026-09-30) — and **both are machine-readable since G0 (2026-10-01)**: 211
contacts (28 P1–P8 + 183 P9–P33). The dev-clip GT
(`video_ari_joan_8_first_points_annotations.json`) is built from dialect A;
the match GT (`20260920_match_contacts.json`, below) from both.

Dialect A (P1–P8):

```
Point 1
Far team P2 serve at f210
Near team P4 dig at f245
Side switch            <- closes the point it follows
```

Dialect B (P9–P33) — every shape below is parsed by the same
`parse_contact_gt`:

```
From now on NT -> Near Team          <- legend prose (ignore)
FT -> Far Team
Point 9
NT serve f5496 P3 (attributed as a spike)      side abbrev, player AFTER frame
f5530 FT P4 returns it on first touch, goes wide     FRAME first, action in prose
FT dig f6065 P4                          side, action, frame, player id
FT bump set f6104 (player not tracked)   player unknown
NT set that overpasses f7320 and scores the point  implicit overpass
NT dig 20951                             missing `f` prefix (3+ lines)
FT dig (occluded and attributed wrong) f16078      parenthetical BEFORE the frame
FT poke on second touch f6320            attack variant wording
NT dig f12160 and overpasses -> overpass            explicit `-> overpass` relabel
NT f23545 touches ball but falls to ground ...      a touch with NO action label
FT is close to a dig in f10180 but the ball falls first ...  PROSE, not a contact
```

Mechanical transcription rules (no owner wording is re-decided):

- `poke` = the soft attack -> GT action `spike` with `spike_type: "touch"`
  (also `spike touch` / `rainbow`); `hard` / `accelerated` -> `spike_type:
  "hard"`.
- `bump set` -> `set` (the bump names the technique); `bump pass(es) (the) ball`
  -> `overpass`; `returns` (a serve reception) -> `dig`.
- Player id: the `P<k>` in the structural slot (after the frame, or before the
  verb in the frame-first form). `"... missatributed to P2, but its P4"`
  yields the TRUE id P4, and the correction stays verbatim in `note` (a
  `P<k>` inside an attribution clause is the pipeline's WRONG id, never GT).
- A frame without the `f` prefix is read as the frame (`NT dig 20951`).
- A line whose side word starts a sentence instead of a verb
  (`FT is close to a dig in f10180 ...`) is owner prose -> `notes`, never a
  contact (open point 25: the owner says that ball must NOT count as a dig).
- `NT f23545 touches ball ...` names a touch but no action: the contact is
  kept with `action: null` + `owner_action_unspecified: true` — a label is
  never invented.
- A wrapped parenthetical (P20 f14518) is joined before parsing; the duplicated
  empty `Point 21` header is merged into P21.

Owner conventions stated in that file (verbatim intent):

- "All actions that overpass label as overpass" — `overpasses` / `-> overpass`
  on a set or dig line makes the GT action `overpass`.
- **"missatr" markers are NOT exhaustive** — a contact without a mis-attribution
  note may still be mis-attributed; never read an unmarked contact as
  guaranteed-correct.
- A **no-touch block is attributed to the player that spikes** (P15 f10158,
  P19 f13397 "missatt as block") — consistent with the standing convention that
  no-touch blocks are physical events the pipeline cannot emit.
- Frames are MATCH frames (same numbering as the serve anchors), coarse ±10–15 f.
- A `player id` is the track id the owner saw AT that contact frame (optional in
  dialect B; absent when "player not tracked").
- Four `Side switch` markers (after P7/14/21/28) match the ratified schedule.
  Team mapping is by PARITY (`_side_to_team`): after the 4 switches `near` is
  Team A again from P29.

## Match contact GT (`20260920_match_contacts.json`, match-contacts-v1)

`scripts/build_match_contact_gt.py` transcribes the whole dictation into a
machine-readable GT JSON on the **MATCH frame axis** (no clip offset: frames
are identical to the serve anchors and every pipeline `frame_number`), plus
`output/match_contact_sheet/P<n>.png` grids and a README index.

```bash
venv/bin/python scripts/build_match_contact_gt.py              # JSON + sheets
venv/bin/python scripts/build_match_contact_gt.py --no-sheets  # JSON only
```

- `points[].contacts` — the parser's verbatim owner fields (side word, track
  id, note, raw line, optional gesture / interpretation flag / spike_type /
  outcome / error).
- `annotated_frames.actions.events` — the evaluator-shaped event list, one per
  contact, `source=owner_gt`, `frame == match_frame`, coarse
  `frame_tolerance=15`; the P30 unknown touch carries `action=null` +
  `owner_action_unspecified=true`.
- `points[].match_start_frame/end_frame` — the episode map's **PREDICTIONS**
  (`window_is_prediction: true`), never ground truth; `--episode-map ""`
  removes them.
- `provenance` carries the 3 preamble `unparsed` lines and the 9 owner
  `notes` lines, so nothing the owner wrote is silently dropped.

## Match Points Ground Truth (`<stem>_match_points.json`, match-points-v1)

For full-match videos the owner dictates a plain-text GT
(e.g. `20260920_match_ari_joan_lost.txt`): one `P<n>: description` line per
point, then a running score table (`A  B` rows) with `Side switch` markers
between rows. `scripts/parse_match_gt_text.py` transcribes it mechanically
into `<stem>_match_points.json` (re-run it after editing the text):

```bash
python scripts/parse_match_gt_text.py ground_truth/20260920_match_ari_joan_lost.txt \
    --out ground_truth/20260920_match_points.json
```

- `winner` is MECHANICAL (which score column incremented) -- descriptions are
  stored verbatim and never parsed; `P<k>` inside a description refers to a
  PLAYER (track id), not a point.
- `side_switch_after: true` on point k means the teams swap halves AFTER that
  point (the next point is played on switched sides).
- Conventions: Team A/B are FIXED SQUADS (A played the near side at match
  start); squads do NOT change at side switches, only their court half does.
- NO frame anchors exist in this format -- score point COUNT with
  `scripts/evaluate_match_points.py`; per-point start alignment needs
  owner-ratified frame anchors first. Winner / side-switch scoring activates
  once the pipeline emits those layers.

## Game-State Ground Truth (`gt_point_start_end.txt`)

For the game on/off state machine there is a plain-text format (owner's
convention, validated on `video_entreno_game_state.mp4`):

> **WARNING: this file anchors `video_entreno_game_state.mp4` ONLY (30fps,
> 4.5 min). Its timestamps are MEANINGLESS for the 20260920 match — never
> pair them with `20260920_match_points.json`. The match has NO frame
> anchors; per-point windows need owner-ratified anchors first.**

```
00:10 point starts
00:18 point stops

00:21 point starts
00:32 point stops
```

- `MM:SS point starts` marks the SERVE moment of a point; `MM:SS point
  stops` marks the ball-death moment (landing / held / settled).
- Whole-second granularity — treat ±15 frames as annotation granularity,
  not machine error.
- Score with `scripts/evaluate_game_state.py` against the
  `game_state.points` key of `pipeline_output.json`.

## File Naming

`{video_name}_annotations.json` -- e.g., `avp_front_1_annotations.json`

## Schema

```json
{
  "video": "path/to/video.mp4",
  "fps": 30.0,
  "resolution": [1920, 1080],
  "annotated_frames": {
    "ball": {
      "description": "Ball center position every 5 frames",
      "frames": {
        "0": {"x": 500, "y": 300, "visible": true},
        "5": {"x": 520, "y": 280, "visible": true},
        "10": null
      }
    },
    "players": {
      "description": "Player bounding boxes + IDs every 10 frames",
      "frames": {
        "0": [
          {"id": 1, "team": "A", "bbox": [100, 200, 160, 400]},
          {"id": 2, "team": "A", "bbox": [300, 210, 360, 410]},
          {"id": 3, "team": "B", "bbox": [600, 190, 660, 390]},
          {"id": 4, "team": "B", "bbox": [800, 200, 860, 400]}
        ]
      }
    },
    "actions": {
      "description": "Action events with frame number, player ID, and type",
      "events": [
        {"frame": 45, "player_id": 1, "action": "serve"},
        {"frame": 78, "player_id": 3, "action": "dig"},
        {"frame": 92, "player_id": 4, "action": "set"},
        {"frame": 105, "player_id": 3, "action": "spike"}
      ]
    }
  },
  "court": {
    "corners": [[x1,y1], [x2,y2], [x3,y3], [x4,y4]],
    "net_posts": [[nx1,ny1], [nx2,ny2]]
  }
}
```

## Field Details

### Ball annotations
- **x, y**: Ball center in pixels
- **visible**: Whether ball is actually visible in the frame
- Annotate every 5 frames. Use `null` for frames where ball is off-screen
- Only annotate frames where you're confident about position

### Player annotations
- **id**: Consistent player ID (1-4) across all frames
- **team**: "A" (left side) or "B" (right side)
- **bbox**: `[x_min, y_min, x_max, y_max]` in pixels
- Annotate every 10 frames

### Action events
- **frame**: Frame number where the action occurs (ball contact frame)
- **player_id**: Which player performed the action (1-4)
- **action**: One of `serve`, `dig`, `set`, `spike`, `block`, `ace`, `kill`
- **Spike events** (optional, entreno_3+) also carry:
  - **spike_type**: `touch` (soft shot / rainbow) or `hard` (driven / accelerated)
  - **attack_zone**: `{"side": "A"|"B", "zone": 1-9}` — the spiker's 3x3 zone on
    their own half. Each half is numbered 1-9 left-to-right as seen standing
    at the net facing that side's OWN baseline (rows: 1-3 at the net, 4-6
    middle, 7-9 back). In the standard camera view (A near/bottom) A's zone 1
    is image-right at the net, B's zone 1 is image-left.
  - **outcome**: `kill`, `out`, `dug`, `blocked`. Kill semantics (owner, 2026-08-31):
    the ball falls directly (no dig), OR is dug and then dies WITHOUT a set —
    falling on the defenders' court or out of bounds. A dig that is kept up
    (a set follows) is `dug`.
  - **landing_zone**: `{"side", "zone"}` for kills — where the ball fell;
    **dug_zone**: `{"side", "zone"}` for digs — where the defender played it

### Court
- **corners**: 4 court corners in pixel coordinates, clockwise from top-left
- **net_posts**: 2 net post positions (left post, right post)

## How Many Annotations Do I Need?

### For Evaluation Only (measuring how well the system works)

| Component | Minimum (good start) | Recommended | What you're annotating |
|---|---|---|---|
| Ball detection | 100 frames (~3s at 30fps) | 300-500 frames (~10-17s) | Ball center position every 5 frames |
| Player tracking | 50 frames | 150-200 frames | Player bounding boxes + IDs every 10 frames |
| Action recognition | 15-20 events | 50-100 events | Each ball contact: frame, player, action type |

**Start here.** Annotate 2-3 short clips (30-60 seconds each) from different rallies. This gives you
enough data to compute detection rates, ID consistency, and action precision/recall -- which tells
you whether code changes are helping or hurting.

### For Fine-Tuning YOLO Ball Detection

If you want to train a custom YOLO model to detect volleyballs better (especially on sand backgrounds):

| Level | Images | Expected improvement |
|---|---|---|
| Minimum viable | 100-200 | Noticeable improvement on your specific court/ball |
| Good | 500-800 | Solid improvement, handles lighting variations |
| Recommended | 1000-1500 | Robust detector for your setup |
| Overkill for personal use | 2000+ | Diminishing returns unless video conditions vary a lot |

**Tips for YOLO fine-tuning annotations:**
- Include frames where the ball is hard to see (fast motion, against sand, partially occluded)
- Include frames without a ball (~20% negatives) so the model learns what's NOT a ball
- Vary lighting conditions, times of day, and ball positions across the court
- Each annotation = a bounding box around the ball in the YOLO format (class x_center y_center width height)

### For Action Recognition Ground Truth

Action events are the most valuable annotations because they're what the system ultimately needs to get right:

- **Minimum**: 15-20 events across 2-3 rallies (enough to see if anything works)
- **Recommended**: 50-100 events covering all action types (serve, dig, set, spike, block)
- **Per-action minimum**: At least 5 examples of each action type you care about

---

## How to Annotate

### Option 1: Roboflow (Recommended for Ball Detection)

[Roboflow](https://roboflow.com) is an excellent choice for annotating ball detections for YOLO fine-tuning.

**Setup:**
1. Create a free Roboflow account (free tier supports up to 10,000 images)
2. Create a new project, select "Object Detection"
3. Upload frames extracted from your videos (see frame extraction below)
4. Draw bounding boxes around the volleyball in each frame
5. Use a single class: `volleyball`

**Exporting from Roboflow:**
- For YOLO fine-tuning: Export in **YOLOv8** format. This gives you the exact format needed to fine-tune
- For our evaluation pipeline: Export in **COCO JSON** format, then convert (see below)

**Extracting frames for Roboflow:**
```bash
# Extract every 5th frame from a video
ffmpeg -i resources/your_video.mp4 -vf "select=not(mod(n\,5))" -vsync vfr frames/frame_%04d.png

# Extract frames from a specific time range (e.g., 30s to 90s)
ffmpeg -i resources/your_video.mp4 -ss 00:00:30 -to 00:01:30 -vf "select=not(mod(n\,5))" -vsync vfr frames/frame_%04d.png
```

**Converting Roboflow COCO JSON to our evaluation format:**
```python
import json

# Load Roboflow COCO export
with open("_annotations.coco.json") as f:
    coco = json.load(f)

# Build our format
our_format = {
    "video": "your_video.mp4",
    "fps": 30.0,
    "resolution": [1920, 1080],
    "annotated_frames": {
        "ball": {"description": "Ball positions", "frames": {}},
        "players": {"description": "Player boxes", "frames": {}},
        "actions": {"description": "Action events", "events": []}
    }
}

for ann in coco["annotations"]:
    img = next(i for i in coco["images"] if i["id"] == ann["image_id"])
    # Extract frame number from filename (e.g., frame_0042.png -> 42)
    frame_num = int(img["file_name"].split("_")[-1].split(".")[0])
    x, y, w, h = ann["bbox"]  # COCO format: x,y,w,h
    cx, cy = x + w/2, y + h/2
    our_format["annotated_frames"]["ball"]["frames"][str(frame_num)] = {
        "x": cx, "y": cy, "visible": True
    }

with open("ground_truth/your_video_annotations.json", "w") as f:
    json.dump(our_format, f, indent=2)
```

### Option 2: CVAT (Free, Open Source)

[CVAT](https://www.cvat.ai/) works directly with video files (no need to extract frames).
Good for player tracking annotations since you can interpolate bounding boxes between keyframes.

- Upload video directly
- Annotate player boxes with track IDs
- Export in CVAT or COCO format

### Option 3: Manual JSON (Quick & Simple)

For action events and small evaluation sets, manually writing JSON is fastest:

1. Open video in VLC (press 'E' to advance frame-by-frame, frame counter shows in bottom bar)
2. Watch rallies and note: frame number, which player, what action
3. Fill in the JSON schema above

**Example workflow for action annotation:**
```
Watch rally → see Player 2 serve at frame 120
→ add {"frame": 120, "player_id": 2, "action": "serve"}
Watch → Player 4 digs at frame 145
→ add {"frame": 145, "player_id": 4, "action": "dig"}
...and so on
```

### Recommended Annotation Strategy

1. **Start with evaluation annotations** (Option 3): Manually annotate 2-3 rallies (ball position + actions) to establish baseline metrics. This takes ~30 minutes.
2. **If ball detection needs improvement**, use Roboflow (Option 1) to annotate 200-500 frames for YOLO fine-tuning.
3. **If player tracking needs improvement**, use CVAT (Option 2) to annotate player boxes with interpolation.

---

## Field Details

### Ball annotations
- **x, y**: Ball center in pixels
- **visible**: Whether ball is actually visible in the frame
- Annotate every 5 frames. Use `null` for frames where ball is off-screen
- Only annotate frames where you're confident about position

### Player annotations
- **id**: Consistent player ID (1-4) across all frames
- **team**: "A" (left side) or "B" (right side)
- **bbox**: `[x_min, y_min, x_max, y_max]` in pixels
- Annotate every 10 frames

### Action events
- **frame**: Frame number where the action occurs (ball contact frame)
- **player_id**: Which player performed the action (1-4)
- **action**: One of `serve`, `dig`, `set`, `spike`, `block`, `ace`, `kill`
- **Spike events** (optional, entreno_3+) also carry:
  - **spike_type**: `touch` (soft shot / rainbow) or `hard` (driven / accelerated)
  - **attack_zone**: `{"side": "A"|"B", "zone": 1-9}` — the spiker's 3x3 zone on
    their own half. Each half is numbered 1-9 left-to-right as seen standing
    at the net facing that side's OWN baseline (rows: 1-3 at the net, 4-6
    middle, 7-9 back). In the standard camera view (A near/bottom) A's zone 1
    is image-right at the net, B's zone 1 is image-left.
  - **outcome**: `kill`, `out`, `dug`, `blocked`. Kill semantics (owner, 2026-08-31):
    the ball falls directly (no dig), OR is dug and then dies WITHOUT a set —
    falling on the defenders' court or out of bounds. A dig that is kept up
    (a set follows) is `dug`.
  - **landing_zone**: `{"side", "zone"}` for kills — where the ball fell;
    **dug_zone**: `{"side", "zone"}` for digs — where the defender played it

### Court
- **corners**: 4 court corners in pixel coordinates, clockwise from top-left
- **net_posts**: 2 net-sideline intersection positions (left, right)
