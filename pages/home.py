import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import os
import sys
from datetime import datetime
from pathlib import Path
import pytz

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.alerts import ensure_alert_columns, ALERT_COLORS, ALERT_ST_FN_NAMES

BENGALURU_LAT = 12.9716
BENGALURU_LON = 77.5946


def compute_heat_index(T: float, RH: float) -> float:
    Tf = T * 9 / 5 + 32
    HI_f = (
        -42.379 + 2.04901523 * Tf + 10.14333127 * RH
        - 0.22475541 * Tf * RH - 0.00683783 * Tf ** 2
        - 0.05481717 * RH ** 2 + 0.00122874 * Tf ** 2 * RH
        + 0.00085282 * Tf * RH ** 2 - 0.00000199 * Tf ** 2 * RH ** 2
    )
    return (HI_f - 32) * 5 / 9


@st.cache_data(ttl=3600)
def fetch_current_weather():
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": BENGALURU_LAT,
        "longitude": BENGALURU_LON,
        "current": ["temperature_2m", "relative_humidity_2m", "apparent_temperature"],
        "timezone": "Asia/Kolkata",
    }
    try:
        resp = requests.get(url, params=params, timeout=8)
        resp.raise_for_status()
        cur = resp.json()["current"]
        T   = cur["temperature_2m"]
        RH  = cur["relative_humidity_2m"]
        hi  = compute_heat_index(T, RH)
        return {"temp": round(T, 1), "rh": round(RH, 1), "heat_index": round(hi, 1)}
    except Exception:
        return None


