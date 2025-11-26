import streamlit as st
import extra_streamlit_components as stx
from data_manager import DataManager
from tools_registry import check_safety 
from gemini_helper import ai_parse_tool, get_ai_advice, get_smart_recommendations, ai_filter_inventory
import time
import datetime
import uuid
import pandas as pd

st.set_page_config(page_title="HFTS v0.9.13", page_icon="🛠️")

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

# --- AUTHENTICATION ---
if "user_info" not in st.session_state:
    st.session_state["user_info"] = None

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
    time.sleep(1) 
    st.rerun()

# Tabs
tabs = ["Borrow Tools", "Return Tools", "🤖 Tool Manager"]
if current_user['role'] == "ADMIN":
    tabs.append("🔐 Admin")

current_tabs = st.tabs(tabs)

# TAB 1: Inventory & Courier
with current_tabs[0]:
    st.header("Family Inventory")
    
    # Layout: Search + Toggle
    c1, c2 = st.columns([5, 1], vertical_alignment="bottom")
    with c1:
        query = st.text_input("🔎 Search or Ask...", placeholder="e.g. 'Automotive tools' or 'What has Shawn borrowed?'")
    with c2:
        use_ai = st.toggle("AI Search", value=False)

    # Filter Logic
    all_tools = dm.con.execute("SELECT * FROM tools").df()
    filtered_df = all_tools
    
    if query:
        if use_ai:
            with st.spinner("AI is filtering..."):
                match_ids = ai_filter_inventory(query, all_tools)
                filtered_df = all_tools[all_tools['id'].isin(match_ids)]
        else:
            mask = (
                all_tools['name'].str.contains(query, case=False, na=False) | 
                all_tools['brand'].str.contains(query, case=False, na=False) |
                all_tools['capabilities'].str.contains(query, case=False, na=False)
            )
            filtered_df = all_tools[mask]

    # Display Inventory
    # FIX 1: Visually mark stationary items
    def format_location(row):
        loc = f"{row['household']} ({row['bin_location']})"
        if row.get('is_stationary'):
            loc += " ⚓ [Fixed]"
        return loc

    filtered_df['Location Info'] = filtered_df.apply(format_location, axis=1)
    
    def get_status_display(row):
        if row['status'] == 'Borrowed':
            return f"⛔ With {row['borrower']}"
        return "✅ Available"
    
    filtered_df['Display Status'] = filtered_df.apply(get_status_display, axis=1)

    st.dataframe(
        filtered_df[['name', 'brand', 'Display Status', 'Location Info', 'return_date']],
        column_config={
            "return_date": st.column_config.DatetimeColumn("Due Back", format="D MMM")
        },
        use_container_width=True
    )

    st.markdown("---")

    # Manual Borrowing
    st.subheader("⚡ Quick Borrow")
    
    # FIX 2: Filter out Stationary tools from the dropdown
    # We use .fillna(False) to handle any old data that might be null
    available_only = all_tools[
        (all_tools['status'] == 'Available') & 
        (all_tools['is_stationary'] != True) 
    ]
    
    if not available_only.empty:
        with st.form("manual_borrow"):
            col_b1, col_b2 = st.columns([3, 1])
            with col_b1:
                target_tool_name = st.selectbox("Select Tool", available_only['name'])
            with col_b2:
                days = st.number_input("Days", min_value=1, value=7)
            
            if st.form_submit_button("Confirm Borrowed"):
                tool_row = available_only[available_only['name'] == target_tool_name].iloc[0]
                
                if check_safety(current_user['role'], tool_row['safety_rating']):
                    dm.borrow_tool(tool_row['id'], current_user['name'], days)
                    st.success(f"✅ You borrowed the {target_tool_name}!")
                    
                    # Courier Logic
                    pickup_household = tool_row['household']
                    resident_name = None
                    for owner, house in OWNER_HOMES.items():
                        if house == pickup_household:
                            resident_name = owner
                            break
                    
                    if resident_name:
                        courier_candidates = all_tools[
                            (all_tools['borrower'] == resident_name) & 
                            (all_tools['status'] == 'Borrowed')
                        ]
                        
                        if not courier_candidates.empty:
                            st.info(f"🚛 **Courier Opportunity!**")
                            st.write(f"Since you are going to **{pickup_household}**, {resident_name} has these items checked out:")
                            for idx, c_row in courier_candidates.iterrows():
                                st.markdown(f"- **{c_row['name']}** (Owned by {c_row['owner']}) - Due: {c_row['return_date']}")
                            st.caption("Ask them if you can save them a trip and return these!")
                    
                    time.sleep(6)
                    st.rerun()
                else:
                    st.error("🚫 Safety Restriction.")
    else:
        st.info("No transportable tools available right now.")

