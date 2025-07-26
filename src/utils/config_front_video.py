CONFIG = {
    "court_detection_method": "geometric",  # "geometric" or "vision"
    "court_height_ratio": 0.23,  # Court takes 60% of frame height
    "court_width_ratio": 0.7,  # Court takes 80% of frame width
    "court_vertical_offset": 0.5,  # Court starts at 20% from top
    "court_horizontal_center": 0.52,  # Court centered horizontally

    # Perspective correction settings
    "court_perspective_enabled": True,  # Enable perspective-aware court detection
    "court_perspective_top_width": 0.5,  # Width ratio at top of court (far end)
    "court_perspective_bottom_width": 0.8,  # Width ratio at bottom of court (near end)
    "court_perspective_skew": 0.0,  # Horizontal skew (-0.2 to 0.2, negative = left skew)
    "court_perspective_depth": 0.20,  # How much perspective depth to apply (0.0 to 0.3)

    # Advanced court detection settings
    "court_margin": 0.01,  # 5% margin around detected court
    "use_adaptive_court": False,  # Adapt court based on player positions

}