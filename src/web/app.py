"""Local web UI for the volleyball analysis database.

Run with ``make ui`` (or ``python -m src.web.app``) -> http://127.0.0.1:8000

Pages:
- /                 video list + labeling status
- /videos/{key}     action timeline (rally-grouped), spike table, label form
- /players          metrics overview per labeled player
- /players/{id}     full metric bundle: cards, court heatmap (attack
                    origins bottom half, landings top half)

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


@app.get("/players/{player_id}", response_class=HTMLResponse)
def player_page(request: Request, player_id: int):
    conn = request.state.conn
    bundle = M.player_metrics(conn, player_id)
    if bundle is None:
        return HTMLResponse(f"Unknown player: {player_id}", status_code=404)

    # Court heatmap: one 3x3 grid per half, keyed by zone digit 1-9.
    # Layout top->bottom, as seen from behind the player's own baseline
    # (matches world_point_to_zone's camera-view diagram):
    #   landing half   7 8 9 / 4 5 6 / 1 2 3   (net row adjacent to the net)
    #   attack half    3 2 1 / 6 5 4 / 9 8 7
    attack_grid = bundle["court_attack"]
    landing_grid = bundle["court_landing"]
    landing_detail = bundle["court_landing_outcomes"]
    max_attack = max(attack_grid.values(), default=0)
    max_landing = max(landing_grid.values(), default=0)
    court_rows = [
        ("landing", [7, 8, 9]), ("landing", [4, 5, 6]), ("landing", [1, 2, 3]),
        ("attack", [3, 2, 1]), ("attack", [6, 5, 4]), ("attack", [9, 8, 7]),
    ]

    return templates.TemplateResponse(request, "player_detail.html", {
        "m": bundle,
        "court_rows": court_rows,
        "attack_grid": attack_grid,
        "landing_grid": landing_grid,
        "landing_detail": landing_detail,
        "max_attack": max_attack,
        "max_landing": max_landing,
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
