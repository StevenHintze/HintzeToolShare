import streamlit.components.v1 as components
import streamlit as st
import extra_streamlit_components as stx
from core.data_manager import DataManager
import time
import datetime

# View Imports
from views.arsenal import render_arsenal
from views.planner import render_planner
from views.lending import render_lending
from views.return_tools import render_return_tools
from views.armory import render_armory


st.set_page_config(page_title="HFTS v0.9.9", page_icon="🛠️")

# Initialize DB (Fail-Safe + Cached)
@st.cache_resource
def get_db():
    manager = DataManager()
    manager.seed_data([], [])
    return manager

dm = get_db() 

# --- COOKIE MANAGER ---
cookie_manager = stx.CookieManager()

# --- CUSTOM CSS ---
st.markdown("""
    <style>
        div[data-testid="stToast"] {
            background-color: rgba(255, 215, 0, 0.95) !important; 
            color: #000000 !important; 
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.3);
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
            border-radius: 12px;
            
            display: flex;
            flex-direction: row;
            align-items: flex-start;
            text-align: left;
            gap: 12px;
            padding: 16px;
        }
        div[data-testid="stToast"] > div:last-child {
            display: flex;
            flex-direction: column;
            justify-content: center;
        }
        div[data-testid="stToast"] p {
            font-weight: 600;
            font-size: 15px;
            margin: 0;
            line-height: 1.4;
            white-space: pre-wrap;
        }
        div[data-testid="stToast"] > div:first-child {
            font-size: 24px;
        }
        span[data-baseweb="tag"] {
            color: #000000 !important;
        }
        /* Custom Toast Notification */
        div[data-testid="stToast"] {
            background-color: #FFD700 !important; /* Yellow */
            color: #000000 !important;
            border-radius: 12px !important;
            padding: 16px !important;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1) !important;
            align-items: center !important;
        }
        /* Toast Content Layout */
        div[data-testid="stToast"] > div {
             align-items: center !important;
        }
        
        /* AI Search Toggle - Yellow and Black */
        /* The container */
        .stToggle label[data-baseweb="checkbox"] {
            border-color: transparent;
        }
        /* The checked state background (Yellow) */
        .stToggle input:checked + div {
            background-color: #FFD700 !important;
        }
        /* The checked state circle (Black) */
        .stToggle input:checked + div > div {
            background-color: #000000 !important;
        }
        /* Custom Radio Buttons (Navigation) */
        div[role="radiogroup"] > label > div:first-child {
            display: none !important;
        }
        div[role="radiogroup"] {
            display: flex;
            flex-direction: row;
            flex-wrap: nowrap;
            overflow-x: auto;
            gap: 8px;
            justify-content: flex-start; /* Align Left for Scrolling */
            background: rgba(43, 49, 62, 0.5);
            padding: 8px 4px;
            border-radius: 12px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            width: 100%; /* Full Width */
            margin-bottom: 10px;
            
            /* Hide Scrollbar */
            -webkit-overflow-scrolling: touch;
            scrollbar-width: none; /* Firefox */
            -ms-overflow-style: none;  /* IE */
        }
        div[role="radiogroup"]::-webkit-scrollbar { 
            display: none; /* Chrome/Safari */
        }
        div[role="radiogroup"] label {
            background-color: transparent !important;
            border: 1px solid transparent !important;
            padding: 4px 12px !important;
            border-radius: 16px !important;
            transition: all 0.2s ease;
            margin: 0 !important;
            white-space: nowrap !important; /* Prevent text wrap */
            flex-shrink: 0 !important;      /* Prevent smashing */
        }
        div[role="radiogroup"] label:hover {
            background-color: rgba(255, 255, 255, 0.05) !important;
            border: 1px solid rgba(255, 255, 255, 0.2) !important;
        }
        div[role="radiogroup"] label[data-checked="true"] {
            background-color: rgba(255, 255, 255, 0.1) !important;
            border: 1px solid rgba(255, 255, 255, 0.3) !important;
            font-weight: bold;
        }
        div[role="radiogroup"] label p {
            font-size: 0.95rem;
            margin: 0 !important;
            padding: 0 !important;
        }
        /* Fix Primary Button Text Color (Yellow Background requires Black Text) */
        div[data-testid="stButton"] > button[kind="primary"] {
            color: #000000 !important;
            font-weight: 600 !important;
        }
        div[data-testid="stButton"] > button[kind="primary"]:hover {
            color: #000000 !important;
            border-color: rgba(0,0,0,0.2) !important;
        }
    </style>
""", unsafe_allow_html=True)

# --- DYNAMIC DATA ---
try:
    family_df = dm.get_family_members() # Cached
    OWNER_HOMES = dict(zip(family_df['name'], family_df['household']))
    ALL_OWNERS = list(OWNER_HOMES.keys())
    ALL_HOUSEHOLDS = list(set(OWNER_HOMES.values()))
except:
    OWNER_HOMES = {}
    ALL_OWNERS = ["Admin"]
    ALL_HOUSEHOLDS = ["Main House"]

# --- AUTHENTICATION ---
if "user_info" not in st.session_state:
    st.session_state["user_info"] = None

if st.session_state.get("logout_flag", False):
    cookie_token = None
    st.session_state["logout_flag"] = False 
else:
    cookie_token = cookie_manager.get(cookie="hfts_session")

if st.session_state["user_info"] is None and cookie_token:
    user = dm.get_user_from_session(cookie_token)
    if user:
        st.session_state["user_info"] = user
        st.query_params.clear()
    else:
        cookie_manager.delete("hfts_session")

