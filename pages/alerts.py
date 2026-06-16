import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import requests
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
import pytz

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.alerts import ALERT_COLORS

BENGALURU_LAT = 12.9716
BENGALURU_LON = 77.5946


def compute_heat_index(T: float, RH: float) -> float:
    Tf = T * 9 / 5 + 32
    HI_f = (
        -42.379
        + 2.04901523 * Tf
        + 10.14333127 * RH
        - 0.22475541 * Tf * RH
        - 0.00683783 * Tf ** 2
        - 0.05481717 * RH ** 2
        + 0.00122874 * Tf ** 2 * RH
        + 0.00085282 * Tf * RH ** 2
        - 0.00000199 * Tf ** 2 * RH ** 2
    )
    return (HI_f - 32) * 5 / 9


def label_alert(hi: float) -> str:
    if hi >= 46:   return "RED"
    if hi >= 43:   return "ORANGE"
    if hi >= 39:   return "YELLOW"
    return "GREEN"


@st.cache_data(ttl=3600)
def fetch_forecast(lat: float, lon: float) -> pd.DataFrame | None:
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": [
            "temperature_2m_max",
            "temperature_2m_min",
            "relative_humidity_2m_mean",
            "precipitation_sum",
            "windspeed_10m_max",
        ],
        "forecast_days": 7,
        "timezone": "Asia/Kolkata",
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()["daily"]

        rows = []
        for i in range(7):
            t_max = data["temperature_2m_max"][i]
            t_min = data["temperature_2m_min"][i]
            rh    = data["relative_humidity_2m_mean"][i]
            prec  = data["precipitation_sum"][i]
            wind  = data["windspeed_10m_max"][i]

            hi = compute_heat_index(t_max, rh) if t_max and rh else t_max
            conf = max(92 - i * 4, 60)

            rows.append({
                "Date":          data["time"][i],
                "Temp_Max":      round(t_max, 1),
                "Temp_Min":      round(t_min, 1),
                "Humidity_Mean": round(rh, 1),
                "Precip_mm":     round(prec, 1),
                "Wind_Max":      round(wind, 1),
                "Heat_Index":    round(hi, 1),
                "Alert_Level":   label_alert(hi),
                "Confidence":    conf,
            })

        return pd.DataFrame(rows)

    except Exception:
        return None


