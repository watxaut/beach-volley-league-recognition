"""
CSV exporter for volleyball video analysis results.

This module exports analysis results to CSV format for further analysis
and reporting.
"""

import csv
import logging
from pathlib import Path
from typing import Dict, Any, List
import pandas as pd


class CSVExporter:
    """Exports volleyball analysis results to CSV format."""

    def __init__(self):
        """Initialize the CSV exporter."""
        self.logger = logging.getLogger(__name__)

    def export(self, analysis_results: Dict[str, Any], output_path: Path) -> None:
        """Export analysis results to CSV file.

        Args:
            analysis_results: Complete analysis results from video processing
            output_path: Path where CSV file should be saved
        """
        self.logger.info(f"Exporting results to CSV: {output_path}")

        try:
            # Create main results CSV
            self._export_player_actions_summary(analysis_results, output_path)

            # Create detailed actions CSV
            detailed_path = output_path.parent / f"{output_path.stem}_detailed.csv"
            self._export_detailed_actions(analysis_results, detailed_path)

            # Create statistics CSV
            stats_path = output_path.parent / f"{output_path.stem}_statistics.csv"
            self._export_statistics(analysis_results, stats_path)

            self.logger.info("CSV export completed successfully")

        except Exception as e:
            self.logger.error(f"CSV export failed: {e}")
            raise

    def _export_player_actions_summary(
        self,
        analysis_results: Dict[str, Any],
        output_path: Path
    ) -> None:
        """Export player action summary to main CSV file.

        Args:
            analysis_results: Analysis results
            output_path: Output CSV path
        """
        # Prepare data for CSV
        csv_data = []

        statistics = analysis_results.get("statistics", {})
        player_stats = statistics.get("player_stats", {})

        # Define action types
        action_types = ["dig", "set", "spike", "block", "ace", "serve"]

        for player_id, stats in player_stats.items():
            action_counts = stats.get("action_counts", {})

            row = {
                "Player_ID": player_id,
                "Total_Actions": stats.get("total_actions", 0),
                "Average_Confidence": round(stats.get("average_confidence", 0.0), 3),
                "Activity_Duration_Frames": stats.get("activity_duration_frames", 0),
                "First_Appearance_Frame": stats.get("first_appearance", 0),
                "Last_Appearance_Frame": stats.get("last_appearance", 0)
            }

            # Add action counts
            for action_type in action_types:
                row[f"{action_type.capitalize()}_Count"] = action_counts.get(action_type, 0)

            # Add action frequencies
            action_frequencies = stats.get("action_frequencies", {})
            for action_type in action_types:
                frequency = action_frequencies.get(action_type, 0.0)
                row[f"{action_type.capitalize()}_Frequency"] = round(frequency, 3)

            csv_data.append(row)

        # Write to CSV
        if csv_data:
            df = pd.DataFrame(csv_data)
            df.to_csv(output_path, index=False)
        else:
            # Create empty CSV with headers
            headers = [
                "Player_ID", "Total_Actions", "Average_Confidence",
                "Activity_Duration_Frames", "First_Appearance_Frame", "Last_Appearance_Frame"
            ]
            headers.extend([f"{action.capitalize()}_Count" for action in action_types])
            headers.extend([f"{action.capitalize()}_Frequency" for action in action_types])

            with open(output_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(headers)

    def _export_detailed_actions(
        self,
        analysis_results: Dict[str, Any],
        output_path: Path
    ) -> None:
        """Export detailed action timeline to CSV.

        Args:
            analysis_results: Analysis results
            output_path: Output CSV path
        """
        csv_data = []

        # Extract detailed actions from frame results
        for frame_result in analysis_results.get("frame_results", []):
            frame_index = frame_result.get("frame_index", 0)

            for action in frame_result.get("actions", []):
                bbox = action.get("bbox", [0, 0, 0, 0])

                row = {
                    "Frame_Index": frame_index,
                    "Player_ID": f"player_{action.get('track_id', 'unknown')}",
                    "Action_Type": action.get("action", "unknown"),
                    "Confidence": round(action.get("confidence", 0.0), 3),
                    "Bbox_X1": round(bbox[0], 1) if len(bbox) > 0 else 0,
                    "Bbox_Y1": round(bbox[1], 1) if len(bbox) > 1 else 0,
                    "Bbox_X2": round(bbox[2], 1) if len(bbox) > 2 else 0,
                    "Bbox_Y2": round(bbox[3], 1) if len(bbox) > 3 else 0,
                }

                # Add timestamp if video info available
                video_info = analysis_results.get("video_info", {})
                fps = video_info.get("fps", 30)
                row["Timestamp_Seconds"] = round(frame_index / fps, 2)

                csv_data.append(row)

        # Write to CSV
        if csv_data:
            df = pd.DataFrame(csv_data)
            df.to_csv(output_path, index=False)
        else:
            # Create empty CSV with headers
            headers = [
                "Frame_Index", "Player_ID", "Action_Type", "Confidence",
                "Bbox_X1", "Bbox_Y1", "Bbox_X2", "Bbox_Y2", "Timestamp_Seconds"
            ]

            with open(output_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(headers)

    def _export_statistics(
        self,
        analysis_results: Dict[str, Any],
        output_path: Path
    ) -> None:
        """Export overall statistics to CSV.

        Args:
            analysis_results: Analysis results
            output_path: Output CSV path
        """
        csv_data = []

        statistics = analysis_results.get("statistics", {})
        video_info = analysis_results.get("video_info", {})

        # Video information
        csv_data.append({
            "Metric": "Video_Total_Frames",
            "Value": video_info.get("total_frames", 0),
            "Unit": "frames"
        })

        csv_data.append({
            "Metric": "Video_FPS",
            "Value": round(video_info.get("fps", 0), 2),
            "Unit": "fps"
        })

        csv_data.append({
            "Metric": "Video_Duration",
            "Value": round(video_info.get("total_frames", 0) / video_info.get("fps", 1), 2),
            "Unit": "seconds"
        })

        # Action statistics
        action_stats = statistics.get("action_stats", {})

        csv_data.append({
            "Metric": "Total_Actions_Detected",
            "Value": action_stats.get("total_actions", 0),
            "Unit": "count"
        })

        csv_data.append({
            "Metric": "Action_Intensity",
            "Value": round(action_stats.get("action_intensity", 0), 4),
            "Unit": "actions_per_frame"
        })

        csv_data.append({
            "Metric": "Actions_Per_Minute",
            "Value": round(statistics.get("temporal_stats", {}).get("actions_per_minute", 0), 2),
            "Unit": "actions_per_minute"
        })

        # Most common action
        most_common = action_stats.get("most_common_action", ("none", 0))
        csv_data.append({
            "Metric": "Most_Common_Action",
            "Value": f"{most_common[0]} ({most_common[1]} times)",
            "Unit": "action_type"
        })

        # Ball statistics
        ball_stats = statistics.get("ball_stats", {})

        if ball_stats.get("ball_detected", False):
            csv_data.append({
                "Metric": "Ball_Visibility_Ratio",
                "Value": round(ball_stats.get("visibility_ratio", 0), 3),
                "Unit": "ratio"
            })

            csv_data.append({
                "Metric": "Ball_Total_Distance",
                "Value": round(ball_stats.get("total_distance", 0), 1),
                "Unit": "pixels"
            })

            csv_data.append({
                "Metric": "Ball_Average_Speed",
                "Value": round(ball_stats.get("average_speed", 0), 2),
                "Unit": "pixels_per_frame"
            })

        # Game flow statistics
        game_flow = statistics.get("game_flow", {})

        csv_data.append({
            "Metric": "Total_Rallies_Identified",
            "Value": game_flow.get("total_rallies", 0),
            "Unit": "count"
        })

        csv_data.append({
            "Metric": "Average_Rally_Length",
            "Value": round(game_flow.get("average_rally_length", 0), 1),
            "Unit": "frames"
        })

        csv_data.append({
            "Metric": "Average_Actions_Per_Rally",
            "Value": round(game_flow.get("average_actions_per_rally", 0), 1),
            "Unit": "actions"
        })

        # Processing statistics
        processing_stats = analysis_results.get("processing_stats", {})

        csv_data.append({
            "Metric": "Total_Processing_Time",
            "Value": round(processing_stats.get("total_processing_time", 0), 2),
            "Unit": "seconds"
        })

        csv_data.append({
            "Metric": "Average_Frame_Processing_Time",
            "Value": round(processing_stats.get("average_frame_time", 0), 4),
            "Unit": "seconds"
        })

        csv_data.append({
            "Metric": "Processing_FPS_Achieved",
            "Value": round(processing_stats.get("fps_achieved", 0), 2),
            "Unit": "fps"
        })

        # Write to CSV
        df = pd.DataFrame(csv_data)
        df.to_csv(output_path, index=False)
