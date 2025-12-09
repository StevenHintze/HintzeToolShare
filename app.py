import streamlit as st
import extra_streamlit_components as stx
from data_manager import DataManager
from tools_registry import check_safety 
from gemini_helper import ai_parse_tool, get_ai_advice, get_smart_recommendations, ai_filter_inventory, parse_location_update, check_duplicate_tool, parse_lending_request
import time
import datetime
import uuid
import pandas as pd

st.set_page_config(page_title="HFTS v0.9.31", page_icon="🛠️")

# Initialize DB
dm = DataManager()
dm.seed_data([], []) 

# --- COOKIE MANAGER ---
cookie_manager = stx.CookieManager()

st.markdown("""
    <style>
    /* Fix Multiselect Tag Text Color (White on Yellow -> Black on Yellow) */
    span[data-baseweb="tag"] {
        color: #000000 !important;
    }
    </style>
""", unsafe_allow_html=True)

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

# --- CALLBACKS ---
def save_tool_callback():
    if not st.session_state.get('tool_owner') or not st.session_state.get('tool_household'):
        st.session_state['admin_error'] = "⚠️ Please select an Owner and Location."
        return

    try:
        dm_cb = DataManager()
        new_id = f"TOOL_{uuid.uuid4().hex[:6].upper()}"
        
        dm_cb.con.execute("INSERT INTO tools VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", 
            (new_id, 
             st.session_state['tool_name'], 
             st.session_state['tool_brand'], 
             st.session_state['tool_model'], 
             st.session_state['tool_power'], 
             st.session_state['tool_owner'], 
             st.session_state['tool_household'], 
             st.session_state['tool_bin'], 
             st.session_state['tool_stationary'], 
             'Available', None, None, 
             st.session_state['tool_caps'], 
             st.session_state['tool_safety']))
        
        st.toast(
            f"""
            #### Tool Added<br>
            **{st.session_state['tool_name']}** is in your Toolbox.<br>
            *Ready for borrowing."*
            """,
            icon="✅"
            )
        st.session_state['admin_error'] = None
        st.session_state['dup_warning'] = None
        
        # Clear form
        st.session_state['tool_name'] = ""
        st.session_state['tool_brand'] = ""
        st.session_state['tool_model'] = ""
        st.session_state['tool_caps'] = ""
        st.session_state['tool_bin'] = ""
        st.session_state['tool_stationary'] = False
        st.session_state['ai_input'] = ""
        st.session_state['tool_power'] = "Manual"
        st.session_state['tool_safety'] = "Open"
        
    except Exception as e:
        st.session_state['admin_error'] = f"Error: {str(e)}"

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
    
    if password == st.secrets["FAMILY_PASSWORD"]:
        user = dm.get_user_by_email(email)
        if user:
            dm.log_event("LOGIN", email, "Successful login")
            st.session_state["user_info"] = user
            token = dm.create_session(email)
            expires = datetime.datetime.now() + datetime.timedelta(days=7)
            cookie_manager.set("hfts_session", token, expires_at=expires)
            st.success(f"Welcome back, {user['name']}!")
            time.sleep(1)
            st.rerun()
        else:
            dm.log_event("FAILED_LOGIN", email, "Email not in registry")
            st.error(f"Email '{email}' not found in registry.")
    else:
        dm.log_event("FAILED_LOGIN", email, "Bad Password")
        st.error("Incorrect Family Password.")

if st.session_state["user_info"] is None:
    st.title("🔐 Family Login")
    with st.form("login_form"):
        st.text_input("Email Address", key="email_input")
        st.text_input("Family Password", type="password", key="password_input")
        submitted = st.form_submit_button("Log In")
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

# Tabs
tabs = ["Family Tool List", "Return Tools", "🚀 Project Planner"]
if current_user['role'] in ["ADMIN", "ADULT"]:
    tabs.append("🤝 Lending Center")
    tabs.append("🧰 Manage Your Toolbox")

current_tabs = st.tabs(tabs)

