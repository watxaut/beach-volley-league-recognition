# Ground Truth Annotation Format

Annotations are stored as JSON files in this directory. Each video gets one JSON file.

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

### Court
- **corners**: 4 court corners in pixel coordinates, clockwise from top-left
- **net_posts**: 2 net-sideline intersection positions (left, right)
