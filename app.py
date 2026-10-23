import json
import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_lottie import st_lottie

# ---------------------------------------------------------
# 1. PAGE CONFIGURATION & INITIAL STATE
# ---------------------------------------------------------
st.set_page_config(
    page_title="EcoScan - Environmental Footprint",
    page_icon="download.jpg",
    layout="wide"
)

# Page Navigation State (1 = Welcome, 2 = Onboarding Steps, 3 = Main Dashboard)
if "page" not in st.session_state:
    st.session_state.page = 1

# Helper function to load local Lottie JSON
def load_lottie_local(filepath: str):
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except Exception:
        return None

lottie_tree = load_lottie_local("kk.json")


# ---------------------------------------------------------
# PAGE 1: WELCOME / LANDING SCREEN
# ---------------------------------------------------------
if st.session_state.page == 1:
    _, center_col, _ = st.columns([1, 2, 1])
    
    with center_col:
        st.write("")
        if lottie_tree:
            st_lottie(lottie_tree, height=220, key="welcome_tree")
        
        st.markdown(
            "<h1 style='text-align: center; color: #2E7D32;'>WELCOME - TO ECO-SCAN</h1>", 
            unsafe_allow_html=True
        )
        st.markdown(
            "<h4 style='text-align: center; color: #888888; font-weight: normal; margin-top: -15px;'>"
            "your first step towards sustainability"
            "</h4>", 
            unsafe_allow_html=True
        )
        
        st.write("")
        st.write("")
        
        if st.button("PRESS TO ENTER ➔", type="primary", use_container_width=True):
            st.session_state.page = 2
            st.rerun()


# ---------------------------------------------------------
# PAGE 2: ONBOARDING STEPS
# ---------------------------------------------------------
elif st.session_state.page == 2:
    st.title("🌱 How EcoScan Works")
    st.caption("Follow these 3 simple steps to measure and reduce your dining footprint.")
    st.divider()

    col1, col2, col3 = st.columns(3, gap="large")

    with col1:
        with st.container(border=True):
            st.markdown("### 📸 Step 1")
            st.markdown("**Upload a photo of your food receipt.**")
            st.caption("Take a photo live or upload a clear receipt image / PDF invoice.")

    with col2:
        with st.container(border=True):
            st.markdown("### 📊 Step 2")
            st.markdown("**Get a detailed analysis of environmental footprints of your meal.**")
            st.caption("Calculates Carbon (CO₂), Water usage, and Land impact per unit quantity.")

    with col3:
        with st.container(border=True):
            st.markdown("### 🌱 Step 3")
            st.markdown("**Understanding and taking sustainable future steps.**")
            st.caption("Identify high-impact items and make eco-friendly food choices.")

    st.write("")
    st.write("")
    
    col_back, col_next = st.columns([1, 2])
    with col_back:
        if st.button("⬅️ Back", use_container_width=True):
            st.session_state.page = 1
            st.rerun()
    with col_next:
        if st.button("GET STARTED TO DASHBOARD 🚀", type="primary", use_container_width=True):
            st.session_state.page = 3
            st.rerun()


