import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(
    page_title="EcoScan",
    page_icon="🌱",
    layout="wide"
)

st.title("🌱 EcoScan: Receipt Footprint Tracker")
st.caption("Upload a receipt to estimate its environmental impact.")

with st.sidebar:
    st.header("About EcoScan")
    st.write("1. Upload a receipt")
    st.write("2. Extract purchased items")
    st.write("3. View carbon, water, and land-use impact")

left_col, right_col = st.columns([1, 1.3])

with left_col:
    st.subheader("📸 Upload Receipt")
    uploaded_file = st.file_uploader(
        "Choose a receipt image or PDF",
        type=["jpg", "jpeg", "png", "pdf"]
    )

    if uploaded_file is not None:
        st.success("Receipt uploaded successfully!")
        if uploaded_file.type.startswith("image/"):
            st.image(uploaded_file, use_container_width=True)
        else:
            st.info("PDF received. Text extraction will be added here.")
    else:
        st.info("Upload a receipt to begin.")

with right_col:
    st.subheader("📊 Environmental Footprint Summary")

    demo_items = pd.DataFrame([
        {"Item": "Milk", "Carbon (kg CO₂)": 2.1, "Water (L)": 628, "Land (m²)": 1.2},
        {"Item": "Rice", "Carbon (kg CO₂)": 5.4, "Water (L)": 5000, "Land (m²)": 3.5},
        {"Item": "Apples", "Carbon (kg CO₂)": 0.8, "Water (L)": 700, "Land (m²)": 0.4}
    ])

    m1, m2, m3 = st.columns(3)
    m1.metric("Carbon", f"{demo_items['Carbon (kg CO₂)'].sum():.1f} kg")
    m2.metric("Water", f"{demo_items['Water (L)'].sum():,.0f} L")
    m3.metric("Land", f"{demo_items['Land (m²)'].sum():.1f} m²")

    st.subheader("Extracted Items")
    st.dataframe(demo_items, use_container_width=True, hide_index=True)

    chart = px.bar(
        demo_items,
        x="Item",
        y="Carbon (kg CO₂)",
        color="Item",
        title="Carbon Footprint by Item"
    )
    st.plotly_chart(chart, use_container_width=True)
