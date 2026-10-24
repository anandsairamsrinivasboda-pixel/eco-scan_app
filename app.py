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
    """
    Sends a real 6-digit OTP email using Gmail SMTP / Streamlit secrets.
    """
    # Fetch credentials from st.secrets if available, else fallback
    sender_email = st.secrets.get("SMTP_EMAIL", os.environ.get("SMTP_EMAIL", ""))
    sender_password = st.secrets.get("SMTP_PASSWORD", os.environ.get("SMTP_PASSWORD", ""))

    if not sender_email or not sender_password:
        raise ValueError(
            "SMTP credentials missing. Please add SMTP_EMAIL and SMTP_PASSWORD "
            "to .streamlit/secrets.toml to send real emails."
        )

    msg = EmailMessage()
    msg['Subject'] = "🔐 EcoScan Account Verification Code"
    msg['From'] = f"EcoScan App <{sender_email}>"
    msg['To'] = receiver_email
    msg.set_content(
        f"Welcome to EcoScan!\n\n"
        f"Your 6-digit verification code is: {otp_code}\n\n"
        f"Please enter this code in the EcoScan App to activate your account.\n"
        f"If you did not request this, please ignore this email."
    )

    # Send using SSL over port 465
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender_email, sender_password)
        server.send_message(msg)