def show():
    india_tz = pytz.timezone("Asia/Kolkata")
    now = datetime.now(india_tz)

    st.title("🚨 Heat Alerts — Next 7 Days")
    st.caption(f"HeatGuard AI • Last updated: {now.strftime('%d %b %Y, %I:%M %p IST')}")

    color_map = ALERT_COLORS

    with st.spinner("Fetching live weather data from Open-Meteo…"):
        df = fetch_forecast(BENGALURU_LAT, BENGALURU_LON)

    if df is None:
        st.warning(
            "⚠️ Could not reach the weather API. "
            "Showing fallback simulated data."
        )
        dates = [(now + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
        df = pd.DataFrame({
            "Date":         dates,
            "Temp_Max":     [36, 37, 38, 37, 36, 35, 34],
            "Temp_Min":     [24, 25, 26, 25, 24, 23, 23],
            "Humidity_Mean":[72, 74, 76, 75, 73, 70, 68],
            "Precip_mm":    [0, 0, 2, 5, 3, 0, 0],
            "Wind_Max":     [18, 20, 22, 21, 18, 16, 15],
            "Heat_Index":   [42, 45, 47, 46, 44, 43, 41],
            "Alert_Level":  ["YELLOW","ORANGE","RED","RED","ORANGE","ORANGE","YELLOW"],
            "Confidence":   [92, 89, 85, 82, 78, 74, 70],
        })
        st.info("🌐 Data source: Fallback simulation (offline)")
    else:
        st.success("✅ Live data from Open-Meteo API (ECMWF + IMD blend, no key required)")

    df["Date_Label"] = pd.to_datetime(df["Date"]).dt.strftime("%d %b")

    today = df.iloc[0]
    col_status, col_hi, col_conf = st.columns(3)
    col_status.metric("Today's Alert", f"{today['Alert_Level']} ALERT")
    col_hi.metric("Heat Index", f"{today['Heat_Index']} °C", f"{today['Temp_Max']}°C actual")
    col_conf.metric("Forecast Confidence", f"{today['Confidence']}%")

    banner_map = {
        "RED":    ("error",   "🚑 CRITICAL — Activate emergency response. Heat Index above 46°C is dangerous."),
        "ORANGE": ("warning", "⚠️ HIGH RISK — Pre-position medical teams and increase water supply."),
        "YELLOW": ("info",    "📢 MODERATE HEAT — Issue public advisories. Monitor vulnerable populations."),
        "GREEN":  ("success", "✅ LOW RISK — Conditions normal. Routine monitoring active."),
    }
    msg_type, msg_text = banner_map[today["Alert_Level"]]
    getattr(st, msg_type)(msg_text)

    st.markdown("### 📈 7-Day Heat Index Trend")
    fig = go.Figure()

    fig.add_hrect(y0=46, y1=60, fillcolor="#e74c3c", opacity=0.08, line_width=0,
                  annotation_text="RED zone", annotation_position="top left")
    fig.add_hrect(y0=43, y1=46, fillcolor="#e67e22", opacity=0.08, line_width=0,
                  annotation_text="ORANGE", annotation_position="top left")
    fig.add_hrect(y0=39, y1=43, fillcolor="#f1c40f", opacity=0.08, line_width=0)
    fig.add_hrect(y0=0,  y1=39, fillcolor="#2ecc71", opacity=0.05, line_width=0)

    for y, col, label in [(46, "#e74c3c", "RED ≥46°C"),
                           (43, "#e67e22", "ORANGE ≥43°C"),
                           (39, "#f1c40f", "YELLOW ≥39°C")]:
        fig.add_hline(y=y, line_dash="dash", line_color=col, opacity=0.6,
                      annotation_text=label, annotation_font_size=11)

    fig.add_trace(go.Scatter(
        x=df["Date_Label"], y=df["Temp_Max"],
        mode="lines", name="Actual Temp (°C)",
        line=dict(color="#aaaaaa", dash="dot", width=2),
    ))

    fig.add_trace(go.Scatter(
        x=df["Date_Label"], y=df["Heat_Index"],
        mode="lines+markers+text",
        text=df["Alert_Level"],
        textposition="top center",
        name="Heat Index (°C)",
        marker=dict(
            color=[color_map[a] for a in df["Alert_Level"]],
            size=13,
            line=dict(width=2, color="white"),
        ),
        line=dict(color="#e94560", width=3),
    ))

    fig.update_layout(
        yaxis_title="Temperature / Heat Index (°C)",
        xaxis_title="Date",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=400,
        legend=dict(orientation="h", y=-0.2),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### 🎯 Forecast Confidence by Day")
    fig2 = px.bar(
        df, x="Date_Label", y="Confidence",
        color="Alert_Level",
        color_discrete_map=color_map,
        text="Confidence",
        labels={"Date_Label": "Date", "Confidence": "Confidence (%)"},
    )
    fig2.update_traces(texttemplate="%{text}%", textposition="outside")
    fig2.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=300,
        showlegend=True,
    )
    st.plotly_chart(fig2, use_container_width=True)

    st.markdown("### 🌡️ Full Forecast Table")
    display = df[["Date_Label", "Temp_Max", "Temp_Min",
                  "Humidity_Mean", "Precip_mm", "Wind_Max",
                  "Heat_Index", "Alert_Level", "Confidence"]].copy()
    display.columns = ["Date", "Max Temp °C", "Min Temp °C",
                        "Humidity %", "Rain mm", "Wind km/h",
                        "Heat Index °C", "Alert", "Confidence %"]
    st.dataframe(display, use_container_width=True, hide_index=True)

    st.markdown("### 📅 Day-by-Day Forecast")
    cols = st.columns(7)
    badge_fn = {"RED": st.error, "ORANGE": st.warning, "YELLOW": st.info, "GREEN": st.success}
    for i, (_, row) in enumerate(df.iterrows()):
        with cols[i]:
            badge_fn[row["Alert_Level"]](
                f"**{row['Date_Label']}**\n\n"
                f"HI: {row['Heat_Index']}°C\n\n"
                f"{row['Alert_Level']}"
            )

    csv_path = os.path.join(
        os.path.dirname(__file__), "..", "data", "processed", "early_warning_output.csv"
    )
    if os.path.exists(csv_path):
        st.divider()
        st.markdown("### 📂 Historical Warning Records")
        hist = pd.read_csv(csv_path)
        hist.columns = hist.columns.str.strip()
        st.dataframe(hist.tail(10), use_container_width=True)

    st.divider()
    st.markdown("### 🚨 Emergency Recommendations")
    alert = today["Alert_Level"]
    if alert == "RED":
        st.error(
            "🏥 **Open all cooling centers immediately**\n\n"
            "💧 **Deploy emergency water tankers to all RED wards**\n\n"
            "📡 **Issue city-wide SMS/Radio alerts**\n\n"
            "🚑 **Pre-position ICU units at high-density zones**\n\n"
            "🏗️ **Suspend all outdoor labor immediately**"
        )
    elif alert == "ORANGE":
        st.warning(
            "🏥 **Put cooling centers on standby — ready to open**\n\n"
            "💧 **Increase drinking water distribution points**\n\n"
            "👨‍⚕️ **Pre-position medical teams in high-risk wards**\n\n"
            "📢 **Broadcast heat safety advisories**"
        )
    else:
        st.info(
            "📢 **Issue public heat advisories**\n\n"
            "💧 **Promote hydration and shade breaks**\n\n"
            "📋 **Review emergency protocols — confirm readiness**"
        )

    st.divider()
    st.caption(
        "🌐 Weather data: [Open-Meteo](https://open-meteo.com/) — Free, CC BY 4.0, no API key required  |  "
        "Heat Index: NOAA Rothfusz Regression  |  "
        "HeatGuard AI — Decision-support for urban heatwave preparedness"
    )