# ---------------------------------------------------------
# TAB BONUS: Lending Center (Index 3 if present)
# ---------------------------------------------------------
if current_user['role'] in ["ADMIN", "ADULT"]:
    with current_tabs[3]:
        st.header("🤝 Lending Center")
        st.caption(f"Lend tools from **{current_user['name']}'s Toolbox** to others.")
        
        my_available_tools = dm.con.execute("SELECT * FROM tools WHERE owner = ? AND status = 'Available'", [current_user['name']]).df()
        
        method = st.radio("Input Method:", ["🤖 AI Assistant", "📝 Manual Selection"], horizontal=True)
        
        # Initialize Session State for Lending
        if 'lend_stage' not in st.session_state: st.session_state['lend_stage'] = 'manual'
        if 'lend_data' not in st.session_state: st.session_state['lend_data'] = None

        # Reset state if switching to Manual
        if method == "📝 Manual Selection" and st.session_state.get('lend_stage') != 'manual':
             st.session_state['lend_stage'] = 'manual'
             st.session_state['lend_data'] = None

        if method == "🤖 AI Assistant":
            with st.container(border=True):
                st.caption("Describe what happened naturally (e.g., 'I lent the drill to Shawn').")
                with st.form("ai_lending_form"):
                    lending_query = st.text_input("Tell me what's happening:", placeholder="Type here and press Enter...")
                    submitted = st.form_submit_button("Analyze Request", use_container_width=True)
                
                if submitted and lending_query:
                    with st.spinner("Processing..."):
                        fam_list = dm.get_family_members().to_dict('records')
                        all_my_tools = dm.get_my_tools(current_user['name'])
                        result = parse_lending_request(lending_query, all_my_tools, fam_list)
                        
                        if result:
                            if result.get('candidates'):
                                st.session_state['lend_stage'] = 'refine'
                                st.session_state['lend_data'] = result
                            else:
                                # No candidates found
                                st.warning("I couldn't find any tools matching your description. Please select manually.")
                                st.session_state['lend_stage'] = 'verify'
                                st.session_state['lend_data'] = result # Keep borrower if found
                        else:
                            st.error("Could not understand request.")

        # --- REFINE CANDIDATES (Checklist) ---
        if st.session_state.get('lend_stage') == 'refine' and st.session_state.get('lend_data'):
            st.divider()
            st.info("🔎 I found multiple options. Select the ones you mean:")
            
            with st.form("refine_candidates"):
                cands = st.session_state['lend_data'].get('candidates', [])
                selected_cands_ids = []
                for c in cands:
                    # Default True for high confidence
                    is_checked = st.checkbox(f"**{c['name']}**", value=True, key=f"cand_{c['id']}")
                    if is_checked:
                        selected_cands_ids.append(c['id'])
                
                if st.form_submit_button("Confirm Selection"):
                    st.session_state['lend_data']['tool_ids'] = selected_cands_ids
                    st.session_state['lend_stage'] = 'verify'
                    st.rerun()

        # --- FORM LOGIC ---
        # Allow 'manual' stage or 'verify' stage (from AI)
        if st.session_state.get('lend_stage') in ['verify', 'manual'] or st.session_state.get('lend_stage') is None: 
            st.markdown("---")
            st.subheader("Confirm Details")

            # PRE-FILL LOGIC
            default_tools = []
            default_borrower = None
            force_safety = False
            
            # Only use AI data if we are in 'verify' stage AND AI method is selected (or we want AI data to persist?)
            # Let's say we persist AI data even if they switch tabs, but maybe clear it if they switch to manual explicitly? 
            # Simpler: If lend_data exists, use it as default.
            if st.session_state.get('lend_data'):
                data = st.session_state['lend_data']
                
                # 1. Match Borrower
                member_names = family_df['name'].tolist()
                if data.get('borrower_name') in member_names:
                    default_borrower = data['borrower_name']
                
                # 2. Match Tools
                if data.get('tool_ids'):
                    t_ids = data['tool_ids']
                    pre_selected = my_available_tools[my_available_tools['id'].isin(t_ids)]['name'].tolist()
                    default_tools = pre_selected
                    
                    # Check unavailable
                    all_my_tools_chk = dm.get_my_tools(current_user['name'])
                    unavailable = all_my_tools_chk[(all_my_tools_chk['id'].isin(t_ids)) & (all_my_tools_chk['status'] != 'Available')]
                    if not unavailable.empty:
                        st.warning(f"⚠️ **Note:** Some tools mentioned are already marked as borrowed: {', '.join(unavailable['name'].tolist())}")
                
                # 3. Safety Override
                if data.get('force_override'): force_safety = True
                
                # If AI was just run, show an info box
                if st.session_state['lend_stage'] == 'verify':
                    st.info("👇 Please verify the details below.")

            if my_available_tools.empty:
                 # Check why
                 chk = dm.get_my_tools(current_user['name'])
                 if chk.empty:
                     st.warning("⚠️ You don't have any tools in your toolbox yet. Go to 'Manage Your Toolbox' to add them.")
                 else:
                     st.warning(f"⚠️ You have {len(chk)} tools, but they are ALL currently borrowed or unavailable.")
            
            with st.form("lending_form"):
                # INPUTS
                selected_tool_names = st.multiselect("Select Tools", my_available_tools['name'], default=default_tools)
                borrower = st.selectbox("Lending To:", family_df['name'], index=family_df['name'].tolist().index(default_borrower) if default_borrower else None)
                days = st.number_input("Duration (Days)", min_value=1, value=7)
                
                # LOGIC CHECK
                safety_warning = []
                requires_override = False
                
                if selected_tool_names and borrower:
                    # Get Borrower Role
                    b_role = family_df[family_df['name'] == borrower].iloc[0]['role']
                    
                    # Check Each Tool
                    for t_name in selected_tool_names:
                        t_row = my_available_tools[my_available_tools['name'] == t_name].iloc[0]
                        if b_role == "CHILD" and t_row['safety_rating'] == "Adult Only":
                            safety_warning.append(f"⛔ **{t_name}** is 'Adult Only' and **{borrower}** is a Child.")
                            requires_override = True
                
                if requires_override:
                    st.error("⚠️ SAFETY ALERT")
                    for w in safety_warning: st.write(w)
                    authorized = st.checkbox("☑️ I authorize this loan and assume full responsibility for safety.", value=force_safety)
                else:
                    authorized = True # No override needed

                # SUBMIT
                if st.form_submit_button("Confirm Loan 🤝"):
                    if not selected_tool_names:
                        st.error("Select at least one tool.")
                    elif not borrower:
                        st.error("Select a borrower.")
                    elif requires_override and not authorized:
                        st.error("You must authorize the safety override to proceed.")
                    else:
                        # PROCESS LOAN
                        success_count = 0
                        for t_name in selected_tool_names:
                            tid = my_available_tools[my_available_tools['name'] == t_name].iloc[0]['id']
                            dm.borrow_tool(tid, borrower, days)
                            success_count += 1
                        
                        st.toast(f"Successfully lent {success_count} tools to {borrower}!", icon="✅")
                        st.session_state['lend_stage'] = 'manual' # Reset
                        st.session_state['lend_data'] = None
                        time.sleep(1.5)
                        st.rerun()

