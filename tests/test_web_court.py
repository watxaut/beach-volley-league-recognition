"""Court-heatmap geometry + rendering for the player page.

The SVG court is LANDSCAPE (160x80 viewBox, 1 unit = 10 cm): net vertical at
x=80, the player's own half on the LEFT (attack takeoffs), the opponent half
on the RIGHT (landings). The mapping must equal the previous portrait court
rotated 90 degrees clockwise, so world_point_to_zone's digit semantics are
unchanged.
"""

import xml.etree.ElementTree as ET

import pytest

from src.web.app import _court_blobs, templates


def test_zone1_attack_net_row_bottom_column():
    """Attack zone 1 hugs the net on the LEFT half, bottom column."""
    (b,) = _court_blobs({1: 1}, "attack")
    assert b["x"] == pytest.approx(66.67, abs=0.01)
    assert b["y"] == pytest.approx(66.67, abs=0.01)
    assert b["title"] == "1 attack from zone 1"


def test_zone9_attack_deep_left_top_column():
    (b,) = _court_blobs({9: 1}, "attack")
    assert b["x"] == pytest.approx(13.33, abs=0.01)
    assert b["y"] == pytest.approx(13.33, abs=0.01)


def test_zone1_landing_net_row_top_column():
    """Landing zone 1 hugs the net on the RIGHT half, top column."""
    (b,) = _court_blobs({1: 1}, "landing")
    assert b["x"] == pytest.approx(93.33, abs=0.01)
    assert b["y"] == pytest.approx(13.33, abs=0.01)


def test_zone9_landing_deep_right_bottom_column():
    (b,) = _court_blobs({9: 1}, "landing")
    assert b["x"] == pytest.approx(146.67, abs=0.01)
    assert b["y"] == pytest.approx(66.67, abs=0.01)


def test_halves_mirror_across_net_and_midline():
    """Same digit on both halves is 180-degree symmetric about the court."""
    a = _court_blobs({5: 1}, "attack")[0]
    l = _court_blobs({5: 1}, "landing")[0]
    assert a["x"] + l["x"] == pytest.approx(160.0)  # mirror across net x=80
    assert a["y"] + l["y"] == pytest.approx(80.0)  # mirror across mid y=40


def test_intensity_is_share_of_half_max():
    blobs = _court_blobs({1: 1, 2: 3}, "attack")
    by_digit = {b["digit"]: b for b in blobs}
    assert by_digit[1]["a"] == pytest.approx(1 / 3, abs=0.01)
    assert by_digit[2]["a"] == 1.0
    # degenerate: no counts -> no division by zero, empty output
    assert _court_blobs({}, "attack") == []


def test_landing_title_carries_outcome_detail():
    detail = {5: {"kill": 1, "out": 0, "dug": 2}}
    (b,) = _court_blobs({5: 3}, "landing", detail)
    assert "3 landings in zone 5" in b["title"]
    assert "1 kill" in b["title"] and "2 dug" in b["title"]


def _render_page(attacks, attack_blobs, landing_blobs):
    m = {
        "player": {"name": "Test"},
        "n_videos": 1, "attacks": attacks, "kills": 0, "kill_pct": 0.0,
        "error_pct": 0.0, "dug_pct": 0.0, "hard_pct": 0.0, "touch_pct": 0.0,
        "digs": 0, "dig_pct": 0.0, "dig_opportunities": 0, "blocks": 0,
        "kill_blocks": 0, "soft_blocks": 0, "serves": 0, "sets": 0,
        "per_video": [], "video_keys": [],
    }
    return templates.env.get_template("player_detail.html").render(
        m=m, attack_blobs=attack_blobs, landing_blobs=landing_blobs
    )


def _svg_of(html: str) -> ET.Element:
    start = html.index("<svg")
    return ET.fromstring(html[start:html.index("</svg>") + 6])


def test_svg_renders_wellformed_landscape_with_numbers():
    html = _render_page(
        2,
        _court_blobs({1: 1, 2: 1}, "attack"),
        _court_blobs({5: 2}, "landing", {5: {"kill": 0, "out": 0, "dug": 2}}),
    )
    svg = _svg_of(html)
    # the fragment carries no xmlns declaration -> plain tag names
    assert svg.get("viewBox") == "-5 -12 170 100"  # landscape frame
    counts = [t for t in svg.iter("text")
              if "blob-count" in (t.get("class") or "")]
    assert sorted(t.text for t in counts) == ["1", "1", "2"]
    for t in counts:
        # numbers must carry their own fill: they survive a stale style.css
        assert t.get("fill") == "#ffffff"
    labels = [t for t in svg.iter("text")
              if "half-label" in (t.get("class") or "")]
    assert sorted(t.text for t in labels) == ["ATTACKS FROM", "LANDS"]
    # exactly one attack and one landing gradient blob per zone with counts
    assert sum(1 for c in svg.iter("circle")
               if c.get("fill") == "url(#blob-attack)") == 2
    assert sum(1 for c in svg.iter("circle")
               if c.get("fill") == "url(#blob-landing)") == 1


def test_page_without_attacks_has_no_svg():
    html = _render_page(0, [], [])
    assert "<svg" not in html
    assert "No attacks recorded." in html
