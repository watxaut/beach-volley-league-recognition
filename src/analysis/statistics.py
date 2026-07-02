"""
Statistics analyzer for volleyball video analysis.

This module analyzes video processing results to generate meaningful
statistics about player actions and game dynamics.
"""

from typing import Dict, List, Any, Tuple
import numpy as np
from collections import defaultdict, Counter
import logging


class StatisticsAnalyzer:
    """Analyzer for volleyball game statistics and player performance metrics."""

    def __init__(self):
        """Initialize the statistics analyzer."""
        self.logger = logging.getLogger(__name__)

        # Action types for volleyball
        self.action_types = ["dig", "set", "spike", "block", "ace", "serve"]

    def analyze_video_results(self, video_results: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze complete video results and generate statistics.

        Args:
            video_results: Complete video processing results

        Returns:
            Comprehensive statistics dictionary
        """
        self.logger.info("Analyzing video results for statistics")

        statistics = {
            "player_stats": self._analyze_player_statistics(video_results),
            "action_stats": self._analyze_action_statistics(video_results),
            "temporal_stats": self._analyze_temporal_patterns(video_results),
            "ball_stats": self._analyze_ball_statistics(video_results),
            "game_flow": self._analyze_game_flow(video_results)
        }

        return statistics

    def _analyze_player_statistics(self, video_results: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze statistics for each individual player.

        Args:
            video_results: Video processing results

        Returns:
            Per-player statistics
        """
        player_actions = video_results.get("player_actions", {})
        player_stats = {}

        for track_id, actions in player_actions.items():
            # Count actions by type
            action_counts = Counter()
            confidence_scores = defaultdict(list)
            frame_appearances = []

            for action_data in actions:
                action_type = action_data.get("action", "unknown")
                confidence = action_data.get("confidence", 0.0)
                frame_index = action_data.get("frame_index", 0)

                # Count every emitted action. These are already the finalised,
                # confidence-gated events from the classifier (dig/set score
                # ~0.5-0.6), so a further >0.6 filter here silently dropped all
                # digs and sets from the summary.
                if action_type != "unknown":
                    action_counts[action_type] += 1

                confidence_scores[action_type].append(confidence)
                frame_appearances.append(frame_index)

            # Calculate player-specific metrics
            total_actions = sum(action_counts.values())
            avg_confidence = np.mean([
                conf for conf_list in confidence_scores.values()
                for conf in conf_list
            ]) if confidence_scores else 0.0

            # Activity metrics
            first_appearance = min(frame_appearances) if frame_appearances else 0
            last_appearance = max(frame_appearances) if frame_appearances else 0
            activity_duration = last_appearance - first_appearance

            player_stats[f"player_{track_id}"] = {
                "action_counts": dict(action_counts),
                "total_actions": total_actions,
                "average_confidence": float(avg_confidence),
                "activity_duration_frames": activity_duration,
                "first_appearance": first_appearance,
                "last_appearance": last_appearance,
                "action_frequencies": {
                    action: count / total_actions if total_actions > 0 else 0
                    for action, count in action_counts.items()
                }
            }

        return player_stats

    def _analyze_action_statistics(self, video_results: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze overall action statistics across all players.

        Args:
            video_results: Video processing results

        Returns:
            Overall action statistics
        """
        all_actions = []
        action_timeline = []

        # Collect all actions from all players
        for frame_result in video_results.get("frame_results", []):
            frame_index = frame_result.get("frame_index", 0)

            for action in frame_result.get("actions", []):
                action_type = action.get("action", "unknown")
                confidence = action.get("confidence", 0.0)

                if action_type != "unknown":  # already emission-gated upstream
                    all_actions.append(action_type)
                    action_timeline.append({
                        "frame": frame_index,
                        "action": action_type,
                        "confidence": confidence
                    })

        # Calculate action statistics
        action_counts = Counter(all_actions)
        total_actions = len(all_actions)

        # Action distribution
        action_distribution = {
            action: count / total_actions if total_actions > 0 else 0
            for action, count in action_counts.items()
        }

        # Action intensity (actions per frame)
        total_frames = video_results.get("video_info", {}).get("total_frames", 1)
        action_intensity = total_actions / total_frames

        return {
            "total_actions": total_actions,
            "action_counts": dict(action_counts),
            "action_distribution": action_distribution,
            "action_intensity": float(action_intensity),
            "action_timeline": action_timeline,
            "most_common_action": action_counts.most_common(1)[0] if action_counts else ("none", 0)
        }

    def _analyze_temporal_patterns(self, video_results: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze temporal patterns in the game.

        Args:
            video_results: Video processing results

        Returns:
            Temporal pattern statistics
        """
        fps = video_results.get("video_info", {}).get("fps", 30)
        total_frames = video_results.get("video_info", {}).get("total_frames", 1)

        # Analyze action sequences
        action_sequences = self._extract_action_sequences(video_results)

        # Calculate action intervals
        action_intervals = []
        last_action_frame = None

        for frame_result in video_results.get("frame_results", []):
            frame_index = frame_result.get("frame_index", 0)

            if frame_result.get("actions", []):
                if last_action_frame is not None:
                    interval = (frame_index - last_action_frame) / fps  # Convert to seconds
                    action_intervals.append(interval)
                last_action_frame = frame_index

        # Activity periods
        activity_periods = self._identify_activity_periods(video_results, fps)

        return {
            "total_duration_seconds": float(total_frames / fps),
            "action_sequences": action_sequences,
            "average_action_interval": float(np.mean(action_intervals)) if action_intervals else 0.0,
            "action_interval_std": float(np.std(action_intervals)) if action_intervals else 0.0,
            "activity_periods": activity_periods,
            "actions_per_minute": float(len(action_intervals) * 60 / (total_frames / fps))
        }

    def _analyze_ball_statistics(self, video_results: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze ball movement and trajectory statistics.

        Args:
            video_results: Video processing results

        Returns:
            Ball movement statistics
        """
        ball_trajectory = video_results.get("ball_trajectory", [])

        # Filter out None values
        valid_positions = [pos for pos in ball_trajectory if pos[0] is not None and pos[1] is not None]

        if not valid_positions:
            return {"ball_detected": False}

        positions = np.array(valid_positions)

        # Calculate movement statistics
        distances = np.sqrt(np.sum(np.diff(positions, axis=0)**2, axis=1))
        total_distance = np.sum(distances)

        # Ball visibility
        total_frames = len(ball_trajectory)
        visible_frames = len(valid_positions)
        visibility_ratio = visible_frames / total_frames if total_frames > 0 else 0

        # Movement patterns
        x_coords = positions[:, 0]
        y_coords = positions[:, 1]

        return {
            "ball_detected": True,
            "visibility_ratio": float(visibility_ratio),
            "total_distance": float(total_distance),
            "average_speed": float(np.mean(distances)) if len(distances) > 0 else 0.0,
            "max_speed": float(np.max(distances)) if len(distances) > 0 else 0.0,
            "trajectory_points": len(valid_positions),
            "x_range": [float(np.min(x_coords)), float(np.max(x_coords))],
            "y_range": [float(np.min(y_coords)), float(np.max(y_coords))],
            "ball_activity_area": float((np.max(x_coords) - np.min(x_coords)) * (np.max(y_coords) - np.min(y_coords)))
        }

    def _analyze_game_flow(self, video_results: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze overall game flow and rally patterns.

        Args:
            video_results: Video processing results

        Returns:
            Game flow analysis
        """
        # Identify rallies based on action patterns
        rallies = self._identify_rallies(video_results)

        # Calculate rally statistics
        rally_lengths = [rally["duration_frames"] for rally in rallies]
        rally_action_counts = [rally["action_count"] for rally in rallies]

        # Player involvement
        player_involvement = self._calculate_player_involvement(video_results)

        return {
            "total_rallies": len(rallies),
            "average_rally_length": float(np.mean(rally_lengths)) if rally_lengths else 0.0,
            "longest_rally": max(rally_lengths) if rally_lengths else 0,
            "average_actions_per_rally": float(np.mean(rally_action_counts)) if rally_action_counts else 0.0,
            "player_involvement": player_involvement,
            "rallies": rallies[:10]  # Store first 10 rallies for detailed analysis
        }

    def _extract_action_sequences(self, video_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract common action sequences.

        Args:
            video_results: Video processing results

        Returns:
            List of action sequences
        """
        sequences = []
        current_sequence = []
        sequence_window = 30  # frames

        for frame_result in video_results.get("frame_results", []):
            frame_actions = [
                action.get("action") for action in frame_result.get("actions", [])
                if action.get("confidence", 0) > 0.6
            ]

            if frame_actions:
                current_sequence.extend(frame_actions)

                # Limit sequence length
                if len(current_sequence) > 5:
                    current_sequence = current_sequence[-5:]
            else:
                # End of sequence
                if len(current_sequence) >= 2:
                    sequences.append({
                        "sequence": current_sequence.copy(),
                        "length": len(current_sequence)
                    })
                current_sequence = []

        # Find common sequences
        sequence_counts = Counter(tuple(seq["sequence"]) for seq in sequences)

        return [
            {"sequence": list(seq), "count": count}
            for seq, count in sequence_counts.most_common(10)
        ]

    def _identify_activity_periods(self, video_results: Dict[str, Any], fps: float) -> List[Dict[str, Any]]:
        """Identify periods of high and low activity.

        Args:
            video_results: Video processing results
            fps: Video frame rate

        Returns:
            List of activity periods
        """
        window_size = int(fps * 5)  # 5-second windows
        total_frames = video_results.get("video_info", {}).get("total_frames", 1)

        activity_levels = []

        for i in range(0, total_frames, window_size):
            window_end = min(i + window_size, total_frames)
            window_actions = 0

            for frame_idx in range(i, window_end):
                if frame_idx < len(video_results.get("frame_results", [])):
                    frame_result = video_results["frame_results"][frame_idx]
                    window_actions += len([
                        a for a in frame_result.get("actions", [])
                        if a.get("confidence", 0) > 0.6
                    ])

            activity_levels.append({
                "start_frame": i,
                "end_frame": window_end,
                "start_time": i / fps,
                "end_time": window_end / fps,
                "action_count": window_actions,
                "activity_level": "high" if window_actions > 3 else "low"
            })

        return activity_levels

    def _identify_rallies(self, video_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify rally periods in the game.

        Args:
            video_results: Video processing results

        Returns:
            List of identified rallies
        """
        rallies = []
        current_rally = None
        inactivity_threshold = 60  # frames of inactivity to end rally
        frames_since_action = 0

        for frame_result in video_results.get("frame_results", []):
            frame_index = frame_result.get("frame_index", 0)
            frame_actions = [
                a for a in frame_result.get("actions", [])
                if a.get("confidence", 0) > 0.6
            ]

            if frame_actions:
                # Action detected
                if current_rally is None:
                    # Start new rally
                    current_rally = {
                        "start_frame": frame_index,
                        "actions": [],
                        "players_involved": set()
                    }

                # Add actions to current rally
                for action in frame_actions:
                    current_rally["actions"].append(action)
                    track_id = action.get("track_id")
                    if track_id is not None:
                        current_rally["players_involved"].add(track_id)

                frames_since_action = 0
            else:
                frames_since_action += 1

                # End rally if too much inactivity
                if current_rally is not None and frames_since_action > inactivity_threshold:
                    current_rally.update({
                        "end_frame": frame_index,
                        "duration_frames": frame_index - current_rally["start_frame"],
                        "action_count": len(current_rally["actions"]),
                        "players_involved": list(current_rally["players_involved"])
                    })
                    rallies.append(current_rally)
                    current_rally = None

        # Close last rally if needed
        if current_rally is not None:
            last_frame = video_results.get("video_info", {}).get("total_frames", 0)
            current_rally.update({
                "end_frame": last_frame,
                "duration_frames": last_frame - current_rally["start_frame"],
                "action_count": len(current_rally["actions"]),
                "players_involved": list(current_rally["players_involved"])
            })
            rallies.append(current_rally)

        return rallies

    def _calculate_player_involvement(self, video_results: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate player involvement metrics.

        Args:
            video_results: Video processing results

        Returns:
            Player involvement statistics
        """
        player_actions = video_results.get("player_actions", {})
        total_frames = video_results.get("video_info", {}).get("total_frames", 1)

        involvement = {}

        for track_id, actions in player_actions.items():
            active_frames = set()
            for action in actions:
                if action.get("confidence", 0) > 0.6:
                    active_frames.add(action.get("frame_index", 0))

            involvement[f"player_{track_id}"] = {
                "active_frames": len(active_frames),
                "involvement_ratio": len(active_frames) / total_frames,
                "actions_per_active_frame": len(actions) / len(active_frames) if active_frames else 0
            }

        return involvement
