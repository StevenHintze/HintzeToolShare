import streamlit as st
import extra_streamlit_components as stx
from data_manager import DataManager
from tools_registry import check_safety 
from gemini_helper import ai_parse_tool 
import time
import datetime
import uuid

st.set_page_config(page_title="HFTS", page_icon="🛠️")

# Initialize DB
dm = DataManager()
dm.seed_data([], []) 

# --- COOKIE MANAGER ---
cookie_manager = stx.CookieManager()

# --- DYNAMIC DATA ---
try:
    family_df = dm.get_family_members()
    OWNER_HOMES = dict(zip(family_df['name'], family_df['household']))
    ALL_OWNERS = list(OWNER_HOMES.keys())
    ALL_HOUSEHOLDS = list(set(OWNER_HOMES.values()))
except:
    OWNER_HOMES = {}
    ALL_OWNERS = ["Admin"]
    ALL_HOUSEHOLDS = ["Main House"]

# --- AUTHENTICATION LOGIC ---
if "user_info" not in st.session_state:
    st.session_state["user_info"] = None

# FIX #1: Logout Handling
# Only auto-login if we aren't in the middle of logging out
cookie_email = cookie_manager.get(cookie="hfts_user")

if st.session_state["user_info"] is None and cookie_email:
    user = dm.get_user_by_email(cookie_email)
    if user:
        st.session_state["user_info"] = user
        st.query_params.clear()

def login():
    email = st.session_state.get("email_input", "").strip().lower()
    password = st.session_state.get("password_input", "")
    
    if password == st.secrets["FAMILY_PASSWORD"]:
        user = dm.get_user_by_email(email)
        if user:
            st.session_state["user_info"] = user
            expires = datetime.datetime.now() + datetime.timedelta(days=30)
            cookie_manager.set("hfts_user", email, expires_at=expires)
            st.success(f"Welcome back, {user['name']}!")
            time.sleep(1)
            st.rerun()
        else:
            st.error("Email not found in the Family Registry.")
    else:
        st.error("Incorrect Family Password.")

# Login Screen
if st.session_state["user_info"] is None:
    st.title("🔐 Family Login")
    st.text_input("Email Address", key="email_input")
    st.text_input("Family Password", type="password", key="password_input")
    if st.button("Log In"):
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
    cookie_manager.delete("hfts_user")
    st.session_state["user_info"] = None
    # Important: Sleep to give browser time to delete cookie before reload
    time.sleep(1) 
    st.rerun()

# Tabs
tabs = ["Borrow Tools", "Return Tools", "🤖 Tool Manager"]
if current_user['role'] == "ADMIN":
    tabs.append("🔐 Admin")

current_tabs = st.tabs(tabs)

# TAB 1: Borrow
with current_tabs[0]:
    st.header("Find & Borrow")
    search_query = st.text_input("🔍 I need to...", placeholder="e.g. fix a flat tire, drill concrete")
    
    available_tools = dm.get_available_tools()
    if search_query:
        available_tools = available_tools[available_tools['capabilities'].str.contains(search_query, case=False, na=False)]
    
    st.dataframe(available_tools[['name', 'brand', 'model_no', 'bin_location', 'household', 'safety_rating', 'capabilities']])

    st.subheader("Checkout")
    if not available_tools.empty:
        with st.form("borrow_form"):
            selected_tool_name = st.selectbox("Select Tool", available_tools['name'])
            days_needed = st.number_input("Days Needed", min_value=1, value=3)
            if st.form_submit_button("Mark it Borrowed"):
                tool_row = available_tools[available_tools['name'] == selected_tool_name].iloc[0]
                if check_safety(current_user['role'], tool_row['safety_rating']):
                    dm.borrow_tool(tool_row['id'], current_user['name'], days_needed)
                    st.success(f"✅ Borrowed {selected_tool_name}!")
                    st.rerun()
                else:
                    st.error(f"🚫 Safety Restriction: {tool_row['safety_rating']}")
    else:
        st.info("No matching tools found.")

# TAB 2: Return
with current_tabs[1]:
    st.header("Return Tools")
    borrowed_tools = dm.get_borrowed_tools()
    if not borrowed_tools.empty:
        st.dataframe(borrowed_tools[['name', 'borrower', 'return_date']])
        tool_to_return = st.selectbox("Select Tool", borrowed_tools['name'])
        if st.button("Mark it Returned"):
            tool_id = borrowed_tools.loc[borrowed_tools['name'] == tool_to_return, 'id'].iloc[0]
            dm.return_tool(tool_id)
            st.success("✅ Returned!")
            st.rerun()
    else:
        st.success("No tools are currently borrowed.")

# TAB 3: Tool Manager
with current_tabs[2]:
    from gemini_helper import get_ai_advice 
    st.header("Ask the Tool Manager")
    project_query = st.text_area("What project are you planning?", placeholder="e.g., I need to build a planter box...")
    
    if st.button("Get Advice"):
        if project_query:
            with st.spinner("Consulting the inventory..."):
                advice = get_ai_advice(project_query, dm.get_available_tools())
                st.markdown(advice)