# TAB 0: Family Tool List
with current_tabs[0]:
    st.header("Family Tool Registry")
    c1, c2 = st.columns([5, 1], vertical_alignment="bottom")
    with c1:
        query = st.text_input("🔎 Search or Ask...", placeholder="e.g. 'Automotive tools' or 'What has Shawn borrowed?'")
    with c2:
        use_ai = st.toggle("AI Search", value=True)

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

    def format_location(row):
        loc = f"{row['household']} ({row['bin_location']})"
        if row.get('is_stationary'): loc += " ⚓ [Fixed]"
        return loc

    filtered_df['Location Info'] = filtered_df.apply(format_location, axis=1)
    
    def get_status_display(row):
        if row['status'] == 'Borrowed': return f"⛔ With {row['borrower']}"
        return "✅ Available"
    
    filtered_df['Display Status'] = filtered_df.apply(get_status_display, axis=1)

    st.dataframe(
        filtered_df[['name', 'brand', 'Display Status', 'Location Info', 'return_date']],
        column_config={"return_date": st.column_config.DatetimeColumn("Due Back", format="D MMM")},
        use_container_width=True
    )

    st.markdown("---")
    st.subheader("⚡ Quick Borrow")
    available_only = all_tools[(all_tools['status'] == 'Available') & (all_tools['is_stationary'] != True)]
    
    if not available_only.empty:
        with st.form("manual_borrow"):
            col_b1, col_b2 = st.columns([3, 1])
            with col_b1:
                target_tool_name = st.selectbox("Select Tool", available_only['name'])
            with col_b2:
                days = st.number_input("Days", min_value=1, value=7)
            
            if st.form_submit_button("Confirm Borrow"):
                tool_row = available_only[available_only['name'] == target_tool_name].iloc[0]
                if check_safety(current_user['role'], tool_row['safety_rating']):
                    dm.borrow_tool(tool_row['id'], current_user['name'], days)
                    st.success(f"✅ You borrowed the {target_tool_name}!")
                    
                    pickup_household = tool_row['household']
                    resident_name = None
                    for owner, house in OWNER_HOMES.items():
                        if house == pickup_household:
                            resident_name = owner
                            break
                    
                    if resident_name:
                        courier_candidates = all_tools[(all_tools['borrower'] == resident_name) & (all_tools['status'] == 'Borrowed')]
                        if not courier_candidates.empty:
                            st.info(f"🚛 **Courier Opportunity!**")
                            st.write(f"Since you are going to **{pickup_household}**, {resident_name} has these items checked out:")
                            for idx, c_row in courier_candidates.iterrows():
                                st.markdown(f"- **{c_row['name']}** (Owned by {c_row['owner']})")
                            st.caption("Ask them if you can return these for them!")
                    time.sleep(6)
                    st.rerun()
                else:
                    st.error("🚫 Safety Restriction.")
    else:
        st.info("No transportable tools available.")

