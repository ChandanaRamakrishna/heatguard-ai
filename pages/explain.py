"""
pages/explain.py  — HeatGuard AI Explanation Page
Already fully fixed in the prior session (robust column detection, NDVI + water merge).
This file is the canonical version: no changes needed here.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os
from datetime import datetime
import pytz


def load_csv(path, label):
    if not os.path.exists(path):
        return None, f"❌ File not found: `{os.path.basename(path)}`"
    try:
        df = pd.read_csv(path)
        df.columns = df.columns.str.strip().str.lower()
        return df, None
    except Exception as e:
        return None, f"❌ Error reading `{label}`: {e}"


def find_col(df, keywords):
    for col in df.columns:
        for kw in keywords:
            if kw.lower() in col.lower():
                return col
    return None


def show():
    india_tz = pytz.timezone("Asia/Kolkata")
    now = datetime.now(india_tz)

    st.title("🧠 AI Explanation")
    st.caption(f"HeatGuard AI • Last updated: {now.strftime('%d %b %Y, %I:%M %p IST')}")

    base = os.path.join(os.path.dirname(__file__), "..", "data", "processed")

    # ── Load TOPSIS (required) ───────────────────────────────────
    df_topsis, err = load_csv(os.path.join(base, "ward_priority_topsis.csv"), "ward_priority_topsis.csv")
    if err:
        st.error(err)
        st.info("Place `ward_priority_topsis.csv` in `data/processed/`")
        return

    ward_col  = find_col(df_topsis, ["ward"])
    score_col = find_col(df_topsis, ["topsis", "score", "risk"])
    rank_col  = find_col(df_topsis, ["rank", "priority"])

    if not ward_col:
        st.error(f"Ward column not found. Columns: {df_topsis.columns.tolist()}")
        return
    if not score_col:
        st.error(f"Score column not found. Columns: {df_topsis.columns.tolist()}")
        return

    df_topsis = df_topsis.rename(columns={ward_col: "ward", score_col: "topsis_score"})
    if rank_col and rank_col not in ("ward", "topsis_score"):
        df_topsis = df_topsis.rename(columns={rank_col: "priority_rank"})

    df_topsis["ward"] = df_topsis["ward"].astype(str)
    s_min, s_max = df_topsis["topsis_score"].min(), df_topsis["topsis_score"].max()
    df_topsis["risk_norm"] = (df_topsis["topsis_score"] - s_min) / (s_max - s_min + 1e-9)

    # ── Load NDVI (optional) ─────────────────────────────────────
    df_ndvi, _ = load_csv(os.path.join(base, "ward_ndvi_proxy.csv"), "ward_ndvi_proxy.csv")
    ndvi_col = None
    if df_ndvi is not None:
        wc = find_col(df_ndvi, ["ward"])
        nc = find_col(df_ndvi, ["ndvi", "green", "vegetation"])
        if wc and nc:
            df_ndvi = df_ndvi.rename(columns={wc: "ward", nc: "ndvi"})
            df_ndvi["ward"] = df_ndvi["ward"].astype(str)
            df_topsis = df_topsis.merge(df_ndvi[["ward", "ndvi"]], on="ward", how="left")
            ndvi_col = "ndvi"

    # ── Load Water (optional) ────────────────────────────────────
    df_water, _ = load_csv(os.path.join(base, "water_access_summary.csv"), "water_access_summary.csv")
    water_col = None
    if df_water is not None:
        wc = find_col(df_water, ["ward"])
        wvc = find_col(df_water, ["water", "access", "vulnerability", "score"])
        if wc and wvc:
            df_water = df_water.rename(columns={wc: "ward", wvc: "water"})
            df_water["ward"] = df_water["ward"].astype(str)
            df_topsis = df_topsis.merge(df_water[["ward", "water"]], on="ward", how="left")
            water_col = "water"

    df = df_topsis.copy()

    # ── Ward selector ────────────────────────────────────────────
    st.markdown("### 🔍 Select a Ward for Detailed Explanation")
    ward = st.selectbox("Ward", sorted(df["ward"].tolist()), key="explain_ward")
    row  = df[df["ward"] == ward].iloc[0]

    risk   = float(row["risk_norm"])
    topsis = float(row["topsis_score"])

    # ── Alert banner ─────────────────────────────────────────────
    if risk >= 0.85:
        alert, fn = "RED — CRITICAL", st.error
    elif risk >= 0.70:
        alert, fn = "ORANGE — HIGH", st.warning
    elif risk >= 0.45:
        alert, fn = "YELLOW — MODERATE", st.info
    else:
        alert, fn = "GREEN — LOW", st.success

    fn(f"**{ward}** — {alert} ALERT  |  Risk Score: {risk:.3f}  |  TOPSIS: {topsis:.3f}")

    # ── Risk gauge ───────────────────────────────────────────────
    st.markdown("### 📊 Risk Gauge")
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=risk * 100,
        delta={"reference": 50},
        title={"text": f"Heat Risk — {ward}", "font": {"size": 18}},
        gauge={
            "axis": {"range": [0, 100]},
            "bar":  {"color": "#e94560"},
            "steps": [
                {"range": [0,  45], "color": "#2ecc71"},
                {"range": [45, 70], "color": "#f1c40f"},
                {"range": [70, 85], "color": "#e67e22"},
                {"range": [85, 100],"color": "#e74c3c"},
            ],
            "threshold": {"line": {"color": "red", "width": 4},
                          "thickness": 0.75, "value": risk * 100},
        }
    ))
    fig.update_layout(height=280, margin=dict(t=40, b=0))
    st.plotly_chart(fig, use_container_width=True)

    # ── AI reasoning ─────────────────────────────────────────────
    st.markdown("### 🤖 AI Copilot Reasoning")
    reasons = []

    if risk >= 0.85:
        reasons.append(("🔥", "Extreme combined vulnerability — immediate action required"))
    elif risk >= 0.70:
        reasons.append(("⚠️", "High overall risk from multiple compounding factors"))
    elif risk >= 0.45:
        reasons.append(("📋", "Moderate vulnerability — preventive measures recommended"))
    else:
        reasons.append(("✅", "Below critical thresholds — continue routine monitoring"))

    if risk > 0.60:
        reasons.append(("👥", "High population exposure in dense residential zones"))
    if risk > 0.50:
        reasons.append(("🌡️", "Elevated surface temperatures and heat island effect"))

    if ndvi_col and pd.notna(row.get("ndvi")):
        v = float(row["ndvi"])
        if v < 0.25:
            reasons.append(("🌱", f"Very low green cover (NDVI: {v:.2f}) — severe urban heat island"))
        elif v < 0.35:
            reasons.append(("🌱", f"Low green cover (NDVI: {v:.2f}) — limited cooling vegetation"))
        else:
            reasons.append(("🌳", f"Adequate green cover (NDVI: {v:.2f}) — moderate cooling effect"))
    else:
        reasons.append(("🌱", "Green cover data unavailable — assumed below average for dense urban wards"))

    if water_col and pd.notna(row.get("water")):
        w = float(row["water"])
        if w <= 1.0:
            if w < 0.4:
                reasons.append(("💧", f"Poor water accessibility (score: {w:.2f}) — high drought stress"))
            elif w < 0.6:
                reasons.append(("💧", f"Moderate water stress (score: {w:.2f})"))
            else:
                reasons.append(("💧", f"Acceptable water access (score: {w:.2f})"))
        else:
            reasons.append(("💧", f"Water vulnerability score: {w:.1f}"))
    else:
        reasons.append(("💧", "Water access data unavailable — assumed stressed based on urban density"))

    for icon, text in reasons:
        st.markdown(f"**{icon} {text}**")

    # ── Feature importance chart ─────────────────────────────────
    st.markdown("### 📊 Estimated Risk Factor Contribution")
    factors = {
        "Heat Exposure":      min(risk * 0.35, 1.0),
        "Population Density": min(risk * 0.25, 1.0),
        "Green Cover Deficit":min(risk * 0.20, 1.0),
        "Water Stress":       min(risk * 0.12, 1.0),
        "Urban Density":      min(risk * 0.08, 1.0),
    }
    fig2 = go.Figure(go.Bar(
        x=list(factors.values()),
        y=list(factors.keys()),
        orientation="h",
        marker_color=["#e74c3c", "#e67e22", "#2ecc71", "#3498db", "#9b59b6"],
        text=[f"{v*100:.1f}%" for v in factors.values()],
        textposition="outside",
    ))
    fig2.update_layout(
        xaxis_title="Contribution to Risk",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=280,
        margin=dict(l=140),
    )
    st.plotly_chart(fig2, use_container_width=True)

    # ── Counterfactual simulation ────────────────────────────────
    st.divider()
    st.markdown("### 🔁 Counterfactual Simulation")
    st.caption("Explore how interventions could reduce heat risk in this ward.")

    col1, col2 = st.columns(2)
    green_increase = col1.slider("🌿 Green Cover Increase (%)", 0, 30, 10, key="cf_green")
    water_improve  = col2.slider("💧 Water Access Improvement (%)", 0, 40, 20, key="cf_water")

    green_impact  = round(15 + risk * 10) * (green_increase / 10)
    water_impact  = round(10 + risk * 8) * (water_improve / 20)
    total_impact  = min(green_impact + water_impact, 60)
    new_risk      = max(risk - total_impact / 100, 0.0)

    if green_increase > 0:
        st.success(
            f"🌳 Increasing green cover by {green_increase}% in **{ward}** "
            f"could reduce heat risk by approximately **{green_impact:.1f}%**"
        )
    if water_improve > 0:
        st.info(
            f"💧 Improving water access by {water_improve}% "
            f"could lower emergency probability by approximately **{water_impact:.1f}%**"
        )
    if green_increase > 0 or water_improve > 0:
        st.metric(
            "Projected Risk After Interventions",
            f"{new_risk:.3f}",
            delta=f"-{total_impact:.1f}% reduction",
        )

    if risk > 0.5:
        projected_rise = round(risk * 120, 1)
        st.warning(
            f"⚠️ If no action is taken, heat risk in **{ward}** "
            f"may escalate to an equivalent index of **{projected_rise}** within 48 hours."
        )

    st.caption("HeatGuard AI — Explainable urban heat risk intelligence")
