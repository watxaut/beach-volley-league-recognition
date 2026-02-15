# Video Recording Guide for Beach Volleyball Tracking

This guide explains how to record videos that maximize ball detection and player tracking accuracy.

## Camera Setup

### Resolution

**Use 1080p (1920x1080).** This is the sweet spot.

- Higher resolutions (4K, 3K) are counterproductive: the ball becomes proportionally smaller in the frame, YOLO needs to
  upscale its input to compensate, and processing is 3-4x slower.
- Lower resolutions (720p) lose too much detail on the ball and player poses.
- If your camera only shoots 4K, that works too -- the system auto-scales -- but 1080p is faster and just as accurate.

### Frame Rate

**30fps is recommended over 60fps.**

- At 60fps each frame has half the exposure time, which means less light per frame and more noise.
- The ball also travels fewer pixels between frames at 30fps, so there's less motion blur per frame.
- Processing is 2x faster at 30fps.
- 60fps does help tracking smoothness between frames, but the detection accuracy gain from 30fps outweighs this.

### Camera Position

**Perpendicular to the net, 3-5 meters from the nearest sideline, elevated ~2 meters (tripod height).**

- Perpendicular to the net means the camera looks straight across the court, with the net dividing the frame vertically.
  This is the ideal angle for team assignment and action recognition.
- 3-5m from the sideline keeps players at a reasonable size (~100-200px tall) while seeing the full court.
- 2m elevation (standard tripod fully extended) reduces occlusion when players are close together.
- The camera must be **completely static** throughout the match -- use a tripod. Any camera movement invalidates the
  court calibration.

### Framing

**Frame the court as tightly as possible.**

- The court should fill most of the frame. The more of the frame the court occupies, the larger the ball and players
  appear, and the better detection works.
- Include a small margin (~10-15%) around the court edges so serves and out-of-bounds plays are visible.
- Avoid wide-angle shots that include lots of sky, surrounding courts, or spectators. Every pixel spent on non-court
  area is a pixel wasted.
- If your camera has optical zoom, use it to fill the frame with the court rather than cropping in post.

## Lighting

### Sun Position

**Never shoot into the sun.**

- The ball disappears against a bright sky. Backlit scenes create silhouettes where YOLO can't see the ball.
- Best: sun behind the camera (players front-lit).
- OK: sun to the side.
- Avoid: sun directly ahead or at a low angle facing the lens.

### Time of Day

- Overcast conditions are actually ideal -- even lighting, no harsh shadows, no sun glare.
- Early morning and late afternoon have better light angles than midday (softer shadows).
- If playing at midday, the sun is overhead which is fine -- the main risk is lens flare, not player shadows.

### Artificial Lighting (Night Games)

- Court lighting works fine as long as there's no flickering (LED lights at certain frequencies can cause banding in
  video).
- Test by recording a short clip first and checking for flickering bands in the footage.

## Ball

### Color

**Use a brightly colored ball that contrasts with the sand.**

- Best: blue, yellow, or multi-colored (Wilson AVP yellow/blue pattern is ideal).
- OK: orange, red, green.
- Worst: white ball on light sand -- minimal contrast, hardest for detection.

### Ball Size

- Official beach volleyball size (circumference 66-68cm) works well. The system is tuned for standard volleyballs.
- Mini volleyballs are too small to detect reliably.

## What to Avoid

| Problem                    | Why it hurts                                             | Fix                                           |
|----------------------------|----------------------------------------------------------|-----------------------------------------------|
| Shaky camera / handheld    | Invalidates court calibration, adds motion blur          | Use a tripod                                  |
| 4K resolution              | Ball too small relative to frame, 3-4x slower processing | Record at 1080p                               |
| Wide-angle lens            | Court is small in frame, barrel distortion               | Use normal/telephoto lens, zoom to fill frame |
| Shooting into sun          | Ball invisible against bright sky                        | Position camera with sun behind it            |
| White ball on light sand   | Low contrast for detection                               | Use colored ball                              |
| Spectators behind baseline | Can be detected as players                               | Court calibration filters them out            |
| Multiple courts in frame   | Players from adjacent courts detected                    | Frame only your court                         |
| Moving camera mid-match    | Court calibration becomes invalid                        | Keep tripod locked                            |

## Quick Checklist Before Recording

1. Tripod is stable and locked
2. Camera is perpendicular to the net
3. Court fills most of the frame (zoom in if needed)
4. Sun is behind or beside the camera, not in front
5. Resolution set to 1080p
6. Frame rate set to 30fps
7. Record a 5-second test clip and verify: court is fully visible, ball is visible at all court positions, no lens flare