# ---------------------------------------------------------
# PAGE 3: MAIN DASHBOARD INTERFACE
# ---------------------------------------------------------
elif st.session_state.page == 3:
    # Header Section
    head_col, anim_col = st.columns([3, 1])
    with head_col:
        st.title("🌱 EcoScan: Receipt Footprint Tracker")
        st.caption("Upload or capture a receipt to analyze Carbon (CO₂), Water, and Land metrics.")
    with anim_col:
        if lottie_tree:
            st_lottie(lottie_tree, height=110, key="dash_tree")
            
    st.divider()

    # Sidebar Controls
    with st.sidebar:
        st.header("⚙️ EcoScan Control")
        st.write("1. 📸 Capture / Upload receipt")
        st.write("2. 🤖 AI Vision extracts items & quantities")
        st.write("3. 📊 Matched footprint metrics calculated")
        st.divider()
        
        if st.button("🔄 Restart Tour"):
            st.session_state.page = 1
            st.rerun()

    # Main Grid (Two Columns)
    left_col, right_col = st.columns([1, 1.2], gap="medium")

    # -----------------------------------------------------
    # LEFT COLUMN: Receipt Capture / Upload
    # -----------------------------------------------------
    active_receipt = None

    with left_col:
        with st.container(border=True):
            st.subheader("📸 Receipt Input")
            
            # Two Tabs: Choose file or take direct photo
            tab_upload, tab_camera = st.tabs(["📁 Upload File", "📷 Take Photo"])
            
            with tab_upload:
                file_input = st.file_uploader(
                    "Choose receipt image or PDF",
                    type=["jpg", "jpeg", "png", "pdf"]
                )
                if file_input:
                    active_receipt = file_input

            with tab_camera:
                camera_input = st.camera_input("Take a photo of your receipt")
                if camera_input:
                    active_receipt = camera_input

        # Display Preview
        if active_receipt is not None:
            with st.container(border=True):
                st.success("✅ Receipt captured successfully!")
                if hasattr(active_receipt, "type") and active_receipt.type == "application/pdf":
                    st.info("📄 PDF document attached ready for AI processing.")
                else:
                    st.image(active_receipt, caption="Receipt Preview", use_container_width=True)

    # -----------------------------------------------------
    # RIGHT COLUMN: AI Agent Processing & Footprint Results
    # -----------------------------------------------------
    with right_col:
        st.subheader("📊 Environmental Footprint Summary")
        
        # STATE 1: No receipt uploaded yet
        if active_receipt is None:
            st.info("👈 Please upload a receipt or take a photo on the left to begin analysis.")
            
            # Empty Metric Display Placeholders
            m1, m2, m3 = st.columns(3)
            with m1:
                with st.container(border=True):
                    st.metric("💨 Carbon", "-- kg")
            with m2:
                with st.container(border=True):
                    st.metric("💧 Water", "-- L")
            with m3:
                with st.container(border=True):
                    st.metric("🌱 Land", "-- m²")

        # STATE 2: Receipt uploaded -> Processing / Displaying Data
        else:
            # ---------------------------------------------------------
            # INTEGRATION POINT FOR YOUR BACKEND PARTNERS (vision.py & calc.py)
            # ---------------------------------------------------------
            # Example Partner Flow:
            # 1. raw_items = vision.process_receipt(active_receipt)
            # 2. results_df = calc.match_database(raw_items)
            # ---------------------------------------------------------
            
            # Temporary mock demonstration data structure (Partners will replace this)
            # To test error banner, set results_data = []
            results_data = [
                {"Item Name": "Milk", "Quantity": "1.5 L", "Carbon (kg CO₂)": 3.15, "Water (L)": 942, "Land (m²)": 1.8},
                {"Item Name": "Rice", "Quantity": "2 kg", "Carbon (kg CO₂)": 10.8, "Water (L)": 10000, "Land (m²)": 7.0},
                {"Item Name": "Apples", "Quantity": "0.5 kg", "Carbon (kg CO₂)": 0.4, "Water (L)": 350, "Land (m²)": 0.2}
            ]

            results_df = pd.DataFrame(results_data)

            # UNMATCHED / UNRECOGNIZED ERROR STATE
            if results_df.empty:
                st.error("⚠️ ITEM NOT RECOGNISED --- PLEASE UPLOAD A CLEARER PICTURE")
            
            # MATCHED SUCCESS STATE
            else:
                # Metric Cards
                m1, m2, m3 = st.columns(3)
                with m1:
                    with st.container(border=True):
                        st.metric("💨 Carbon", f"{results_df['Carbon (kg CO₂)'].sum():.1f} kg")
                with m2:
                    with st.container(border=True):
                        st.metric("💧 Water", f"{results_df['Water (L)'].sum():,.0f} L")
                with m3:
                    with st.container(border=True):
                        st.metric("🌱 Land", f"{results_df['Land (m²)'].sum():.1f} m²")

                st.divider()

                # Results Table & Visualizations
                tab1, tab2 = st.tabs(["📝 Itemized Footprint Table", "📈 Carbon Impact Chart"])

                with tab1:
                    # Clean table output matching exact specifications
                    st.dataframe(
                        results_df,
                        use_container_width=True,
                        hide_index=True
                    )

                with tab2:
                    fig = px.bar(
                        results_df,
                        x="Item Name",
                        y="Carbon (kg CO₂)",
                        color="Item Name",
                        hover_data=["Quantity", "Water (L)", "Land (m²)"],
                        title="Carbon Footprint by Purchased Item",
                        template="plotly_dark"
                    )
                    st.plotly_chart(fig, use_container_width=True)