# TAB 2: My Workbench
with current_tabs[1]:
    st.header("My Workbench & Assets")
    all_tools = dm.con.execute("SELECT * FROM tools").df()
    my_loans = all_tools[all_tools['borrower'] == current_user['name']]
    
    st.subheader("🛠️ Tools I have Borrowed")
    if not my_loans.empty:
        my_loans['Due In'] = (pd.to_datetime(my_loans['return_date']) - pd.Timestamp.now()).dt.days
        def color_status(days):
            if days < 0: return "🔴 Overdue"
            if days <= 2: return "🟠 Due Soon"
            return "🟢 On Track"
        my_loans['Status'] = my_loans['Due In'].apply(color_status)

        st.dataframe(my_loans[['name', 'brand', 'household', 'return_date', 'Status']])
        
        tool_to_return = st.selectbox("Select tool to return:", my_loans['name'], key="return_select")
        if st.button("✅ Return Selected Tool"):
            tid = my_loans[my_loans['name'] == tool_to_return].iloc[0]['id']
            dm.return_tool(tid)
            st.success(f"Returned {tool_to_return}!")
            st.rerun()
    else:
        st.info("You don't owe anyone anything.")

    st.markdown("---")
    
    my_assets = all_tools[(all_tools['owner'] == current_user['name']) & (all_tools['status'] == 'Borrowed')]
    st.subheader("👀 Who has my stuff?")
    if not my_assets.empty:
        st.warning(f"You have {len(my_assets)} tools currently loaned out.")
        st.dataframe(my_assets[['name', 'borrower', 'return_date']])
        
        tool_back = st.selectbox("Select tool received:", my_assets['name'], key="owner_return_select")
        if st.button("📥 Mark as Received"):
            tid = my_assets[my_assets['name'] == tool_back].iloc[0]['id']
            dm.return_tool(tid)
            st.success(f"Marked {tool_back} as returned.")
            st.rerun()
    else:
        st.success("All your tools are safe at home.")

# TAB 3: Smart Tool Manager
with current_tabs[2]:
    st.header("Ask the Tool Manager")
    
    if "ai_recs" not in st.session_state:
        st.session_state["ai_recs"] = None

    if st.session_state["ai_recs"] is None:
        st.info(f"Planning a project? I'll check your household first, then look for loans.")
        project_query = st.text_area("Describe your project:", placeholder="e.g. I need to sand and stain the deck...")
        
        if st.button("Analyze Needs"):
            if project_query:
                with st.spinner("Checking inventory..."):
                    all_tools_df = dm.con.execute("SELECT * FROM tools").df()
                    recs = get_smart_recommendations(project_query, all_tools_df, current_user['household'])
                    if recs:
                        st.session_state["ai_recs"] = recs
                        st.rerun()
    else:
        recs = st.session_state["ai_recs"]
        if st.button("← New Search"):
            st.session_state["ai_recs"] = None
            st.rerun()

        if recs.get('locate_list'):
            st.success("✅ **You already own these:**")
            for item in recs['locate_list']:
                st.markdown(f"- **{item['tool_name']}**")
        
        if recs.get('track_down_list'):
            st.warning("⚠️ **You own these, but they are gone:**")
            for item in recs['track_down_list']:
                st.markdown(f"- **{item['tool_name']}** is with **{item['held_by']}**")

        if recs.get('borrow_list'):
            st.info("🛒 **Logistics Plan:**")
            with st.form("smart_borrow"):
                selected_ids = []
                for item in recs['borrow_list']:
                    label = f"**{item['name']}** from {item['household']}"
                    if st.checkbox(label, value=True, help=item['reason']):
                        selected_ids.append(item['tool_id'])
                
                days = st.number_input("Days needed:", min_value=1, value=7)
                if st.form_submit_button("Confirm Borrow Request"):
                    for tid in selected_ids:
                        dm.borrow_tool(tid, current_user['name'], days)
                    st.success("Tools borrowed!")
                    st.session_state["ai_recs"] = None
                    st.rerun()

