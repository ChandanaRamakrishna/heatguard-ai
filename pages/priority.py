import streamlit as st
import pandas as pd
import plotly.express as px
import os
from datetime import datetime
import pytz

def show():
    india_tz = pytz.timezone("Asia/Kolkata")
    now = datetime.now(india_tz)

    st.title("📍 Priority Areas")
    st.caption(f"HeatGuard AI • Last updated: {now.strftime('%d %b %Y, %I:%M %p IST')}")

    # ── Load data ────────────────────────────────────────────────
    csv_path = os.path.join(
        os.path.dirname(__file__), "..", "data", "processed", "ward_priority_topsis.csv"
    )
    if not os.path.exists(csv_path):
        st.error(f"❌ Data file not found: {csv_path}")
        st.info("Ensure `ward_priority_topsis.csv` is in `data/processed/`")
        return

    vul = pd.read_csv(csv_path)
    vul.columns = vul.columns.str.strip()

    required = {"Ward", "TOPSIS_SCORE", "PRIORITY_RANK"}
    if not required.issubset(vul.columns):
        st.error(f"Missing columns. Found: {vul.columns.tolist()}")
        return

    # ── Sidebar filters ──────────────────────────────────────────
    st.sidebar.header("🔍 Filter Wards")
    top_n = st.sidebar.slider("Show Top N Wards", 5, len(vul), 10)
    min_score = st.sidebar.slider(
        "Minimum Risk Score", 0.0, float(vul["TOPSIS_SCORE"].max()), 0.0, 0.01
    )
    search = st.sidebar.text_input("Search Ward Name")

    filtered = vul[vul["TOPSIS_SCORE"] >= min_score]
    if search:
        filtered = filtered[filtered["Ward"].str.contains(search, case=False, na=False)]
    top = filtered.sort_values("PRIORITY_RANK").head(top_n)

    # ── Summary metrics ─────────────────────────────────────────
    col1, col2, col3 = st.columns(3)
    col1.metric("Wards Shown", len(top))
    col2.metric("Highest Risk Score", f"{top['TOPSIS_SCORE'].max():.3f}")
    col3.metric("Avg Score (filtered)", f"{top['TOPSIS_SCORE'].mean():.3f}")

    # ── Risk bar chart ───────────────────────────────────────────
    st.markdown("### 📊 Risk Score Ranking")
    fig = px.bar(
        top.sort_values("TOPSIS_SCORE", ascending=True),
        x="TOPSIS_SCORE",
        y="Ward",
        orientation="h",
        color="TOPSIS_SCORE",
        color_continuous_scale=["#2ecc71", "#f1c40f", "#e67e22", "#e74c3c"],
        labels={"TOPSIS_SCORE": "Risk Score"},
        text="TOPSIS_SCORE",
    )
    fig.update_traces(texttemplate="%{text:.3f}", textposition="outside")
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=max(300, len(top) * 35),
        coloraxis_showscale=False,
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── Ward cards ───────────────────────────────────────────────
    st.markdown("### 🔴 Most Vulnerable Wards")
    for _, row in top.iterrows():
        score = row["TOPSIS_SCORE"]
        rank = int(row["PRIORITY_RANK"])

        if score >= 0.70:
            alert, color_fn = "🔴 RED", st.error
        elif score >= 0.55:
            alert, color_fn = "🟠 ORANGE", st.warning
        elif score >= 0.40:
            alert, color_fn = "🟡 YELLOW", st.info
        else:
            alert, color_fn = "🟢 GREEN", st.success

        with st.expander(f"Rank #{rank} — {row['Ward']}  |  Score: {score:.3f}  |  {alert}"):
            c1, c2, c3 = st.columns(3)
            c1.metric("Priority Rank", f"#{rank}")
            c2.metric("TOPSIS Score", f"{score:.3f}")
            c3.metric("Alert Level", alert)

            # Risk drivers (inferred from score bands)
            reasons = []
            if score > 0.65:
                reasons.append("🔥 Very high surface temperature exposure")
            if score > 0.55:
                reasons.append("👥 High population density")
            if score > 0.50:
                reasons.append("💧 Water access stress")
            if score > 0.45:
                reasons.append("🌱 Low green cover / urban heat island")
            if not reasons:
                reasons.append("📋 Within acceptable thresholds — monitor routinely")

            st.markdown("**Risk Drivers:**")
            for r in reasons:
                st.write(f"  • {r}")

    # ── Data table ───────────────────────────────────────────────
    st.divider()
    st.markdown("### 📋 Full Ward Data Table")
    st.dataframe(
        filtered.sort_values("PRIORITY_RANK")[["Ward", "PRIORITY_RANK", "TOPSIS_SCORE"]],
        use_container_width=True,
        hide_index=True,
    )

    st.warning("⚠️ If resources are limited, these wards maximize life-saving impact.")
    st.caption("HeatGuard AI — A decision-support system for urban heatwave preparedness")