def show():
    india_tz = pytz.timezone("Asia/Kolkata")
    now = datetime.now(india_tz)

    st.title("🔥 HeatGuard AI — City Command Center")
    st.subheader("Urban Heatwave Early-Warning & Response System")
    st.caption(f"Last updated: {now.strftime('%d %b %Y, %I:%M %p IST')}")

    # ── Live weather banner ──────────────────────────────────────
    live = fetch_current_weather()
    if live:
        w1, w2, w3 = st.columns(3)
        w1.metric("🌡️ Current Temp (Bengaluru)", f"{live['temp']} °C")
        w2.metric("💧 Relative Humidity", f"{live['rh']} %")
        hi = live["heat_index"]
        if hi >= 46:   hi_label, delta_col = "DANGER", "inverse"
        elif hi >= 43: hi_label, delta_col = "EXTREME CAUTION", "inverse"
        elif hi >= 39: hi_label, delta_col = "CAUTION", "normal"
        else:          hi_label, delta_col = "NORMAL", "normal"
        w3.metric("🔥 Heat Index", f"{hi} °C", hi_label, delta_color=delta_col)
        st.caption("🌐 Live data via Open-Meteo API (refreshes every hour)")
    else:
        st.info("ℹ️ Live weather unavailable — check your network connection.")

    # ── Load ward data ───────────────────────────────────────────
    csv_path = os.path.join(
        os.path.dirname(__file__), "..", "data", "processed", "ward_priority_topsis.csv"
    )
    if not os.path.exists(csv_path):
        st.error(f"❌ Data file not found: {csv_path}")
        st.info("Make sure `ward_priority_topsis.csv` is in `data/processed/`")
        return

    vul = pd.read_csv(csv_path)
    vul.columns = vul.columns.str.strip()

    if "TOPSIS_SCORE" not in vul.columns:
        st.error(f"Column 'TOPSIS_SCORE' missing. Found: {vul.columns.tolist()}")
        return

    # ── Centralized alert classification (shared across all pages) ──
    vul = ensure_alert_columns(vul, score_col="TOPSIS_SCORE")

    avg_risk        = vul["TOPSIS_SCORE"].mean()
    red_count       = (vul["ALERT_LEVEL"] == "RED").sum()
    orange_count    = (vul["ALERT_LEVEL"] == "ORANGE").sum()
    high_risk_count = red_count + orange_count
    total_wards     = len(vul)

    # ── Alert status banner ──────────────────────────────────────
    if avg_risk >= 0.70:
        status_label  = "🔴 RED ALERT"
        status_color  = "error"
    elif avg_risk >= 0.55:
        status_label  = "🟠 ORANGE ALERT"
        status_color  = "warning"
    elif avg_risk >= 0.40:
        status_label  = "🟡 YELLOW ALERT"
        status_color  = "info"
    else:
        status_label  = "🟢 GREEN — MONITORING"
        status_color  = "success"

    getattr(st, status_color)(f"### Operational Mode: {status_label}")

    # ── KPI Metrics ──────────────────────────────────────────────
    st.markdown("### 📊 City Risk Snapshot")
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total Wards",     total_wards)
    col2.metric("High-Risk Wards", int(high_risk_count))
    col3.metric("RED Alert Wards", int(red_count))
    col4.metric("Avg Risk Score",  f"{avg_risk:.3f}")
    col5.metric("Critical NOW",    "⚠️ Yes" if avg_risk > 0.55 else "✅ No")

    # ── Ward risk distribution ───────────────────────────────────
    st.markdown("### 📈 Ward Risk Distribution")
    chart_df = vul.sort_values("PRIORITY_RANK")[["Ward", "TOPSIS_SCORE"]].set_index("Ward")
    st.bar_chart(chart_df, use_container_width=True)

    # ── Alert distribution donut ─────────────────────────────────
    st.markdown("### 🎯 Alert Level Breakdown")
    alert_counts = vul["ALERT_LEVEL"].value_counts().reset_index()
    alert_counts.columns = ["Alert", "Count"]
    fig_pie = px.pie(
        alert_counts, values="Count", names="Alert",
        color="Alert", color_discrete_map=ALERT_COLORS,
        hole=0.5,
    )
    fig_pie.update_layout(height=300, margin=dict(t=20, b=20))
    st.plotly_chart(fig_pie, use_container_width=True)

    # ── Decision Readiness ───────────────────────────────────────
    st.markdown("### 🚦 Decision Readiness Index")
    readiness = min(avg_risk / 0.9, 1.0)
    st.progress(readiness)
    st.caption(
        f"{readiness*100:.0f}% threshold — "
        f"{'⚠️ Emergency coordination recommended' if readiness > 0.7 else '✅ Continue monitoring'}"
    )

    # ── 72-hour outlook ──────────────────────────────────────────
    st.markdown("### ⏳ 72-Hour Heat Outlook")
    col_a, col_b, col_c = st.columns(3)
    col_a.warning("**Next 24 hrs**\nRisk increasing in dense wards")
    col_b.warning("**48 hrs**\nPossible Orange → Red escalation")
    col_c.info("**72 hrs**\nSustained stress without intervention")

    # ── AI Executive Brief ───────────────────────────────────────
    st.markdown("### 🤖 AI Executive Brief")
    hi_note = f" Live heat index is {live['heat_index']}°C." if live else ""
    st.info(
        f"HeatGuard AI recommends immediate preparedness actions.{hi_note} "
        "Primary drivers include rising night-time temperatures, "
        "high population density, and limited passive cooling infrastructure. "
        f"Top {int(high_risk_count)} wards require priority deployment of "
        "cooling centers and water tankers. RED-alert wards should activate "
        "emergency response immediately."
    )

    # ── Top 5 at-risk wards ──────────────────────────────────────
    st.markdown("### 🔴 Top 5 Highest-Risk Wards (Act Now)")
    top5 = vul.sort_values("TOPSIS_SCORE", ascending=False).head(5)
    for _, row in top5.iterrows():
        s = row["TOPSIS_SCORE"]
        alert = row["ALERT_LEVEL"]
        fn = getattr(st, ALERT_ST_FN_NAMES[alert])
        fn(f"**{row['Ward']}** — Risk: {s:.3f}  |  {alert} ALERT")

    st.caption("HeatGuard AI — Decision-support system for urban heatwave preparedness")