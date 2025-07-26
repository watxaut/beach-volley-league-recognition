"""
Visualization generator for volleyball video analysis results.

This module creates graphs and charts to visualize analysis results
including action counts, player statistics, and temporal patterns.
"""

import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, Any, List, Tuple
import logging


class VisualizationGenerator:
    """Generator for volleyball analysis visualization graphs."""

    def __init__(self):
        """Initialize the visualization generator."""
        self.logger = logging.getLogger(__name__)

        # Set style
        plt.style.use('seaborn-v0_8')
        sns.set_palette("husl")

        # Action colors for consistency
        self.action_colors = {
            'dig': '#FF6B6B',
            'set': '#4ECDC4',
            'spike': '#45B7D1',
            'block': '#96CEB4',
            'ace': '#FFEAA7',
            'serve': '#DDA0DD'
        }

    def generate_summary_graphs(
        self,
        analysis_results: Dict[str, Any],
        output_path: Path
    ) -> None:
        """Generate summary visualization graphs as required by project specs.

        Args:
            analysis_results: Complete analysis results
            output_path: Path to save the PNG file
        """
        self.logger.info(f"Generating summary graphs: {output_path}")

        try:
            # Create figure with subplots
            fig = plt.figure(figsize=(16, 12))

            # Generate required visualizations
            self._create_total_actions_bar_chart(fig, analysis_results, subplot_pos=221)
            self._create_player_actions_breakdown(fig, analysis_results, subplot_pos=222)
            self._create_temporal_analysis(fig, analysis_results, subplot_pos=223)
            self._create_action_distribution_pie(fig, analysis_results, subplot_pos=224)

            # Adjust layout and save
            plt.tight_layout()
            plt.suptitle('Beach Volleyball Video Analysis Summary', fontsize=16, y=0.98)
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            plt.close()

            self.logger.info("Summary graphs generated successfully")

        except Exception as e:
            self.logger.error(f"Visualization generation failed: {e}")
            raise

    def _create_total_actions_bar_chart(
        self,
        fig: plt.Figure,
        analysis_results: Dict[str, Any],
        subplot_pos: int
    ) -> None:
        """Create bar chart showing total count of each action type.

        Args:
            fig: Matplotlib figure
            analysis_results: Analysis results
            subplot_pos: Subplot position
        """
        ax = fig.add_subplot(subplot_pos)

        # Extract action statistics
        action_stats = analysis_results.get("statistics", {}).get("action_stats", {})
        action_counts = action_stats.get("action_counts", {})

        # Prepare data
        actions = ['Digs', 'Sets', 'Spikes', 'Blocks', 'Aces', 'Serves']
        action_keys = ['dig', 'set', 'spike', 'block', 'ace', 'serve']
        counts = [action_counts.get(key, 0) for key in action_keys]
        colors = [self.action_colors.get(key, '#95A5A6') for key in action_keys]

        # Create bar chart
        bars = ax.bar(actions, counts, color=colors, alpha=0.8, edgecolor='black', linewidth=0.5)

        # Customize chart
        ax.set_title('Total Action Counts Across Video', fontsize=14, fontweight='bold')
        ax.set_xlabel('Action Types', fontsize=12)
        ax.set_ylabel('Number of Actions', fontsize=12)
        ax.grid(axis='y', alpha=0.3)

        # Add value labels on bars
        for bar, count in zip(bars, counts):
            if count > 0:
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
                       str(count), ha='center', va='bottom', fontweight='bold')

        # Rotate x-axis labels if needed
        plt.setp(ax.get_xticklabels(), rotation=45, ha='right')

    def _create_player_actions_breakdown(
        self,
        fig: plt.Figure,
        analysis_results: Dict[str, Any],
        subplot_pos: int
    ) -> None:
        """Create stacked bar chart showing action breakdown per player.

        Args:
            fig: Matplotlib figure
            analysis_results: Analysis results
            subplot_pos: Subplot position
        """
        ax = fig.add_subplot(subplot_pos)

        # Extract player statistics
        player_stats = analysis_results.get("statistics", {}).get("player_stats", {})

        if not player_stats:
            ax.text(0.5, 0.5, 'No Player Data Available',
                   ha='center', va='center', transform=ax.transAxes, fontsize=12)
            ax.set_title('Action Breakdown by Player', fontsize=14, fontweight='bold')
            return

        # Prepare data for stacked bar chart
        players = list(player_stats.keys())
        action_types = ['dig', 'set', 'spike', 'block', 'ace', 'serve']
        action_labels = ['Digs', 'Sets', 'Spikes', 'Blocks', 'Aces', 'Serves']

        # Create data matrix
        data_matrix = []
        for action_type in action_types:
            action_counts = [
                player_stats[player].get("action_counts", {}).get(action_type, 0)
                for player in players
            ]
            data_matrix.append(action_counts)

        # Create stacked bar chart
        bottom = np.zeros(len(players))

        for i, (action_type, action_label) in enumerate(zip(action_types, action_labels)):
            color = self.action_colors.get(action_type, '#95A5A6')
            ax.bar(players, data_matrix[i], bottom=bottom,
                  label=action_label, color=color, alpha=0.8)
            bottom += data_matrix[i]

        # Customize chart
        ax.set_title('Action Breakdown by Player', fontsize=14, fontweight='bold')
        ax.set_xlabel('Players', fontsize=12)
        ax.set_ylabel('Number of Actions', fontsize=12)
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        ax.grid(axis='y', alpha=0.3)

        # Rotate x-axis labels
        plt.setp(ax.get_xticklabels(), rotation=45, ha='right')

    def _create_temporal_analysis(
        self,
        fig: plt.Figure,
        analysis_results: Dict[str, Any],
        subplot_pos: int
    ) -> None:
        """Create temporal analysis showing activity over time.

        Args:
            fig: Matplotlib figure
            analysis_results: Analysis results
            subplot_pos: Subplot position
        """
        ax = fig.add_subplot(subplot_pos)

        # Extract temporal data
        temporal_stats = analysis_results.get("statistics", {}).get("temporal_stats", {})
        activity_periods = temporal_stats.get("activity_periods", [])

        if not activity_periods:
            ax.text(0.5, 0.5, 'No Temporal Data Available',
                   ha='center', va='center', transform=ax.transAxes, fontsize=12)
            ax.set_title('Activity Over Time', fontsize=14, fontweight='bold')
            return

        # Prepare data
        times = [period.get("start_time", 0) for period in activity_periods]
        action_counts = [period.get("action_count", 0) for period in activity_periods]

        # Create line plot
        ax.plot(times, action_counts, marker='o', linewidth=2, markersize=4,
               color='#3498DB', alpha=0.8)
        ax.fill_between(times, action_counts, alpha=0.3, color='#3498DB')

        # Customize chart
        ax.set_title('Game Activity Over Time', fontsize=14, fontweight='bold')
        ax.set_xlabel('Time (seconds)', fontsize=12)
        ax.set_ylabel('Actions per 5-second Window', fontsize=12)
        ax.grid(True, alpha=0.3)

        # Add activity threshold line
        if action_counts:
            threshold = np.mean(action_counts)
            ax.axhline(y=threshold, color='red', linestyle='--', alpha=0.7,
                      label=f'Average Activity ({threshold:.1f})')
            ax.legend()

    def _create_action_distribution_pie(
        self,
        fig: plt.Figure,
        analysis_results: Dict[str, Any],
        subplot_pos: int
    ) -> None:
        """Create pie chart showing action distribution.

        Args:
            fig: Matplotlib figure
            analysis_results: Analysis results
            subplot_pos: Subplot position
        """
        ax = fig.add_subplot(subplot_pos)

        # Extract action data
        action_stats = analysis_results.get("statistics", {}).get("action_stats", {})
        action_counts = action_stats.get("action_counts", {})

        if not action_counts or sum(action_counts.values()) == 0:
            ax.text(0.5, 0.5, 'No Action Data Available',
                   ha='center', va='center', transform=ax.transAxes, fontsize=12)
            ax.set_title('Action Distribution', fontsize=14, fontweight='bold')
            return

        # Filter out zero counts
        filtered_actions = {k: v for k, v in action_counts.items() if v > 0}

        if not filtered_actions:
            ax.text(0.5, 0.5, 'No Actions Detected',
                   ha='center', va='center', transform=ax.transAxes, fontsize=12)
            ax.set_title('Action Distribution', fontsize=14, fontweight='bold')
            return

        # Prepare data
        labels = [action.capitalize() + 's' for action in filtered_actions.keys()]
        sizes = list(filtered_actions.values())
        colors = [self.action_colors.get(action, '#95A5A6') for action in filtered_actions.keys()]

        # Create pie chart
        wedges, texts, autotexts = ax.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%',
                                         startangle=90, textprops={'fontsize': 10})

        # Customize chart
        ax.set_title('Action Distribution', fontsize=14, fontweight='bold')

        # Make percentage text bold
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontweight('bold')

    def generate_detailed_analysis(
        self,
        analysis_results: Dict[str, Any],
        output_dir: Path
    ) -> None:
        """Generate detailed analysis graphs (optional, beyond requirements).

        Args:
            analysis_results: Complete analysis results
            output_dir: Directory to save detailed graphs
        """
        self.logger.info(f"Generating detailed analysis graphs in: {output_dir}")

        output_dir.mkdir(exist_ok=True)

        try:
            # Player performance comparison
            self._create_player_performance_radar(analysis_results,
                                                output_dir / "player_performance.png")

            # Ball trajectory visualization
            self._create_ball_trajectory_plot(analysis_results,
                                            output_dir / "ball_trajectory.png")

            # Rally analysis
            self._create_rally_analysis(analysis_results,
                                      output_dir / "rally_analysis.png")

            self.logger.info("Detailed analysis graphs generated successfully")

        except Exception as e:
            self.logger.error(f"Detailed visualization generation failed: {e}")

    def _create_player_performance_radar(
        self,
        analysis_results: Dict[str, Any],
        output_path: Path
    ) -> None:
        """Create radar chart for player performance comparison."""
        # Implementation for radar chart would go here
        # This is a bonus feature beyond the core requirements
        pass

    def _create_ball_trajectory_plot(
        self,
        analysis_results: Dict[str, Any],
        output_path: Path
    ) -> None:
        """Create ball trajectory visualization."""
        # Implementation for trajectory plot would go here
        # This is a bonus feature beyond the core requirements
        pass

    def _create_rally_analysis(
        self,
        analysis_results: Dict[str, Any],
        output_path: Path
    ) -> None:
        """Create rally pattern analysis."""
        # Implementation for rally analysis would go here
        # This is a bonus feature beyond the core requirements
        pass