# TAB 2: Return Tools
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

# TAB 3: Project Planner
with current_tabs[2]:
    st.header("Project Planner")
    if "ai_recs" not in st.session_state: st.session_state["ai_recs"] = None

    if st.session_state["ai_recs"] is None:
        st.info(f"Describe your job. I'll check your household tools, find ones you may need to borrow, and identify useful tools that are not in the family toolbox.")
        with st.form("project_form"):
            project_query = st.text_area("Describe your project:", placeholder="e.g. I need to rotate my tires and change the oil...")
            submit_search = st.form_submit_button("Analyze Needs")
        
        if submit_search and project_query:
            with st.spinner("Planning and Looking for Tools..."):
                all_tools_df = dm.con.execute("SELECT * FROM tools").df()
                recs = get_smart_recommendations(project_query, all_tools_df, current_user['household'])
                if recs:
                    st.session_state["ai_recs"] = recs
                    st.rerun()
    else:
        recs = st.session_state["ai_recs"]
        if st.button("← Start Over"):
            st.session_state["ai_recs"] = None
            st.rerun()

        if recs.get('locate_list'):
            st.success("✅ **You already own these:**")
            for item in recs['locate_list']:
                st.markdown(f"- **{item['tool_name']}** ({item.get('location', 'Home')})")
        
        if recs.get('track_down_list'):
            st.warning("⚠️ **You own these, but they are gone:**")
            for item in recs['track_down_list']:
                st.markdown(f"- **{item['tool_name']}** is with **{item['held_by']}**")

        if recs.get('missing_list'):
            st.error("🛑 **Missing Essentials (Not in Family Registry):**")
            for item in recs['missing_list']:
                st.markdown(f"**{item['tool_name']}** ({item['importance']})")
                st.caption(f"💡 *Advice: {item['advice']}*")

        if recs.get('borrow_list'):
            st.info("🛒 **Tools to Borrow:**")
            with st.form("smart_borrow"):
                selected_ids = []
                for item in recs['borrow_list']:
                    label = f"**{item['name']}** from {item['household']}"
                    if item.get('tool_id') and item['tool_id'] != "Unknown":
                        if st.checkbox(label, value=True, help=item['reason']):
                            selected_ids.append(item['tool_id'])
                days = st.number_input("Days needed:", min_value=1, value=7)
                if st.form_submit_button("Confirm Borrow Request"):
                    if selected_ids:
                        for tid in selected_ids:
                            dm.borrow_tool(tid, current_user['name'], days)
                        st.success("Tools borrowed!")
                        st.session_state["ai_recs"] = None
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.warning("No tools selected.")
        
        elif not recs.get('missing_list'):
            st.info("Looks like you have everything you need at home! Good luck.")

