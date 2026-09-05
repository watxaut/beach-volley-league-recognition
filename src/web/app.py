"""Local web UI for the volleyball analysis database.

Run with ``make ui`` (or ``python -m src.web.app``) -> http://127.0.0.1:8000

Pages:
- /                 video list + labeling status
- /videos/{key}     action timeline (rally-grouped), spike table, label form
- /players          metrics overview per labeled player
- /players/{id}     full metric bundle: cards, court field heatmap (landscape
                    SVG: attack-origin hotspots on the LEFT half, landing
                    hotspots on the RIGHT half, net drawn vertically)

Charts are CSS-only (bars via divs, heatmap via colored table cells) -- no
JS dependency, fully offline. The DB is opened read-write (labeling) but
ingestion never runs here: extraction and DB are separate processes.
"""

import argparse
import logging
import re
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ..db import labels as L
from ..db import metrics as M
from ..db.schema import DEFAULT_DB_PATH, connect, init_db

BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Cache-bust the stylesheet on every edit: browsers otherwise keep serving a
# stale style.css (which once hid the court heatmap's CSS-styled parts).
_STYLE_PATH = BASE_DIR / "static" / "style.css"
templates.env.globals["style_ver"] = str(int(_STYLE_PATH.stat().st_mtime))

THUMB_NAME = re.compile(r"^track_\d+\.png$")