# TAB 4: Admin
if current_user['role'] == "ADMIN":
    with current_tabs[3]:
        st.header("Add New Tool")
        
        # --- SECTION 1: AI HELPER ---
        st.markdown("### 🤖 Step 1: Scan Tool")
        st.info("Select the owner, paste the description, and click Auto-Fill.")
        
        # Wrapped in Form for Enter Key support
        with st.form("ai_prefill_form"):
            c_ai_1, c_ai_2 = st.columns([1, 3], vertical_alignment="bottom")
            with c_ai_1:
                quick_owner = st.selectbox("Who owns it?", ALL_OWNERS, index=None, placeholder="Owner...", key="ai_owner_select")
            with c_ai_2:
                raw_input = st.text_input("Paste Description", key="ai_input")
            
            trigger_ai = st.form_submit_button("✨ Auto-Fill", use_container_width=True)

        if trigger_ai:
            if raw_input:
                with st.spinner("Analyzing..."):
                    ai_data = ai_parse_tool(raw_input)
                    if ai_data:
                        st.session_state['form_name'] = ai_data.get('name', '')
                        st.session_state['form_brand'] = ai_data.get('brand', '')
                        st.session_state['form_model'] = ai_data.get('model_no', '')
                        st.session_state['form_caps'] = ai_data.get('capabilities', '')
                        st.session_state['form_stationary'] = ai_data.get('is_stationary', False)
                        
                        try: 
                            p_options = ["Manual", "Corded", "Battery", "Gas", "Pneumatic", "Hydraulic"]
                            st.session_state['form_power_idx'] = p_options.index(ai_data.get('power_source', 'Manual'))
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
                        st.rerun()
                    else:
                        st.error("AI could not generate details from description.")
            else:
                st.error("Please paste a description.")

        st.markdown("---")
        st.markdown("### 📝 Step 2: Review & Save")
        
        with st.form("add_tool"):
            if 'form_name' not in st.session_state: st.session_state['form_name'] = ""
            if 'form_brand' not in st.session_state: st.session_state['form_brand'] = ""
            if 'form_model' not in st.session_state: st.session_state['form_model'] = ""
            if 'form_caps' not in st.session_state: st.session_state['form_caps'] = ""
            if 'form_safety_index' not in st.session_state: st.session_state['form_safety_index'] = 0
            if 'form_power_idx' not in st.session_state: st.session_state['form_power_idx'] = 0
            
            owner_idx = 0
            if 'form_owner' in st.session_state and st.session_state['form_owner'] in ALL_OWNERS:
                 owner_idx = ALL_OWNERS.index(st.session_state['form_owner'])
            
            house_idx = 0
            if 'form_household' in st.session_state and st.session_state['form_household'] in ALL_HOUSEHOLDS:
                 house_idx = ALL_HOUSEHOLDS.index(st.session_state['form_household'])

            new_name = st.text_input("Tool Name", key="form_name")
            
            c1, c2, c3 = st.columns(3)
            with c1:
                new_brand = st.text_input("Brand", key="form_brand")
            with c2:
                new_model = st.text_input("Model #", key="form_model")
            with c3:
                new_power = st.selectbox("Power", ["Manual", "Corded", "Battery", "Gas", "Pneumatic", "Hydraulic"], index=st.session_state['form_power_idx'])

            c4, c5 = st.columns(2)
            with c4:
                new_owner = st.selectbox("Owner", ALL_OWNERS, index=owner_idx, placeholder="Select owner...")
            with c5:
                new_household = st.selectbox("Location", ALL_HOUSEHOLDS, index=house_idx, placeholder="Select household...")

            new_bin = st.text_input("Specific Location", placeholder="e.g. Garage - Shelf 2", key="form_bin")
            
            new_stationary = st.checkbox("Stationary Tool (Must be used on-site)", value=st.session_state.get('form_stationary', False))

            new_safety = st.selectbox("Safety", ["Open", "Supervised", "Adult Only"], index=st.session_state['form_safety_index'])
            new_caps = st.text_input("Capabilities", key="form_caps")
            
            if st.form_submit_button("💾 Add to Tool Registry", use_container_width=True):
                if not new_owner or not new_household:
                    st.error("⚠️ Please select Owner and Household")
                else:
                    new_id = f"TOOL_{uuid.uuid4().hex[:6].upper()}"
                    dm.con.execute("INSERT INTO tools VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", 
                        (new_id, new_name, new_brand, new_model, new_power, new_owner, new_household, new_bin, new_stationary, 'Available', None, None, new_caps, new_safety))
                    st.success(f"✅ Saved: {new_name}")
                    st.rerun()