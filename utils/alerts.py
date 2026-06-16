"""
utils/alerts.py
Single source of truth for ward alert-level classification.
Every page should call ensure_alert_columns() instead of writing
its own classify()/threshold logic, so RED/ORANGE/YELLOW/GREEN
labels are identical across Home, Map, Priority, Action Plan, etc.
"""

import pandas as pd

# Thresholds applied to NORMALIZED risk (0-1), matching the
# 'All Wards — Alert Summary' table (Shivajinagar=1.0 -> RED,
# Lakkasandra=0.43 -> GREEN, etc.)
RED_THRESHOLD = 0.90
ORANGE_THRESHOLD = 0.70
YELLOW_THRESHOLD = 0.45


def normalize_score(score: float, min_score: float, max_score: float) -> float:
    if max_score == min_score:
        return 0.0
    return (score - min_score) / (max_score - min_score)


def classify_normalized(norm_risk: float) -> str:
    if norm_risk >= RED_THRESHOLD:
        return "RED"
    if norm_risk >= ORANGE_THRESHOLD:
        return "ORANGE"
    if norm_risk >= YELLOW_THRESHOLD:
        return "YELLOW"
    return "GREEN"


def ensure_alert_columns(df: pd.DataFrame, score_col: str = "TOPSIS_SCORE") -> pd.DataFrame:
    """
    Guarantee df has NORMALIZED_RISK and ALERT_LEVEL columns,
    computed consistently. If your CSV pipeline already wrote
    these columns, they're left untouched (canonical source).
    """
    df = df.copy()

    if "NORMALIZED_RISK" not in df.columns:
        smin, smax = df[score_col].min(), df[score_col].max()
        df["NORMALIZED_RISK"] = df[score_col].apply(
            lambda s: normalize_score(s, smin, smax)
        )

    if "ALERT_LEVEL" not in df.columns:
        df["ALERT_LEVEL"] = df["NORMALIZED_RISK"].apply(classify_normalized)

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