# TAB 4: Admin
if current_user['role'] == "ADMIN":
    with current_tabs[3]:
        st.header("Add New Tool")
        
        st.markdown("### 🤖 Step 1: Scan Tool")
        st.info("Select the owner, paste the description, and click Auto-Fill.")
        
        # Layout
        col_ai_1, col_ai_2, col_ai_3 = st.columns([1, 2, 1])
        with col_ai_1:
            quick_owner = st.selectbox("Who bought it?", ALL_OWNERS, index=None, placeholder="Select owner...", key="ai_owner_select")
        with col_ai_2:
            raw_input = st.text_input("Paste Description", key="ai_input", label_visibility="collapsed")
        with col_ai_3:
            if st.button("✨ Auto-Fill", use_container_width=True):
                if raw_input:
                    with st.spinner("Analyzing..."):
                        ai_data = ai_parse_tool(raw_input)
                        if ai_data:
                            # FIX #2: FILL THE NEW FIELDS
                            st.session_state['form_name'] = ai_data.get('name', '')
                            st.session_state['form_brand'] = ai_data.get('brand', '')
                            st.session_state['form_model'] = ai_data.get('model_no', '')
                            st.session_state['form_caps'] = ai_data.get('capabilities', '')
                            
                            # Smart Power mapping
                            power_map = ["Manual", "Corded", "Battery", "Gas"]
                            try: 
                                p_idx = power_map.index(ai_data.get('power_source', 'Manual'))
                                st.session_state['form_power_idx'] = p_idx
                            except: 
                                st.session_state['form_power_idx'] = 0

                            try:
                                st.session_state['form_safety_index'] = ["Open", "Supervised", "Adult Only"].index(ai_data.get('safety', 'Open'))
                            except:
                                st.session_state['form_safety_index'] = 0
                            
                            if quick_owner:
                                st.session_state['form_owner'] = quick_owner
                                st.session_state['form_household'] = OWNER_HOMES.get(quick_owner, ALL_HOUSEHOLDS[0])
                            
                            st.success("✅ AI Generated Details - Please Check for Accuracy.")
                        else:
                            st.error("AI could not generate details from description.")
            else:
                st.error("Please paste a description.")

        st.markdown("---")
        st.markdown("### 📝 Step 2: Review & Save")
        
        with st.form("add_tool"):
            # Init Session State
            if 'form_name' not in st.session_state: st.session_state['form_name'] = ""
            if 'form_brand' not in st.session_state: st.session_state['form_brand'] = ""
            if 'form_model' not in st.session_state: st.session_state['form_model'] = ""
            if 'form_caps' not in st.session_state: st.session_state['form_caps'] = ""
            if 'form_safety_index' not in st.session_state: st.session_state['form_safety_index'] = 0
            if 'form_power_idx' not in st.session_state: st.session_state['form_power_idx'] = 0
            
            owner_idx = None
            if 'form_owner' in st.session_state and st.session_state['form_owner'] in ALL_OWNERS:
                 owner_idx = ALL_OWNERS.index(st.session_state['form_owner'])
            
            house_idx = None
            if 'form_household' in st.session_state and st.session_state['form_household'] in ALL_HOUSEHOLDS:
                 house_idx = ALL_HOUSEHOLDS.index(st.session_state['form_household'])

            # Form Layout
            new_name = st.text_input("Tool Name", key="form_name")
            
            c1, c2, c3 = st.columns(3)
            with c1:
                new_brand = st.text_input("Brand", key="form_brand")
            with c2:
                new_model = st.text_input("Model #", key="form_model")
            with c3:
                new_power = st.selectbox("Power", ["Manual", "Corded", "Battery", "Gas"], index=st.session_state['form_power_idx'])

            c4, c5 = st.columns(2)
            with c4:
                new_owner = st.selectbox("Owner", ALL_OWNERS, index=owner_idx, placeholder="Select owner...")
            with c5:
                new_household = st.selectbox("Location", ALL_HOUSEHOLDS, index=house_idx, placeholder="Select household...")

            new_bin = st.text_input("Specific Location", placeholder="e.g. Garage - Shelf 2", key="form_bin")
            
            new_safety = st.selectbox("Safety", ["Open", "Supervised", "Adult Only"], index=st.session_state['form_safety_index'])
            new_caps = st.text_input("Capabilities", key="form_caps")
            
            if st.form_submit_button("💾 Add to Tool Registry", use_container_width=True):
                if not new_owner or not new_household:
                    st.error("⚠️ Please select Owner and Household")
                else:
                    new_id = f"TOOL_{uuid.uuid4().hex[:6].upper()}"
                    dm.con.execute("INSERT INTO tools VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", 
                        (new_id, new_name, new_brand, new_model, new_power, new_owner, new_household, new_bin, 'Available', None, None, new_caps, new_safety))
                    st.success(f"✅ Saved: {new_name}")
                    st.rerun()