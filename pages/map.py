import streamlit as st
import pandas as pd
import pydeck as pdk
import json
import copy
import os
import sys
from datetime import datetime
from pathlib import Path
import pytz

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.alerts import ensure_alert_columns


def risk_color(x):
    """x in [0,1] -> RGBA color, green -> yellow -> orange -> red."""
    r = int(min(255, x * 2 * 255))
    g = int(min(255, (1 - x) * 2 * 255))
    return [r, g, 0, 160]


def normalize_name(name):
    """Normalize ward names for joining GeoJSON properties to the risk dataframe."""
    if name is None:
        return ""
    return str(name).strip().lower().replace(".", "").replace("  ", " ")


def show():
    india_tz = pytz.timezone("Asia/Kolkata")
    now = datetime.now(india_tz)

    st.title("🗺️ City Heat-Risk Map")
    st.caption(f"HeatGuard AI • Last updated: {now.strftime('%d %b %Y, %I:%M %p IST')}")

    base = os.path.join(os.path.dirname(__file__), "..", "data", "processed")
    priority_path = os.path.join(base, "ward_priority_topsis.csv")
    location_path = os.path.join(base, "ward_locations.csv")
    geojson_path = os.path.join(base, "heatguard_ward_boundaries.geojson")

    for path, name in [
        (priority_path, "ward_priority_topsis.csv"),
        (location_path, "ward_locations.csv"),
    ]:
        if not os.path.exists(path):
            st.error(f"❌ Missing file: {name}")
            st.info(f"Ensure `{name}` exists in `data/processed/`")
            return

    priority_df = pd.read_csv(priority_path)
    location_df = pd.read_csv(location_path)
    priority_df.columns = priority_df.columns.str.strip()
    location_df.columns = location_df.columns.str.strip()

    for col in ["lat", "lon"]:
        if col not in location_df.columns:
            alt = {"lat": ["latitude", "Lat", "LAT"], "lon": ["longitude", "lng", "Lon", "LON"]}
            found = next((a for a in alt[col] if a in location_df.columns), None)
            if found:
                location_df = location_df.rename(columns={found: col})
            else:
                st.error(f"Column `{col}` not found in ward_locations.csv. Found: {location_df.columns.tolist()}")
                return

    df = priority_df.merge(location_df, on="Ward", how="inner")
    if df.empty:
        st.error("Merge returned empty — check that Ward names match in both CSVs.")
        return

    df = ensure_alert_columns(df, score_col="TOPSIS_SCORE")

    score_min, score_max = df["TOPSIS_SCORE"].min(), df["TOPSIS_SCORE"].max()
    df["risk_norm"] = (df["TOPSIS_SCORE"] - score_min) / (score_max - score_min + 1e-9)

    st.sidebar.header("🧠 Policy Simulation")
    green_boost = st.sidebar.slider("🌿 Increase Green Cover (%)", 0, 30, 0, 1, key="green_map_boost")
    cool_infra = st.sidebar.slider("❄️ Cooling Infrastructure (%)", 0, 20, 0, 1, key="cool_infra_boost")
    map_style_choice = st.sidebar.radio("Map Style", ["Light", "Dark", "Satellite"], key="map_style")
    layer_choice = st.sidebar.radio(
        "Map Layer", ["Ward Points (Scatter)", "Ward Boundaries (Polygons)"], key="map_layer"
    )

    total_reduction = (green_boost * 0.018) + (cool_infra * 0.015)
    df["adjusted_risk"] = (df["risk_norm"] * (1 - total_reduction)).clip(0, 1)
    df["radius"] = (300 + df["adjusted_risk"] * 1200).astype(int)
    df["color"] = df["adjusted_risk"].apply(risk_color)

    original_avg = df["risk_norm"].mean()
    adjusted_avg = df["adjusted_risk"].mean()
    reduction_pct = (original_avg - adjusted_avg) / (original_avg + 1e-9) * 100

    if green_boost > 0 or cool_infra > 0:
        st.sidebar.success(f"📉 Estimated city-wide risk reduction: {reduction_pct:.1f}%")
        st.sidebar.info(
            f"🌿 Green cover +{green_boost}% → ~{green_boost*1.8:.1f}% risk drop\n\n"
            f"❄️ Cooling infra +{cool_infra}% → ~{cool_infra*1.5:.1f}% risk drop"
        )

    MAP_STYLES = {
        "Light": "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
        "Dark": "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
        "Satellite": "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json",
    }

    st.markdown("### 🗺️ City-Wide Heat Risk")

    layers = []

    if layer_choice == "Ward Boundaries (Polygons)" and os.path.exists(geojson_path):
        with open(geojson_path) as f:
            geo = json.load(f)

        geo = copy.deepcopy(geo)

        df["_ward_key"] = df["Ward"].apply(normalize_name)
        risk_lookup = df.set_index("_ward_key")["adjusted_risk"].to_dict()
        rank_lookup = df.set_index("_ward_key")["PRIORITY_RANK"].to_dict()
        score_lookup = df.set_index("_ward_key")["TOPSIS_SCORE"].to_dict()
        alert_lookup = df.set_index("_ward_key")["ALERT_LEVEL"].to_dict()

        unmatched = []
        for feat in geo["features"]:
            props = feat["properties"]
            ward_name = props.get("Ward_Name")
            key = normalize_name(ward_name)

            if key in risk_lookup:
                adj = risk_lookup[key]
                props["adjusted_risk"] = round(float(adj), 4)
                props["fill_color"] = risk_color(adj)
                props["Priority_Rank_live"] = rank_lookup[key]
                props["TOPSIS_live"] = round(float(score_lookup[key]), 4)
                props["Alert_live"] = alert_lookup[key]
            else:
                unmatched.append(ward_name)
                adj = props.get("Risk_Score", 0.3)
                props["adjusted_risk"] = round(float(adj), 4)
                props["fill_color"] = risk_color(adj)
                props["Priority_Rank_live"] = props.get("Priority_Rank")
                props["TOPSIS_live"] = round(float(props.get("Risk_Score", 0)), 4)
                props["Alert_live"] = props.get("Alert_Level")

        if unmatched:
            with st.expander(f"⚠️ {len(unmatched)} ward(s) didn't match risk data — using fallback values"):
                st.write(unmatched)

        geo_layer = pdk.Layer(
            "GeoJsonLayer",
            data=geo,
            opacity=0.65,
            stroked=True,
            filled=True,
            get_fill_color="properties.fill_color",
            get_line_color=[255, 255, 255, 120],
            line_width_min_pixels=1,
            pickable=True,
            auto_highlight=True,
        )
        layers.append(geo_layer)
        tooltip = {
            "html": (
                "<b>{Ward_Name}</b> ({Zone})<br/>"
                "Priority Rank: #{Priority_Rank_live}<br/>"
                "Risk Score: {TOPSIS_live}<br/>"
                "Adjusted Risk: {adjusted_risk}<br/>"
                "Alert: {Alert_live}"
            )
        }
    else:
        scatter_layer = pdk.Layer(
            "ScatterplotLayer",
            data=df,
            get_position="[lon, lat]",
            get_radius="radius",
            get_fill_color="color",
            pickable=True,
            auto_highlight=True,
        )
        layers.append(scatter_layer)
        tooltip = {
            "html": "<b>{Ward}</b><br/>Risk Score: {TOPSIS_SCORE}<br/>Priority Rank: {PRIORITY_RANK}<br/>Adjusted Risk: {adjusted_risk}"
        }

    view = pdk.ViewState(
        latitude=df["lat"].mean(),
        longitude=df["lon"].mean(),
        zoom=10.3,
        pitch=0,
    )
    deck = pdk.Deck(
        layers=layers,
        initial_view_state=view,
        map_style=MAP_STYLES[map_style_choice],
        tooltip=tooltip,
    )
    st.pydeck_chart(deck, use_container_width=True)

    col_a, col_b, col_c, col_d = st.columns(4)
    col_a.error("🔴 High Risk")
    col_b.warning("🟠 Medium-High")
    col_c.info("🟡 Moderate")
    col_d.success("🟢 Low Risk")

    st.divider()
    st.markdown("### 🔍 Focus on a Ward")
    selected_ward = st.selectbox("Select Ward", sorted(df["Ward"].unique()), key="focus_ward")
    ward_row = df[df["Ward"] == selected_ward].iloc[0]

    c1, c2, c3 = st.columns(3)
    c1.metric("TOPSIS Score", f"{ward_row['TOPSIS_SCORE']:.3f}")
    c2.metric("Priority Rank", f"#{int(ward_row['PRIORITY_RANK'])}")
    c3.metric("Adjusted Risk", f"{ward_row['adjusted_risk']:.3f}")

    focused_layer = pdk.Layer(
        "ScatterplotLayer",
        data=df[df["Ward"] == selected_ward],
        get_position="[lon, lat]",
        get_radius=1200,
        get_fill_color="color",
        pickable=True,
    )
    focused_view = pdk.ViewState(
        latitude=ward_row["lat"],
        longitude=ward_row["lon"],
        zoom=14,
        pitch=30,
    )
    focused_deck = pdk.Deck(
        layers=[focused_layer],
        initial_view_state=focused_view,
        map_style=MAP_STYLES[map_style_choice],
        tooltip={"html": f"<b>{selected_ward}</b><br/>Adjusted Risk: {ward_row['adjusted_risk']:.3f}"},
    )
    st.pydeck_chart(focused_deck, use_container_width=True)

    ward_reduction = ward_row["risk_norm"] - ward_row["adjusted_risk"]
    if ward_reduction > 0:
        st.success(
            f"🌳 With current interventions, heat risk in **{selected_ward}** "
            f"is estimated to reduce by **{ward_reduction/ward_row['risk_norm']*100:.1f}%** "
            f"(from {ward_row['risk_norm']:.3f} → {ward_row['adjusted_risk']:.3f})"
        )

    st.caption("HeatGuard AI — Geospatial heat-risk visualization and policy simulation")