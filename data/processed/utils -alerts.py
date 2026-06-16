"""
utils/alerts.py
Single source of truth for ward alert-level classification.
Always recomputes ALERT_LEVEL from TOPSIS_SCORE using these thresholds,
overriding any stale ALERT_LEVEL column from the CSV, so every page
shows identical labels.
"""

import pandas as pd

# Thresholds applied directly to TOPSIS_SCORE (0-1).
# Matches your ward_priority_topsis.csv pipeline:
#   Shivajinagar 0.982 -> RED/extreme
#   Mathikere    0.7713 -> RED/extreme
#   Kammanahalli 0.7107 -> RED/critical
#   Lakkasandra  0.5729 -> ORANGE/high
#   Jayanagar    0.4755 -> YELLOW/moderate
RED_THRESHOLD = 0.70
ORANGE_THRESHOLD = 0.45
YELLOW_THRESHOLD = 0.25


def classify_score(score: float) -> str:
    if score >= RED_THRESHOLD:
        return "RED"
    if score >= ORANGE_THRESHOLD:
        return "ORANGE"
    if score >= YELLOW_THRESHOLD:
        return "YELLOW"
    return "GREEN"


def ensure_alert_columns(df: pd.DataFrame, score_col: str = "TOPSIS_SCORE") -> pd.DataFrame:
    """
    Always (re)compute ALERT_LEVEL from TOPSIS_SCORE so every page
    uses identical thresholds, even if the CSV already had its own
    ALERT_LEVEL/SEVERITY_BAND columns from a different scheme.
    """
    df = df.copy()
    df["ALERT_LEVEL"] = df[score_col].apply(classify_score)

    if "NORMALIZED_RISK" not in df.columns:
        smin, smax = df[score_col].min(), df[score_col].max()
        df["NORMALIZED_RISK"] = (df[score_col] - smin) / (smax - smin + 1e-9)

    return df


ALERT_ICONS = {
    "RED": "🔴",
    "ORANGE": "🟠",
    "YELLOW": "🟡",
    "GREEN": "🟢",
}

ALERT_COLORS = {
    "RED": "#e74c3c",
    "ORANGE": "#e67e22",
    "YELLOW": "#f1c40f",
    "GREEN": "#2ecc71",
}

ALERT_ST_FN_NAMES = {
    "RED": "error",
    "ORANGE": "warning",
    "YELLOW": "info",
    "GREEN": "success",
}