# TAB 4: Manage Toolbox
if current_user['role'] in ["ADMIN", "ADULT"]:
    with current_tabs[4]:
        st.header(f"Manage {current_user['name']}'s Inventory")
        
        # QUICK ACTIONS
        with st.container(border=True):
            st.subheader("⚡ Quick Actions")
            st.caption("Move, Sell, Donate, or Report Broken tools.")
            with st.form("quick_action_form"):
                c_act_1, c_act_2 = st.columns([4, 1], vertical_alignment="bottom")
                with c_act_1:
                    move_query = st.text_input("Action Description:", placeholder="e.g. 'I sold the miter saw'", key="move_input")
                with c_act_2:
                    preview_btn = st.form_submit_button("Review Action", use_container_width=True)

            if preview_btn and move_query:
                with st.spinner("Analyzing..."):
                    my_tools_df = dm.get_my_tools(current_user['name'])
                    if my_tools_df.empty:
                        st.toast("No tools found.", icon="🚫")
                    else:
                        move_data = parse_location_update(move_query, my_tools_df)
                        proposed = []
                        if move_data and move_data.get('updates'):
                            for update in move_data['updates']:
                                tid = update.get('tool_id')
                                if tid in my_tools_df['id'].values:
                                    curr = my_tools_df[my_tools_df['id'] == tid].iloc[0]
                                    action = update.get('action', 'MOVE')
                                    current_house_val = curr['household']
                                    if pd.isna(current_house_val) or current_house_val == "":
                                        current_house_val = OWNER_HOMES.get(curr['owner'], "Main House")
                                    new_house = update.get('new_household') or current_house_val
                                    new_bin = update.get('new_bin')
                                    desc = f"❌ RETIRE ({update.get('reason', 'Gone')})" if action == "RETIRE" else f"📍 MOVE to {new_bin}"
                                    proposed.append({"ID": tid, "Tool": curr['name'], "Action": desc, "_data": update, "_bin": new_bin, "_house": new_house})
                        if proposed:
                            st.session_state['pending_moves'] = proposed
                            st.rerun()
                        else:
                            st.toast("No matching tools found.", icon="🤷")

            if st.session_state.get('pending_moves'):
                st.markdown("#### 🛡️ Verify Changes")
                df_review = pd.DataFrame(st.session_state['pending_moves'])
                st.dataframe(df_review[["Tool", "Action"]], use_container_width=True, hide_index=True)
                c_y, c_n = st.columns(2)
                if c_y.button("Confirm Update", type="primary", use_container_width=True):
                    count = 0
                    for change in st.session_state['pending_moves']:
                        data = change['_data']
                        dm.log_event("ADMIN_UPDATE", current_user['name'], f"{change['Action']} on {change['Tool']}")
                        if data.get('action') == 'RETIRE':
                            dm.retire_tool(change['ID'], data.get('reason', 'Retired'), current_user['name'])
                        else:
                            dm.update_tool_location(change['ID'], change['_bin'], change['_house'], current_user['name'])
                        count += 1
                    st.toast(f"**✅ Update Complete**\n\nProcessed **{count}** items.", icon="📦")
                    st.session_state['pending_moves'] = None
                    time.sleep(1)
                    st.rerun()
                if c_n.button("Cancel", use_container_width=True):
                    st.session_state['pending_moves'] = None
                    st.rerun()

        st.markdown("---")
        st.subheader("📝 Edit Details")
        if current_user['role'] == "ADMIN":
            edit_df = dm.con.execute("SELECT * FROM tools").df()
            st.caption("Admin Mode: Editing ALL tools.")
        else:
            edit_df = dm.get_my_tools(current_user['name'])
            st.caption("Editing ONLY tools you own.")

        edited_tools = st.data_editor(
            edit_df,
            column_config={"id": st.column_config.TextColumn(disabled=True), "status": st.column_config.TextColumn(disabled=True), "borrower": st.column_config.TextColumn(disabled=True), "return_date": st.column_config.TextColumn(disabled=True), "owner": st.column_config.SelectboxColumn(options=ALL_OWNERS, required=True), "household": st.column_config.SelectboxColumn(options=ALL_HOUSEHOLDS, required=True), "safety_rating": st.column_config.SelectboxColumn(options=["Open", "Supervised", "Adult Only"])},
            hide_index=True,
            key="tool_editor"
        )
        if st.button("💾 Save Changes"):
            dm.batch_update_tools(edited_tools, current_user['name'])
            st.toast("Inventory updated successfully!", icon="💾")
            time.sleep(1)
            st.rerun()

        st.markdown("---")
        with st.expander("📜 View History / Audit Trail"):
            hist_tool_name = st.selectbox("Select tool history:", edit_df['name'].sort_values().unique())
            if hist_tool_name:
                hist_tid = edit_df[edit_df['name'] == hist_tool_name].iloc[0]['id']
                history = dm.get_tool_history(hist_tid)
                if not history.empty: st.dataframe(history)
                else: st.caption("No history records found.")

        if current_user['role'] == "ADMIN":
            st.markdown("---")
            with st.expander("⚙️ Database Maintenance"):
                if st.button("🧹 Purge Old History"):
                    deleted = dm.purge_old_history(30)
                    st.toast(f"Removed {deleted} old records.", icon="🗑️")

        st.markdown("---")
        st.subheader("Add New Tool")
        
        with st.form("ai_prefill_form"):
            c1, c2 = st.columns([1, 3], vertical_alignment="bottom")
            with c1: quick_owner = st.selectbox("Who Owns It?", ALL_OWNERS, index=None, placeholder="Owner...", key="ai_owner_select")
            with c2: raw_input = st.text_input("Paste Description", key="ai_input")
            trigger_ai = st.form_submit_button("✨ Auto-Fill the Form Below", use_container_width=True)

        if trigger_ai and raw_input:
            with st.spinner("Analyzing..."):
                ai_data = ai_parse_tool(raw_input)
                if ai_data:
                    st.session_state['tool_name'] = ai_data.get('name', '')
                    st.session_state['tool_brand'] = ai_data.get('brand', '')
                    st.session_state['tool_model'] = ai_data.get('model_no', '')
                    st.session_state['tool_caps'] = ai_data.get('capabilities', '')
                    st.session_state['tool_stationary'] = ai_data.get('is_stationary', False)
                    
                    # DUPLICATE CHECK
                    all_inv = dm.con.execute("SELECT * FROM tools").df()
                    target_house = OWNER_HOMES.get(quick_owner, ALL_HOUSEHOLDS[0]) if quick_owner else ALL_HOUSEHOLDS[0]
                    house_tools = all_inv[all_inv['household'] == target_house]
                    if not house_tools.empty:
                        dup = check_duplicate_tool(ai_data, house_tools)
                        if dup and dup.get('is_duplicate'):
                            # UPDATED MESSAGE:
                            st.session_state['dup_warning'] = f"⚠️ **Possible Duplicate:** Similar to **{dup['match_name']}** already in **{target_house}** household."
                        else: st.session_state['dup_warning'] = None
                    else: st.session_state['dup_warning'] = None

                    try: 
                        p_list = ["Manual", "Corded", "Battery", "Gas", "Pneumatic", "Hydraulic"]
                        st.session_state['tool_power'] = ai_data.get('power_source', 'Manual') if ai_data.get('power_source', 'Manual') in p_list else "Manual"
                    except: st.session_state['tool_power'] = "Manual"
                    
                    if quick_owner:
                        st.session_state['tool_owner'] = quick_owner
                        st.session_state['tool_household'] = OWNER_HOMES.get(quick_owner, ALL_HOUSEHOLDS[0])
                    
                    st.toast("AI Generated Details! Please Check for Accuracy.", icon="🕵️")
                    time.sleep(2.5)
                    st.rerun()

        if st.session_state.get('dup_warning'):
            st.warning(st.session_state['dup_warning'])

        with st.form("add_tool"):
            keys = ['tool_name', 'tool_brand', 'tool_model', 'tool_caps', 'tool_bin']
            for k in keys:
                if k not in st.session_state: st.session_state[k] = ""
            
            if 'tool_power' not in st.session_state: st.session_state['tool_power'] = "Manual"
            if 'tool_safety' not in st.session_state: st.session_state['tool_safety'] = "Open"
            if 'tool_stationary' not in st.session_state: st.session_state['tool_stationary'] = False
            
            if 'tool_owner' not in st.session_state or st.session_state['tool_owner'] not in ALL_OWNERS:
                st.session_state['tool_owner'] = ALL_OWNERS[0] if ALL_OWNERS else None
            if 'tool_household' not in st.session_state or st.session_state['tool_household'] not in ALL_HOUSEHOLDS:
                st.session_state['tool_household'] = ALL_HOUSEHOLDS[0] if ALL_HOUSEHOLDS else None

            st.text_input("Tool Name", key="tool_name")
            c1, c2, c3 = st.columns(3)
            with c1: st.text_input("Brand", key="tool_brand")
            with c2: st.text_input("Model #", key="tool_model")
            with c3: st.selectbox("Power", ["Manual", "Corded", "Battery", "Gas", "Pneumatic", "Hydraulic"], key="tool_power")

            c4, c5 = st.columns(2)
            with c4: st.selectbox("Owner", ALL_OWNERS, key="tool_owner")
            with c5: st.selectbox("Location", ALL_HOUSEHOLDS, key="tool_household")

            st.text_input("Specific Location", placeholder="e.g. Garage - Shelf 2", key="tool_bin")
            st.checkbox("Stationary Tool (Must be used on-site)", key="tool_stationary")
            st.selectbox("Safety", ["Open", "Supervised", "Adult Only"], key="tool_safety")
            st.text_input("Capabilities", key="tool_caps")
            
            st.form_submit_button("💾 Add to Tool Registry", use_container_width=True, on_click=save_tool_callback)