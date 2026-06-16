import streamlit as st
import pandas as pd
import random
import os
from datetime import datetime
import pytz

# ── Action profiles keyed by severity band ──────────────────────
ACTION_PROFILES = {
    "extreme": [
        [
            "Declare city-wide heat emergency immediately",
            "Open all cooling centers, schools, and community halls as shelters",
            "Deploy ICU-equipped emergency medical units to high-density zones",
            "Suspend all outdoor labor and construction activities",
            "Activate disaster response command center 24×7",
        ],
        [
            "Trigger highest-level disaster response protocols",
            "Convert public buildings into emergency shelters",
            "Mobilize national disaster medical teams",
            "Ban all non-essential outdoor operations",
            "Broadcast mass public emergency alerts via SMS and radio",
        ],
    ],
    "critical": [
        [
            "Escalate heat response to district-level authorities",
            "Open major cooling centers in high-density zones",
            "Deploy emergency medical camps and first-aid posts",
            "Ensure uninterrupted 24×7 water tanker supply",
            "Issue mandatory heat emergency SMS alerts to residents",
        ],
        [
            "Activate district emergency coordination unit",
            "Set up temporary shade and misting stations",
            "Position ambulances at heat stress hotspots",
            "Push real-time heat alerts to mobile users",
        ],
    ],
    "severe": [
        [
            "Activate local heat emergency protocols",
            "Open priority cooling centers in vulnerable wards",
            "Deploy rapid medical response teams",
            "Issue targeted heat alert notifications in hotspot wards",
        ],
        [
            "Increase field surveillance by health officers",
            "Expand clinic and hospital operating hours",
            "Issue strong public heat advisories via media",
        ],
    ],
    "high": [
        [
            "Prepare cooling centers at high capacity",
            "Deploy mobile health vans in vulnerable areas",
            "Increase drinking water distribution points",
            "Advise work-from-home and staggered outdoor shifts",
        ],
        [
            "Inspect hospital readiness for heat-related admissions",
            "Deploy awareness teams in crowded public zones",
            "Pre-position emergency water and medical supplies",
        ],
    ],
    "moderate": [
        [
            "Issue early heat warning to all residents",
            "Monitor elderly, children, and outdoor workers closely",
            "Promote hydration and shaded rest breaks",
            "Prepare emergency teams for possible escalation",
        ],
        [
            "Distribute preventive heat awareness pamphlets",
            "Review and update emergency response protocols",
        ],
    ],
    "low": [
        [
            "Routine heat monitoring across all wards",
            "Update seasonal climate risk assessments",
            "Advance urban greening and cool-roof initiatives",
            "Community education on heat illness prevention",
        ],
        [
            "Conduct staff training on heat illness recognition",
            "Inspect and service cooling center equipment",
        ],
    ],
}

def severity_band(risk):
    if risk >= 0.90: return "extreme"
    if risk >= 0.82: return "critical"
    if risk >= 0.75: return "severe"
    if risk >= 0.65: return "high"
    if risk >= 0.50: return "moderate"
    return "low"

def get_actions(risk):
    band = severity_band(risk)
    return random.choice(ACTION_PROFILES[band])

def show():
    india_tz = pytz.timezone("Asia/Kolkata")
    now = datetime.now(india_tz)

    st.title("🚑 Action Plan")
    st.caption(f"HeatGuard AI • Last updated: {now.strftime('%d %b %Y, %I:%M %p IST')}")

    # ── Load data ────────────────────────────────────────────────
    csv_path = os.path.join(
        os.path.dirname(__file__), "..", "data", "processed", "ward_priority_topsis.csv"
    )
    if not os.path.exists(csv_path):
        st.error(f"❌ Data file not found: {csv_path}")
        st.info("Ensure `ward_priority_topsis.csv` is in `data/processed/`")
        return

    df = pd.read_csv(csv_path)
    df.columns = df.columns.str.strip()

    if not {"Ward", "TOPSIS_SCORE"}.issubset(df.columns):
        st.error(f"Missing required columns. Found: {df.columns.tolist()}")
        return

    score_min, score_max = df["TOPSIS_SCORE"].min(), df["TOPSIS_SCORE"].max()
    df["risk_norm"] = (df["TOPSIS_SCORE"] - score_min) / (score_max - score_min + 1e-9)

    def classify_alert(risk):
        if risk >= 0.85: return "RED"
        if risk >= 0.70: return "ORANGE"
        if risk >= 0.45: return "YELLOW"
        return "GREEN"

    df["ALERT"] = df["risk_norm"].apply(classify_alert)
    df["BAND"] = df["risk_norm"].apply(severity_band)

    color_fn_map = {"RED": st.error, "ORANGE": st.warning, "YELLOW": st.info, "GREEN": st.success}

    # ── Top 5 most critical ──────────────────────────────────────
    st.subheader("🚨 Highest Risk Wards — Priority Actions")
    for _, row in df.sort_values("risk_norm", ascending=False).head(5).iterrows():
        alert = row["ALERT"]
        risk = row["risk_norm"]
        band = row["BAND"]

        with st.expander(f"{row['Ward']} — {alert} ALERT  |  Risk: {risk:.3f}  |  Band: {band.upper()}"):
            col1, col2 = st.columns([1, 2])
            col1.metric("Risk Score", f"{risk:.3f}")
            col1.metric("Alert Level", alert)
            col1.metric("Severity Band", band.title())

            actions = get_actions(risk)
            color_fn_map[alert](f"**{alert} ALERT — Recommended Actions:**")
            for act in actions:
                st.markdown(f"• {act}")

    # ── All wards table ──────────────────────────────────────────
    st.divider()
    st.subheader("📋 All Wards — Alert Summary")
    display_df = df[["Ward", "TOPSIS_SCORE", "risk_norm", "ALERT", "BAND"]].sort_values("risk_norm", ascending=False)
    display_df.columns = ["Ward", "TOPSIS Score", "Normalized Risk", "Alert Level", "Severity Band"]
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    # ── Response timeline ────────────────────────────────────────
    st.divider()
    st.subheader("⏱️ Recommended Response Timeline")
    st.error("**0–6 hrs:** Open cooling centers in RED/extreme wards immediately")
    st.warning("**6–24 hrs:** Deploy water tankers and medical teams to critical zones")
    st.info("**24–72 hrs:** Community outreach, advisories, and ongoing monitoring")
    st.success("**72 hrs+:** Evaluate outcomes and replenish resources")

    # ── Agency responsibilities ─────────────────────────────────
    st.divider()
    st.subheader("🧑‍💼 Responsible Agencies")
    col_a, col_b, col_c = st.columns(3)
    col_a.info("🏛️ **Municipal Corporation**\nCooling centers, water supply, infrastructure")
    col_b.warning("🏥 **Health Department**\nMedical teams, ORS, heat illness treatment")
    col_c.error("🚨 **Disaster Response Units**\nEmergency logistics, command coordination")

    st.caption("HeatGuard AI — Decision-support system for urban heatwave preparedness")
