"""Tests for resolve_source_stem (src/utils/video_upscale.py).

The upscale cache names files ``<stem>_up<target>.mp4`` next to the source;
calibration auto-detect and output naming must key on the SOURCE stem even
when a run is pointed directly at the cached file (e.g. live-debug on
``..._up1080.mp4`` must still find ``calibrations/<source_stem>.json``).
"""

from pathlib import Path

from src.utils.video_upscale import ensure_1080, resolve_source_stem


def test_plain_stem_passes_through():
    assert resolve_source_stem("resources/video_entreno_1.mp4") == "video_entreno_1"


def test_upscale_cache_suffix_is_stripped():
    assert (
        resolve_source_stem(
            "resources/full_videos/20260920_match_ari_joan_lost_up1080.mp4"
        )
        == "20260920_match_ari_joan_lost"
    )


def test_any_target_height_suffix_is_stripped():
    # The cache suffix carries the configured target height, not always 1080.
    assert resolve_source_stem("out/tiny_up144.mp4") == "tiny"


def test_stem_ending_in_digits_without_up_is_kept():
    assert resolve_source_stem("resources/video2.mp4") == "video2"


def test_up_without_digits_is_kept():
    assert resolve_source_stem("resources/warm_up.mp4") == "warm_up"


def test_only_one_trailing_suffix_is_stripped():
    # A genuine source whose name itself carries the pattern keeps its base.
    assert resolve_source_stem("resources/a_up1080_up144.mp4") == "a_up1080"


def test_round_trip_against_ensure_1080_cache_naming():
    # The name ensure_1080 would cache must resolve back to the source stem.
    source = Path("resources/full_videos/20260920_match_ari_joan_lost.mp4")
    cached = source.with_name(f"{source.stem}_up1080{source.suffix}")
    assert resolve_source_stem(cached) == source.stem


def test_calibration_script_keys_cached_file_on_source_stem():
    # scripts/test_court_calibration.py must WRITE where the pipeline READS.
    import importlib.util

    script = Path("scripts/test_court_calibration.py")
    spec = importlib.util.spec_from_file_location("tcc", script)
    tcc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tcc)
    calib = tcc.get_calibration_path(
        "resources/full_videos/20260920_match_ari_joan_lost_up1080.mp4"
    )
    assert calib.name == "20260920_match_ari_joan_lost.json"
    assert calib.exists()