app = FastAPI(title="Volleyball Analysis", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.state.db_path = DEFAULT_DB_PATH  # overridden by --db in main()
logger = logging.getLogger(__name__)


def get_conn():
    """One connection per request (SQLite WAL handles the concurrency)."""
    conn = connect(app.state.db_path)
    init_db(conn)
    try:
        yield conn
    finally:
        conn.close()


@app.middleware("http")
async def db_conn_middleware(request: Request, call_next):
    gen = get_conn()
    request.state.conn = next(gen)
    try:
        response = await call_next(request)
    finally:
        try:
            next(gen)
        except StopIteration:
            pass
    return response


# --- template filters ---------------------------------------------------------


def pct(value: Optional[float]) -> str:
    """Render a percentage or an em-dash when the denominator was zero."""
    return "—" if value is None else f"{value:.1f}%"


templates.env.filters["pct"] = pct


def team_color(team: Optional[str]) -> str:
    return {"A": "team-a", "B": "team-b"}.get(team or "", "")


templates.env.filters["teamcolor"] = team_color


def _thumbs_root() -> Path:
    return Path(app.state.db_path).parent / "thumbs"


def _thumb_url(video_key: str, track_id: int) -> Optional[str]:
    """URL of the track's thumbnail strip, or None when not materialized."""
    path = _thumbs_root() / video_key / f"track_{track_id}.png"
    return f"/thumbs/{video_key}/track_{track_id}.png" if path.is_file() else None


@app.get("/", response_class=HTMLResponse)
def videos_page(request: Request):
    conn = request.state.conn
    return templates.TemplateResponse(request, "videos.html", {
        "videos": M.list_videos(conn),
        "unlabeled": M.unlabeled_tracks(conn),
    })


@app.get("/videos/{video_key}", response_class=HTMLResponse)
def video_page(request: Request, video_key: str, saved: Optional[str] = None):
    conn = request.state.conn
    videos = {v["video_key"] for v in M.list_videos(conn)}
    if video_key not in videos:
        return HTMLResponse(f"Unknown video: {video_key}", status_code=404)

    actions = M.video_actions(conn, video_key)
    spikes = M.video_spikes(conn, video_key)
    existing = L.labels_for_video(conn, video_key)
    tracks = L.tracks_in_video(conn, video_key)
    block_class = M.classify_blocks(conn, video_key)
    thumbs = {t: _thumb_url(video_key, t) for t in tracks}

    # Dominant team per track (suggested team for the label form).
    suggested_team = {
        t: next(
            (a["team"] for a in actions if a["track_id"] == t and a["team"]),
            None,
        )
        for t in tracks
    }

    # Group the timeline by rally_id (None -> a "no-rally" bucket, sorted last).
    rallies: dict = {}
    for a in actions:
        rallies.setdefault(a["rally_id"], []).append(a)
    rally_rows = sorted(
        rallies.items(), key=lambda kv: (kv[0] is None, kv[0] if kv[0] is not None else 0)
    )

    return templates.TemplateResponse(request, "video_detail.html", {
        "video_key": video_key,
        "video": next(v for v in M.list_videos(conn) if v["video_key"] == video_key),
        "tracks": tracks,
        "labels": existing,
        "suggested_team": suggested_team,
        "players": [p["name"] for p in L.all_players(conn)],
        "rally_rows": rally_rows,
        "spikes": spikes,
        "block_class": block_class,
        "actions": actions,
        "thumbs": thumbs,
        "saved": saved == "1",
    })


@app.post("/videos/{video_key}/labels")
async def save_labels(request: Request, video_key: str):
    conn = request.state.conn
    form = await request.form()

    for key, value in form.items():
        if not key.startswith("track_") or not key.endswith("_name"):
            continue
        track_id = int(key[len("track_"):-len("_name")])
        name = str(value).strip()
        team = str(form.get(f"track_{track_id}_team", "")).strip() or None
        if name:
            L.set_label(conn, video_key, track_id, name, team)
        else:
            L.clear_label(conn, video_key, track_id)

    return RedirectResponse(f"/videos/{video_key}?saved=1", status_code=303)


@app.get("/thumbs/{video_key}/{filename}")
def thumb_file(video_key: str, filename: str):
    """Serve labeling thumbnails (strict name check -- no traversal)."""
    if not THUMB_NAME.match(filename):
        return HTMLResponse("Bad thumbnail name", status_code=400)
    path = _thumbs_root() / video_key / filename
    if not path.is_file():
        return HTMLResponse("Not found", status_code=404)
    return FileResponse(path, media_type="image/png")


@app.get("/players", response_class=HTMLResponse)
def players_page(request: Request):
    conn = request.state.conn
    return templates.TemplateResponse(request, "players.html", {
        "players": M.players_overview(conn),
        "unlabeled": M.unlabeled_tracks(conn),
    })


def _court_blobs(counts, half, detail=None):
    """Zone-digit counts -> hotspot geometry on a 160x80 landscape SVG court.

    1 unit = 10 cm: the 16m x 8m court fills 0..160 x 0..80 with the net
    VERTICAL at x=80. The player's own half is on the LEFT (attack takeoffs),
    the opponent half on the RIGHT (where attacks land). Zone centers follow
    world_point_to_zone's camera-view layout -- each side's net row (row 0)
    hugs the net and the columns run opposite ways between the halves; the
    mapping is exactly the previous portrait drawing rotated 90 degrees
    clockwise, so the zone-digit semantics are unchanged. Intensity `a` is
    the count's share of the half's max.
    """
    mx = max(counts.values(), default=0)
    blobs = []
    for digit, n in sorted(counts.items()):
        row, col = divmod(digit - 1, 3)  # row 0 = net row, own-facing columns
        if half == "attack":
            x, y = 66.67 - row * 26.67, 66.67 - col * 26.67
            title = f"{n} attack{'s' if n != 1 else ''} from zone {digit}"
        else:
            x, y = 93.33 + row * 26.67, 13.33 + col * 26.67
            d = (detail or {}).get(digit, {})
            title = (f"{n} landing{'s' if n != 1 else ''} in zone {digit}: "
                     f"{d.get('kill', 0)} kill / {d.get('out', 0)} out / "
                     f"{d.get('dug', 0)} dug")
        blobs.append({
            "digit": digit, "x": round(x, 2), "y": round(y, 2), "count": n,
            "a": round(n / mx, 2) if mx else 0.0, "title": title,
        })
    return blobs


@app.get("/players/{player_id}", response_class=HTMLResponse)
def player_page(request: Request, player_id: int):
    conn = request.state.conn
    bundle = M.player_metrics(conn, player_id)
    if bundle is None:
        return HTMLResponse(f"Unknown player: {player_id}", status_code=404)

    # Court field heatmap: smooth hotspots on a drawn court. Bottom half =
    # takeoff zones (where the player attacks from), top half = where the
    # attacks land (kill/out landing_zone, dug -> dug_zone).
    attack_blobs = _court_blobs(bundle["court_attack"], "attack")
    landing_blobs = _court_blobs(
        bundle["court_landing"], "landing", bundle["court_landing_outcomes"]
    )

    return templates.TemplateResponse(request, "player_detail.html", {
        "m": bundle,
        "attack_blobs": attack_blobs,
        "landing_blobs": landing_blobs,
    })


def main() -> int:
    parser = argparse.ArgumentParser(description="Local volleyball analysis UI")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    import uvicorn

    app.state.db_path = Path(args.db)
    init_db(connect(app.state.db_path))  # create on first run
    logger.info(f"Serving UI for {args.db} at http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