# ---------------------------------------------------------
# 4. GLOBAL SIDEBAR FUNCTION
# ---------------------------------------------------------
def render_sidebar():
    with st.sidebar:
        st.header("⚙️ EcoScan Control")
        if st.session_state.current_user:
            st.markdown(f"👤 Logged in as: **@{st.session_state.current_user}**")
        st.divider()

        # Navigation Links
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

        # RED LOGOUT BUTTON
        if st.button("🚪 LOG OUT", type="secondary", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.current_user = None
            st.session_state.page = "welcome"
            st.session_state.auth_mode = "login"
            st.rerun()

# ---------------------------------------------------------
# 5. SESSION STATE INITIALIZATION
# ---------------------------------------------------------
if "page" not in st.session_state:
    st.session_state.page = "welcome"
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "current_user" not in st.session_state:
    st.session_state.current_user = None
if "auth_mode" not in st.session_state:
    st.session_state.auth_mode = "login"  # 'login', 'signup', 'verify'
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


# PAGE 2: AUTHENTICATION (LOGIN / REAL OTP SIGNUP / VERIFY)
elif st.session_state.page == "auth":
    _, auth_col, _ = st.columns([1, 1.5, 1])
    
    with auth_col:
        st.title("🔐 EcoScan Account Portal")
        st.caption("Sign in or create a new account to sync receipt footprints across devices.")
        st.divider()

        users_db = load_json_file(USERS_FILE)

        # -------------------------------------------------
        # MODE A: LOGIN
        # -------------------------------------------------
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

        # -------------------------------------------------
        # MODE B: REAL EMAIL SIGNUP
        # -------------------------------------------------
        elif st.session_state.auth_mode == "signup":
            st.subheader("📝 Create New Account")
            new_email = st.text_input("Email Address (e.g., user@example.com)")
            new_username = st.text_input("Choose a Username (e.g., eco_warrior)")
            new_password = st.text_input("Create Password", type="password")

            if st.button("Send Verification Code 📩", type="primary", use_container_width=True):
                clean_email = new_email.strip().lower()
                clean_uname = new_username.strip()

                # Check 1: Missing Fields
                if not clean_email or not clean_uname or not new_password:
                    st.warning("Please fill in all fields.")
                
                # Check 2: Valid Email Syntax
                elif not is_valid_email(clean_email):
                    st.error("⚠️ Invalid email format! Please enter a real email address (e.g., name@gmail.com).")

                # Check 3: Check if Username is Already Registered
                elif clean_uname in users_db:
                    st.error(f"⚠️ Username '@{clean_uname}' is already registered. Please choose another.")

                # Check 4: Check if Email is Already Registered
                elif any(u.get("email", "").strip().lower() == clean_email for u in users_db.values()):
                    st.error("⚠️ An account with this email already exists! Please Log In instead.")

                else:
                    # Generate 6-Digit Real OTP Code
                    otp = str(random.randint(100000, 999999))
                    
                    with st.spinner(f"Sending real OTP email to {clean_email}..."):
                        try:
                            send_real_otp_email(clean_email, otp)
                            st.session_state.verification_code = otp
                            st.session_state.pending_signup = {
                                "email": clean_email,
                                "username": clean_uname,
                                "password": new_password,
                                "joined_date": datetime.now().strftime("%Y-%m-%d %H:%M")
                            }
                            st.session_state.auth_mode = "verify"
                            st.rerun()

                        except Exception as e:
                            # Useful error feedback if SMTP secrets are not set up yet
                            st.error(f"❌ Could not send email: {e}")
                            st.info(
                                "💡 **Setup Tip:** Add your Gmail App Password to `.streamlit/secrets.toml` "
                                "to send live emails!"
                            )

            st.write("")
            if st.button("⬅️ Already have an account? Log In"):
                st.session_state.auth_mode = "login"
                st.rerun()

        # -------------------------------------------------
        # MODE C: ENTER REAL EMAIL OTP
        # -------------------------------------------------
        elif st.session_state.auth_mode == "verify":
            st.subheader("📧 Email OTP Verification")
            target_email = st.session_state.pending_signup.get("email", "")
            
            st.success(f"📩 An actual 6-digit verification code was sent to **`{target_email}`**. Please check your inbox / spam folder!")

            entered_otp = st.text_input("Enter 6-Digit Verification Code", max_chars=6)

            if st.button("Verify OTP & Activate Account ✅", type="primary", use_container_width=True):
                if entered_otp.strip() == st.session_state.verification_code:
                    uname = st.session_state.pending_signup["username"]
                    users_db[uname] = st.session_state.pending_signup
                    save_json_file(USERS_FILE, users_db)

                    # Auto login and proceed to onboarding
                    st.session_state.logged_in = True
                    st.session_state.current_user = uname
                    st.success("Account verified and registered successfully!")
                    st.session_state.page = "onboarding"
                    st.rerun()
                else:
                    st.error("❌ Incorrect verification code. Please check your inbox and try again.")

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


# PAGE 4: MAIN DASHBOARD INTERFACE
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
            try:
                from pathlib import Path
                from vision import parse_receipt
                from calc import calculate_impact, load_environmental_data

                environmental_data = load_environmental_data(
                    Path(__file__).with_name("data.csv")
                )
                receipt_items = parse_receipt(active_receipt, environmental_data)
                impact_rows, summary = calculate_impact(
                    receipt_items, environmental_data
                )

                per_kg_mode = summary["per_kg_mode"]
                by_food = summary["by_food"]
                results_df = pd.DataFrame({
                    "Item Name": by_food["Product"],
                    "Quantity": (
                        ["1 kg reference" for _ in range(len(by_food))]
                        if per_kg_mode
                        else by_food["Quantity_kg"].map(lambda value: f"{value:g} kg")
                    ),
                    "Carbon (kg CO₂)": by_food["CO2_total_kg"],
                    "Water (L)": by_food["Water_total_litres"],
                    "Land (m²)": by_food["Land_total_m2"],
                })
                report_df = summary["report_table"]
                scan_error = None
            except Exception as error:
                results_df = pd.DataFrame()
                report_df = pd.DataFrame()
                summary = None
                per_kg_mode = False
                scan_error = error

            if scan_error is not None:
                st.error(f"Could not analyze this receipt: {scan_error}")
            elif results_df.empty:
                st.error("⚠️ No food items were recognized. Please upload a clearer receipt.")
            else:
                totals = summary["totals"]
                c_total = totals["carbon"]["total"]
                w_total = totals["water"]["total"]
                l_total = totals["land"]["total"]
                unit_suffix = "/kg reference" if per_kg_mode else ""

                m1, m2, m3 = st.columns(3)
                with m1:
                    with st.container(border=True):
                        st.metric(
                            f"💨 Carbon{unit_suffix}",
                            "--" if c_total is None else f"{c_total:.3f} kg CO₂e",
                        )
                with m2:
                    with st.container(border=True):
                        st.metric(
                            f"💧 Water{unit_suffix}",
                            "--" if w_total is None else f"{w_total:,.3f} L",
                        )
                with m3:
                    with st.container(border=True):
                        st.metric(
                            f"🌱 Land{unit_suffix}",
                            "--" if l_total is None else f"{l_total:.4f} m²",
                        )

                if per_kg_mode:
                    st.caption(
                        "At least one receipt amount had no readable unit. "
                        "All listed foods are compared using the database values per 1 kg."
                    )

                st.divider()
                tab1, tab2 = st.tabs(["📝 Itemized Footprint Table", "📈 Carbon Impact Chart"])
                with tab1:
                    st.dataframe(report_df, use_container_width=True, hide_index=True)
                    if summary["suggestions"]:
                        st.markdown("#### Suggestions")
                        for suggestion in summary["suggestions"]:
                            st.write(
                                f"For {suggestion['measure']}, you can prefer "
                                f"{suggestion['alternative']} instead of {suggestion['food']} "
                                f"(estimated reduction: {suggestion['reduction_percent']:.2f}%)."
                            )
                with tab2:
                    fig = px.bar(
                        results_df,
                        x="Item Name",
                        y="Carbon (kg CO₂)",
                        color="Item Name",
                        hover_data=["Quantity", "Water (L)", "Land (m²)"],
                        title=(
                            "Carbon Footprint per 1 kg Reference"
                            if per_kg_mode
                            else "Carbon Footprint by Purchased Item"
                        ),
                        template="plotly_dark",
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
                        "total_carbon": c_total,
                        "total_water": w_total,
                        "total_land": l_total,
                        "per_kg_mode": per_kg_mode,
                        "items": results_df.to_dict(orient="records"),
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
            st.markdown("**Account Status:** Verified ✅")

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
 
