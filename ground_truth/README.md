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

## How to Annotate

1. Open video in a frame-by-frame viewer (e.g., VLC frame advance with 'E' key)
2. Note frame numbers and positions
3. Fill in JSON manually or use a simple annotation tool
4. Focus on accuracy over coverage -- 30-60 seconds of well-annotated video is enough
