"""
Analysis configuration for enabling/disabling specific analysis features.

This allows incremental debugging by testing one component at a time.
"""

from dataclasses import dataclass


@dataclass
class AnalysisConfig:
    """
    Configuration for which analysis features to enable.

    Usage:
        # Only match rates
        config = AnalysisConfig.only_match_rates()

        # Only basic metrics
        config = AnalysisConfig.only_basic_metrics()

        # Everything enabled (default)
        config = AnalysisConfig.all_enabled()
    """

    # Core metrics (always needed)
    basic_metrics: bool = True  # ACPL, accuracy, move quality
    topn_match_rates: bool = True  # Top-N engine match rates

    # Time-based analysis
    time_pressure: bool = True  # Time management metrics
    time_complexity_correlation: bool = True  # Time vs complexity
    post_pause_quality: bool = True  # Quality after long pauses

    # Psychological analysis
    psychological_momentum: bool = True  # Tilt, recovery, pressure response

    # Pattern analysis
    consistency_patterns: bool = True  # Performance consistency
    mistake_clustering: bool = True  # Error pattern detection

    # Opening analysis
    opening_analysis: bool = True  # Opening book detection and impact

    # Development mode
    dry_run: bool = False  # If True, analyze but don't save to database

    @classmethod
    def only_match_rates(cls) -> "AnalysisConfig":
        """Only calculate basic metrics + topN match rates."""
        return cls(
            basic_metrics=True,
            topn_match_rates=True,
            time_pressure=False,
            time_complexity_correlation=False,
            post_pause_quality=False,
            psychological_momentum=False,
            consistency_patterns=False,
            mistake_clustering=False,
            opening_analysis=False,
        )

    @classmethod
    def only_basic_metrics(cls) -> "AnalysisConfig":
        """Only calculate basic metrics (ACPL, accuracy)."""
        return cls(
            basic_metrics=True,
            topn_match_rates=False,
            time_pressure=False,
            time_complexity_correlation=False,
            post_pause_quality=False,
            psychological_momentum=False,
            consistency_patterns=False,
            mistake_clustering=False,
            opening_analysis=False,
        )

    @classmethod
    def all_enabled(cls) -> "AnalysisConfig":
        """Enable all analysis features (default)."""
        return cls()

    @classmethod
    def minimal(cls) -> "AnalysisConfig":
        """Absolute minimum for testing."""
        return cls(
            basic_metrics=True,
            topn_match_rates=False,
            time_pressure=False,
            time_complexity_correlation=False,
            post_pause_quality=False,
            psychological_momentum=False,
            consistency_patterns=False,
            mistake_clustering=False,
            opening_analysis=False,
        )

    @classmethod
    def dry_run_mode(cls, base_config: "AnalysisConfig | None" = None) -> "AnalysisConfig":
        """
        Create a dry-run configuration (analyze but don't save to database).

        Args:
            base_config: Optional base configuration to enable dry_run on.
                        If None, uses all_enabled() as base.

        Returns:
            AnalysisConfig with dry_run=True
        """
        if base_config is None:
            base_config = cls.all_enabled()

        # Create a copy and enable dry_run
        config = cls(
            basic_metrics=base_config.basic_metrics,
            topn_match_rates=base_config.topn_match_rates,
            time_pressure=base_config.time_pressure,
            time_complexity_correlation=base_config.time_complexity_correlation,
            post_pause_quality=base_config.post_pause_quality,
            psychological_momentum=base_config.psychological_momentum,
            consistency_patterns=base_config.consistency_patterns,
            mistake_clustering=base_config.mistake_clustering,
            opening_analysis=base_config.opening_analysis,
            dry_run=True,  # Enable dry-run mode
        )
        return config
