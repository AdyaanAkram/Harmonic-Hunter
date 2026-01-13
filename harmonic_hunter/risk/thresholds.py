# Conservative, "typical" thresholds (not claiming code violation).
# You can tune these after pilots.

THRESHOLDS = {
    # Total Harmonic Distortion (%)
    "THD_WARN": 15.0,
    "THD_CRITICAL": 20.0,

    # Triplen harmonic index (% of fundamental)
    "TRIPLEN_WARN": 20.0,
    "TRIPLEN_CRITICAL": 30.0,

    # Individual harmonic % of fundamental
    "FIFTH_WARN": 12.0,
    "FIFTH_CRITICAL": 15.0,

    # Trend-mode indicators
    "CREST_WARN": 2.5,
    "CREST_CRITICAL": 3.0,

    "VARIABILITY_WARN": 25.0,      # %
    "VARIABILITY_CRITICAL": 40.0,  # %
}