def login():
    email = st.session_state.get("email_input", "").strip().lower()
    password = st.session_state.get("password_input", "")
    
    user = dm.get_user_by_email(email)
    
    if user:
        # Check Role-Based Password
        if user['role'] == 'ADMIN':
            required_pass = st.secrets.get("ADMIN_PASSWORD")
            if not required_pass:
                st.error("⚠️ System Configuration Error: ADMIN_PASSWORD is missing in secrets.")
                return
        else:
            required_pass = st.secrets["FAMILY_PASSWORD"]

        if password == required_pass:
            dm.log_event("LOGIN", email, "Successful login")
            st.session_state["user_info"] = user
            token = dm.create_session(email)
            expires = datetime.datetime.now() + datetime.timedelta(days=7)
            cookie_manager.set("hfts_session", token, expires_at=expires)
            st.success(f"Welcome back, {user['name']}!")
            time.sleep(1)
            st.rerun()
        else:
            dm.log_event("FAILED_LOGIN", email, "Bad Password")
            st.error("Incorrect Password.")
    else:
        # User not found
        dm.log_event("FAILED_LOGIN", email, "Email not in registry")
        st.error(f"Email '{email}' not found in registry.")

if st.session_state["user_info"] is None:
    st.title("🔐 Family Login")
    with st.form("login_form"):
        st.text_input("Email Address", key="email_input")
        st.text_input("Family Password", type="password", key="password_input")
        submitted = st.form_submit_button("Log in")
    if submitted:
        login()
    st.stop()

# --- APP STARTS HERE ---
current_user = st.session_state["user_info"]
st.title(f"🛠️ Hintze Family Tool Share")

# Sidebar
st.sidebar.header("My Profile")
st.sidebar.write(f"**Name:** {current_user['name']}")
st.sidebar.write(f"**Role:** {current_user['role']}")
st.sidebar.write(f"**House:** {current_user['household']}")

if st.sidebar.button("Log Out"):
    cookie_token = cookie_manager.get(cookie="hfts_session")
    if cookie_token:
        dm.revoke_session(cookie_token)
    cookie_manager.delete("hfts_session")
    st.session_state["user_info"] = None
    st.session_state["logout_flag"] = True 
    time.sleep(1) 
    st.rerun()

# Tabs Logic
keys = ["Arsenal", "Planner"]
titles = ["🧰 Tool Arsenal", "🏗️ Project Planner"]
if current_user['role'] in ["ADMIN", "ADULT"]:
    keys.append("Lending")
    titles.append("🤝 Lend Tools")

keys.append("Return")
titles.append("🪃 Return Tools")

if current_user['role'] in ["ADMIN", "ADULT"]:
    keys.append("Armory")
    titles.append("🛡️ The Armory")

# Initialize Session State
if 'nav_tab' not in st.session_state: st.session_state['nav_tab'] = keys[0]

# Render Custom Tab Bar
# Helper Maps
id_to_title = dict(zip(keys, titles))
title_to_id = dict(zip(titles, keys))

# Get current index for Radio
curr_id = st.session_state.get('nav_tab', keys[0])
if curr_id not in keys: curr_id = keys[0]
curr_index = keys.index(curr_id)

# Render Navigation (Native Radio as Fallback)
selected_title = st.radio("Navigation", titles, index=curr_index, horizontal=True, label_visibility="collapsed")
selected_id = title_to_id[selected_title]

# Sync and Rerun if changed by user click
if selected_id != st.session_state['nav_tab']:
    st.session_state['nav_tab'] = selected_id
    st.rerun()

# Auto-scroll to selected item (JavaScript Injection - Robust Polling)
if 'last_scrolled_tab' not in st.session_state:
    st.session_state['last_scrolled_tab'] = None

if st.session_state['nav_tab'] != st.session_state['last_scrolled_tab']:
    components.html(f"""
    <script>
        (function() {{
            let attempts = 0;
            const maxAttempts = 20; // Try for ~1-2 seconds
            
            function scrollToActive() {{
                // Try finding the actual checked input, then get its parent label
                const radios = window.parent.document.querySelectorAll('div[role="radiogroup"] input[type="radio"]');
                let active = null;
                
                for (let i = 0; i < radios.length; i++) {{
                    if (radios[i].checked) {{
                        active = radios[i].closest('label');
                        break;
                    }}
                }}
                
                if (active) {{
                    active.scrollIntoView({{
                        behavior: "smooth",
                        inline: "center",
                        block: "nearest"
                    }});
                    // Once found and scrolled, stop.
                    return;
                }} else if (attempts < maxAttempts) {{
                    attempts++;
                    setTimeout(scrollToActive, 100);
                }}
            }}
            
            // Start polling
            setTimeout(scrollToActive, 100);
        }})();
    </script>
    <div style="display:none;">{st.session_state['nav_tab']}</div>
""", height=0)
    st.session_state['last_scrolled_tab'] = st.session_state['nav_tab']

# --- TAB RENDERING ---
if st.session_state['nav_tab'] == "Arsenal":
    render_arsenal(dm, current_user)

elif st.session_state['nav_tab'] == "Planner":
    render_planner(dm, current_user)

elif st.session_state['nav_tab'] == "Lending" and current_user['role'] in ["ADMIN", "ADULT"]:
    render_lending(dm, current_user)

elif st.session_state['nav_tab'] == "Return":
    render_return_tools(dm, current_user)

elif st.session_state['nav_tab'] == "Armory" and current_user['role'] in ["ADMIN", "ADULT"]:
    render_armory(dm, current_user)

