import json
import os
import random
import re
import smtplib
from datetime import datetime
from email.message import EmailMessage
import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_lottie import st_lottie

# ---------------------------------------------------------
# 1. PAGE CONFIGURATION & CUSTOM STYLING
# ---------------------------------------------------------
st.set_page_config(
    page_title="EcoScan - Environmental Footprint",
    page_icon="🌱",
    layout="wide"
)

# Custom CSS for Red Logout Button & Accent UI
st.markdown("""
    <style>
    div.stButton > button[kind="secondary"] {
        background-color: #d32f2f !important;
        color: white !important;
        border: none !important;
        font-weight: bold !important;
    }
    div.stButton > button[kind="secondary"]:hover {
        background-color: #b71c1c !important;
        color: white !important;
    }
    </style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 2. PERSISTENT JSON DATABASE HELPERS
# ---------------------------------------------------------
USERS_FILE = "users.json"
HISTORY_FILE = "history.json"

def load_json_file(filepath: str):
    if os.path.exists(filepath):
        try:
            with open(filepath, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_json_file(filepath: str, data: dict):
    with open(filepath, "w") as f:
        json.dump(data, f, indent=4)

# Helper to load Lottie animation
def load_lottie_local(filepath: str):
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except Exception:
        return None

lottie_tree = load_lottie_local("kk.json")

# ---------------------------------------------------------
# 3. EMAIL VALIDATION & REAL SMTP OTP SENDER
# ---------------------------------------------------------
def is_valid_email(email: str) -> bool:
    """Validates email format using strict regex."""
    pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
    return bool(re.match(pattern, email.strip()))

def send_real_otp_email(receiver_email: str, otp_code: str):
    """Sends a real 6-digit OTP email using Gmail SMTP / Streamlit secrets."""
    sender_email = st.secrets.get("SMTP_EMAIL", os.environ.get("SMTP_EMAIL", ""))
    sender_password = st.secrets.get("SMTP_PASSWORD", os.environ.get("SMTP_PASSWORD", ""))

    if not sender_email or not sender_password:
        raise ValueError("SMTP credentials missing in st.secrets.")

    msg = EmailMessage()
    msg['Subject'] = "🔐 EcoScan Account Verification Code"
    msg['From'] = f"EcoScan App <{sender_email}>"
    msg['To'] = receiver_email
    msg.set_content(
        f"Welcome to EcoScan!\n\n"
        f"Your 6-digit verification code is: {otp_code}\n\n"
        f"Please enter this code in the EcoScan App to activate your account."
    )

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender_email, sender_password)
        server.send_message(msg)

# ---------------------------------------------------------
# 4. BACKEND INTEGRATION HELPER FOR VISION & CALC
# ---------------------------------------------------------
def standardize_df_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Ensures DataFrame from calc.py matches app.py expected display column names."""
    if df is None or df.empty:
        return pd.DataFrame()
    
    rename_map = {}
    for col in df.columns:
        c_lower = str(col).lower()
        if "item" in c_lower or "food" in c_lower or "name" in c_lower:
            if "Item Name" not in rename_map.values():
                rename_map[col] = "Item Name"
        elif "qty" in c_lower or "quantity" in c_lower:
            if "Quantity" not in rename_map.values():
                rename_map[col] = "Quantity"
        elif "carbon" in c_lower or "co2" in c_lower:
            if "Carbon (kg CO₂)" not in rename_map.values():
                rename_map[col] = "Carbon (kg CO₂)"
        elif "water" in c_lower:
            if "Water (L)" not in rename_map.values():
                rename_map[col] = "Water (L)"
        elif "land" in c_lower:
            if "Land (m²)" not in rename_map.values():
                rename_map[col] = "Land (m²)"

    df = df.rename(columns=rename_map)

    required_cols = ["Item Name", "Quantity", "Carbon (kg CO₂)", "Water (L)", "Land (m²)"]
    for col in required_cols:
        if col not in df.columns:
            df[col] = 0.0 if col not in ["Item Name", "Quantity"] else "N/A"

    return df[required_cols]

# ---------------------------------------------------------
# 5. GLOBAL SIDEBAR FUNCTION
# ---------------------------------------------------------
def render_sidebar():
    with st.sidebar:
        st.header("⚙️ EcoScan Control")
        if st.session_state.current_user:
            st.markdown(f"👤 Logged in as: **@{st.session_state.current_user}**")
        st.divider()

        st.subheader("📌 Navigation")
        if st.button("📊 Main Dashboard", use_container_width=True):
            st.session_state.page = "dashboard"
            st.rerun()

        if st.button("📜 View History", use_container_width=True):
            st.session_state.page = "history"
            st.rerun()

        if st.button("👤 My Profile", use_container_width=True):
            st.session_state.page = "profile"
            st.rerun()

        st.divider()

        if st.button("🚪 LOG OUT", type="secondary", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.current_user = None
            st.session_state.page = "welcome"
            st.session_state.auth_mode = "login"
            st.rerun()

# ---------------------------------------------------------
# 6. SESSION STATE INITIALIZATION
# ---------------------------------------------------------
if "page" not in st.session_state:
    st.session_state.page = "welcome"
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "current_user" not in st.session_state:
    st.session_state.current_user = None
if "auth_mode" not in st.session_state:
    st.session_state.auth_mode = "login"
if "verification_code" not in st.session_state:
    st.session_state.verification_code = None
if "pending_signup" not in st.session_state:
    st.session_state.pending_signup = {}


# =========================================================
# PAGE ROUTER
# =========================================================

# PAGE 1: WELCOME / LANDING SCREEN
if st.session_state.page == "welcome":
    _, center_col, _ = st.columns([1, 2, 1])
    
    with center_col:
        st.write("")
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
            if st.session_state.logged_in:
                st.session_state.page = "dashboard"
            else:
                st.session_state.page = "auth"
            st.rerun()


# PAGE 2: AUTHENTICATION
elif st.session_state.page == "auth":
    _, auth_col, _ = st.columns([1, 1.5, 1])
    
    with auth_col:
        st.title("🔐 EcoScan Account Portal")
        st.caption("Sign in or create a new account to sync receipt footprints across devices.")
        st.divider()

        users_db = load_json_file(USERS_FILE)

        # MODE A: LOGIN
        if st.session_state.auth_mode == "login":
            st.subheader("🔑 Sign In")
            username_or_email = st.text_input("Username or Email Address")
            password = st.text_input("Password", type="password")

            if st.button("Log In 🚀", type="primary", use_container_width=True):
                user_found = None
                clean_input = username_or_email.strip().lower()

                for uname, udata in users_db.items():
                    registered_email = udata.get("email", "").strip().lower()
                    if (uname.lower() == clean_input or registered_email == clean_input) and udata.get("password") == password:
                        user_found = uname
                        break

                if user_found:
                    st.session_state.logged_in = True
                    st.session_state.current_user = user_found
                    st.success(f"Welcome back, @{user_found}!")
                    st.session_state.page = "dashboard"
                    st.rerun()
                else:
                    st.error("Invalid username/email or password. Please try again.")

            st.write("")
            st.caption("New to EcoScan?")
            if st.button("Create New Account ➔"):
                st.session_state.auth_mode = "signup"
                st.rerun()

        # MODE B: REAL EMAIL SIGNUP
        elif st.session_state.auth_mode == "signup":
            st.subheader("📝 Create New Account")
            new_email = st.text_input("Email Address")
            new_username = st.text_input("Choose a Username (e.g., eco_warrior)")
            new_password = st.text_input("Create Password", type="password")

            if st.button("Send Verification Code 📩", type="primary", use_container_width=True):
                clean_email = new_email.strip().lower()
                clean_uname = new_username.strip()

                if not clean_email or not clean_uname or not new_password:
                    st.warning("Please fill in all fields.")
                elif not is_valid_email(clean_email):
                    st.error("⚠️ Invalid email format! Please enter a real email address (e.g., name@gmail.com).")
                elif clean_uname in users_db:
                    st.error(f"⚠️ Username '@{clean_uname}' is already registered.")
                elif any(u.get("email", "").strip().lower() == clean_email for u in users_db.values()):
                    st.error("⚠️ An account with this email already exists! Please Log In instead.")
                else:
                    otp = str(random.randint(100000, 999999))
                    st.session_state.verification_code = otp
                    st.session_state.pending_signup = {
                        "email": clean_email,
                        "username": clean_uname,
                        "password": new_password,
                        "joined_date": datetime.now().strftime("%Y-%m-%d %H:%M")
                    }

                    try:
                        send_real_otp_email(clean_email, otp)
                        st.toast(f"📩 Real OTP email sent to {clean_email}!")
                    except Exception:
                        st.toast("⚠️ Development mode activated. Use verification code on screen.", icon="ℹ️")

                    st.session_state.auth_mode = "verify"
                    st.rerun()

            st.write("")
            if st.button("⬅️ Already have an account? Log In"):
                st.session_state.auth_mode = "login"
                st.rerun()

        # MODE C: ENTER EMAIL OTP
        elif st.session_state.auth_mode == "verify":
            st.subheader("📧 Email OTP Verification")
            target_email = st.session_state.pending_signup.get("email", "")
            
            st.info(f"📩 Verification code sent to **`{target_email}`**.")

            if "SMTP_EMAIL" not in st.secrets:
                st.warning(f"💡 **[DEV MODE CODE]:** Use code **`{st.session_state.verification_code}`** to verify.")

            entered_otp = st.text_input("Enter 6-Digit Verification Code", max_chars=6)

            if st.button("Verify OTP & Activate Account ✅", type="primary", use_container_width=True):
                if entered_otp.strip() == st.session_state.verification_code:
                    uname = st.session_state.pending_signup["username"]
                    users_db[uname] = st.session_state.pending_signup
                    save_json_file(USERS_FILE, users_db)

                    st.session_state.logged_in = True
                    st.session_state.current_user = uname
                    st.success("Account verified and registered successfully!")
                    st.session_state.page = "onboarding"
                    st.rerun()
                else:
                    st.error("❌ Incorrect verification code. Please try again.")

            st.write("")
            if st.button("⬅️ Cancel & Re-enter Email"):
                st.session_state.auth_mode = "signup"
                st.rerun()


# PAGE 3: ONBOARDING STEPS
elif st.session_state.page == "onboarding":
    st.title("🌱 How EcoScan Works")
    st.caption("Follow these 3 simple steps to measure and reduce your dining footprint.")
    st.divider()

    col1, col2, col3 = st.columns(3, gap="large")

    with col1:
        with st.container(border=True):
            st.markdown("### 📸 Step 1")
            st.markdown("**Upload a photo of your food receipt.**")
            st.caption("Take a live camera photo or upload an image / PDF receipt.")

    with col2:
        with st.container(border=True):
            st.markdown("### 📊 Step 2")
            st.markdown("**Get a detailed analysis of environmental footprints.**")
            st.caption("Calculates Carbon (CO₂), Water usage, and Land impact per unit quantity.")

    with col3:
        with st.container(border=True):
            st.markdown("### 🌱 Step 3")
            st.markdown("**Understanding and taking sustainable future steps.**")
            st.caption("Identify high-impact items and track cumulative history in your profile.")

    st.write("")
    st.write("")
    
    if st.button("GET STARTED TO DASHBOARD 🚀", type="primary", use_container_width=True):
        st.session_state.page = "dashboard"
        st.rerun()


# PAGE 4: MAIN DASHBOARD INTERFACE (CONNECTED TO VISION.PY & CALC.PY)
elif st.session_state.page == "dashboard":
    render_sidebar()

    head_col, anim_col = st.columns([3, 1])
    with head_col:
        st.title("🌱 EcoScan: Receipt Footprint Tracker")
        st.caption("Upload or capture a receipt to analyze Carbon (CO₂), Water, and Land metrics.")
    with anim_col:
        if lottie_tree:
            st_lottie(lottie_tree, height=110, key="dash_tree")
            
    st.divider()

    left_col, right_col = st.columns([1, 1.2], gap="medium")

    active_receipt = None

    with left_col:
        with st.container(border=True):
            st.subheader("📸 Receipt Input")
            tab_upload, tab_camera = st.tabs(["📁 Upload File", "📷 Take Photo"])
            
            with tab_upload:
                file_input = st.file_uploader("Choose receipt image or PDF", type=["jpg", "jpeg", "png", "pdf"])
                if file_input:
                    active_receipt = file_input

            with tab_camera:
                camera_input = st.camera_input("Take a photo of your receipt")
                if camera_input:
                    active_receipt = camera_input

        if active_receipt is not None:
            with st.container(border=True):
                st.success("✅ Receipt captured successfully!")
                if hasattr(active_receipt, "type") and active_receipt.type == "application/pdf":
                    st.info("📄 PDF document attached ready for AI processing.")
                else:
                    st.image(active_receipt, caption="Receipt Preview", use_container_width=True)

    with right_col:
        st.subheader("📊 Environmental Footprint Summary")
        
        if active_receipt is None:
            st.info("👈 Please upload a receipt or take a photo on the left to begin analysis.")
            
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

        else:
            # LIVE INTEGRATION: CALLING VISION.PY AND CALC.PY
            results_df = pd.DataFrame()

            with st.spinner("🤖 AI Vision analyzing receipt and calculating footprint..."):
                try:
                    import vision
                    import calc

                    # Call vision.py
                    if hasattr(vision, "process_receipt"):
                        extracted_items = vision.process_receipt(active_receipt)
                    elif hasattr(vision, "analyze_receipt"):
                        extracted_items = vision.analyze_receipt(active_receipt)
                    elif hasattr(vision, "extract_items"):
                        extracted_items = vision.extract_items(active_receipt)
                    else:
                        extracted_items = None

                    # Call calc.py
                    if extracted_items is not None:
                        if hasattr(calc, "calculate_footprint"):
                            results_df = calc.calculate_footprint(extracted_items)
                        elif hasattr(calc, "process_items"):
                            results_df = calc.process_items(extracted_items)
                        elif hasattr(calc, "calculate_impact"):
                            results_df = calc.calculate_impact(extracted_items)
                        elif isinstance(extracted_items, pd.DataFrame):
                            results_df = extracted_items

                    results_df = standardize_df_columns(results_df)

                except Exception as e:
                    # Fallback to empty dataframe on error/non-receipt images
                    results_df = pd.DataFrame()

            # UNMATCHED / UNRECOGNIZED ERROR STATE
            if results_df.empty or results_df["Carbon (kg CO₂)"].sum() == 0:
                st.error("⚠️ ITEM NOT RECOGNISED --- PLEASE UPLOAD A CLEARER PICTURE")
            else:
                c_sum = float(results_df["Carbon (kg CO₂)"].sum())
                w_sum = float(results_df["Water (L)"].sum())
                l_sum = float(results_df["Land (m²)"].sum())

                m1, m2, m3 = st.columns(3)
                with m1:
                    with st.container(border=True):
                        st.metric("💨 Carbon", f"{c_sum:.1f} kg")
                with m2:
                    with st.container(border=True):
                        st.metric("💧 Water", f"{w_sum:,.0f} L")
                with m3:
                    with st.container(border=True):
                        st.metric("🌱 Land", f"{l_sum:.1f} m²")

                st.divider()

                tab1, tab2 = st.tabs(["📝 Itemized Footprint Table", "📈 Carbon Impact Chart"])

                with tab1:
                    st.dataframe(results_df, use_container_width=True, hide_index=True)

                with tab2:
                    fig = px.bar(
                        results_df, x="Item Name", y="Carbon (kg CO₂)", color="Item Name",
                        hover_data=["Quantity", "Water (L)", "Land (m²)"],
                        title="Carbon Footprint by Purchased Item", template="plotly_dark"
                    )
                    st.plotly_chart(fig, use_container_width=True)

                if st.button("💾 Save Scan Report to History", type="primary"):
                    history_db = load_json_file(HISTORY_FILE)
                    u = st.session_state.current_user
                    if u not in history_db:
                        history_db[u] = []

                    scan_record = {
                        "id": len(history_db[u]) + 1,
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "total_carbon": c_sum,
                        "total_water": w_sum,
                        "total_land": l_sum,
                        "items": results_df.to_dict(orient="records")
                    }
                    history_db[u].append(scan_record)
                    save_json_file(HISTORY_FILE, history_db)
                    st.success("Report saved to your History Vault!")


# PAGE 5: PROFILE PLUGIN
elif st.session_state.page == "profile":
    render_sidebar()
    
    st.title("👤 User Profile")
    st.caption("Manage your EcoScan account details and environmental statistics.")
    st.divider()

    users_db = load_json_file(USERS_FILE)
    history_db = load_json_file(HISTORY_FILE)
    
    curr_user = st.session_state.current_user
    user_info = users_db.get(curr_user, {})
    user_history = history_db.get(curr_user, [])

    total_scans = len(user_history)
    cum_carbon = sum(item.get("total_carbon", 0) for item in user_history)
    cum_water = sum(item.get("total_water", 0) for item in user_history)

    p_col1, p_col2 = st.columns([1, 2], gap="large")

    with p_col1:
        with st.container(border=True):
            st.markdown(f"### 🌿 @{curr_user}")
            st.markdown(f"**Email:** `{user_info.get('email', 'N/A')}`")
            st.markdown(f"**Member Since:** {user_info.get('joined_date', 'N/A')}")
            st.markdown("**Account Status:** Active User ✅")

    with p_col2:
        st.subheader("📈 Cumulative Lifetime Impact")
        s1, s2, s3 = st.columns(3)
        with s1:
            with st.container(border=True):
                st.metric("Total Scans", f"{total_scans}")
        with s2:
            with st.container(border=True):
                st.metric("Lifetime Carbon", f"{cum_carbon:.1f} kg")
        with s3:
            with st.container(border=True):
                st.metric("Lifetime Water", f"{cum_water:,.0f} L")


# PAGE 6: VIEW HISTORY PLUGIN
elif st.session_state.page == "history":
    render_sidebar()

    st.title("📜 Scanned Receipts History Vault")
    st.caption("Review past uploaded receipt reports and track footprint trends over time.")
    st.divider()

    history_db = load_json_file(HISTORY_FILE)
    curr_user = st.session_state.current_user
    user_history = history_db.get(curr_user, [])

    if not user_history:
        st.info("No saved receipts found in history yet. Upload a receipt on the Dashboard to save reports here!")
    else:
        for scan in reversed(user_history):
            with st.expander(f"🧾 Scan #{scan['id']} — {scan['timestamp']} (Carbon: {scan['total_carbon']:.1f} kg)"):
                m1, m2, m3 = st.columns(3)
                m1.metric("Carbon CO₂", f"{scan['total_carbon']:.1f} kg")
                m2.metric("Water Usage", f"{scan['total_water']:,.0f} L")
                m3.metric("Land Impact", f"{scan['total_land']:.1f} m²")

                st.write("**Item Breakdown:**")
                st.dataframe(pd.DataFrame(scan["items"]), use_container_width=True, hide_index=True)
