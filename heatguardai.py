import streamlit as st

st.set_page_config(
    page_title="HeatGuard AI",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for professional look
st.markdown("""
<style>
    [data-testid="stSidebar"] {background-color: #1a1a2e;}
    [data-testid="stSidebar"] * {color: #eee !important;}
    .metric-card {
        background: linear-gradient(135deg, #1a1a2e, #16213e);
        border-radius: 12px;
        padding: 1rem;
        border-left: 4px solid #e94560;
    }
    .stAlert {border-radius: 10px;}
</style>
""", unsafe_allow_html=True)

st.sidebar.image("https://img.icons8.com/fluency/48/fire.png", width=48)
st.sidebar.title("HeatGuard AI")
st.sidebar.caption("Urban Heatwave Response System")
st.sidebar.divider()

page = st.sidebar.radio(
    "Navigate",
    [
        "🏠 Home",
        "🚨 Heat Alerts",
        "📍 Priority Areas",
        "🗺️ Risk Map",
        "🚑 Action Plan",
        "🧠 AI Explanation"
    ]
)

st.sidebar.divider()
st.sidebar.caption("© 2025 HeatGuard AI | Built for Imagine Cup 2026")

if page == "🏠 Home":
    from pages.home import show
    show()
elif page == "🚨 Heat Alerts":
    from pages.alerts import show
    show()
elif page == "📍 Priority Areas":
    from pages.priority import show
    show()
elif page == "🗺️ Risk Map":
    from pages.map import show
    show()
elif page == "🚑 Action Plan":
    from pages.actions import show
    show()
elif page == "🧠 AI Explanation":
    from pages.explain import show
    show()
