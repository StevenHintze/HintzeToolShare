import streamlit as st
import extra_streamlit_components as stx
from data_manager import DataManager
from tools_registry import check_safety 
from gemini_helper import ai_parse_tool, get_ai_advice, get_smart_recommendations, ai_filter_inventory, parse_location_update
import time
import datetime
import uuid
import pandas as pd

st.set_page_config(page_title="HFTS v0.9.20", page_icon="🛠️")

# Initialize DB
dm = DataManager()
dm.seed_data([], []) 
if st.sidebar.button("Admin Cleanup", key="cleanup"): # Hidden utility
    dm.clean_old_sessions()

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

cookie_token = cookie_manager.get(cookie="hfts_session")

if st.session_state["user_info"] is None and cookie_token:
    # Validate TOKEN against DB (Secure)
    user = dm.get_user_from_session(cookie_token)
    if user:
        st.session_state["user_info"] = user
        st.query_params.clear()
    else:
        # Token is invalid/expired, delete the bad cookie
        cookie_manager.delete("hfts_session")

def login():
    # FORCE CLEAN: Remove all whitespace and lowercase immediately
    raw_email = st.session_state.get("email_input", "")
    email = str(raw_email).strip().lower()
    
    password = st.session_state.get("password_input", "")
    
    if password == st.secrets["FAMILY_PASSWORD"]:
        user = dm.get_user_by_email(email)
        if user:
            # ... (Success logic stays the same) ...
            st.session_state["user_info"] = user
            token = dm.create_session(email)
            expires = datetime.datetime.now() + datetime.timedelta(days=7)
            cookie_manager.set("hfts_session", token, expires_at=expires)
            st.success(f"Welcome back, {user['name']}!")
            time.sleep(1)
            st.rerun()
        else:
            # ERROR: Show exactly what failed to help debug
            st.error(f"Email '{email}' not found in registry.")
            # Check if it's a registry mismatch
            # (Optional: You could print valid emails to console for your own debugging)
            # print(f"Attempted: {email}")
    else:
        st.error("Incorrect Family Password.")

if st.session_state["user_info"] is None:
    st.title("🔐 Family Login")
    st.text_input("Email Address", key="email_input")
    st.text_input("Family Password", type="password", key="password_input")
    if st.button("Log In"):
        login()
    st.stop()

# --- HELPER: CLEAR FORM CALLBACK ---
def clear_admin_form():
    """Resets all admin form session state keys"""
    keys = ['form_name', 'form_brand', 'form_model', 'form_caps', 'form_bin', 'form_power_idx', 'form_safety_index', 'ai_input']
    for k in keys:
        if k in st.session_state:
            del st.session_state[k] # Deleting causes Streamlit to re-init them to empty on next run

# --- APP STARTS HERE ---
current_user = st.session_state["user_info"]
st.title(f"🛠️ Hintze Family Tool Share")

# Sidebar
st.sidebar.header("My Profile")
st.sidebar.write(f"**Name:** {current_user['name']}")
st.sidebar.write(f"**Role:** {current_user['role']}")
st.sidebar.write(f"**House:** {current_user['household']}")

if st.sidebar.button("Log Out"):
    # 1. Remove from Browser
    cookie_token = cookie_manager.get(cookie="hfts_session")
    cookie_manager.delete("hfts_session")
    
    # 2. Remove from Server (Revoke access immediately)
    if cookie_token:
        dm.revoke_session(cookie_token)
        
    st.session_state["user_info"] = None
    time.sleep(1) 
    st.rerun()

# Tabs
tabs = ["Inventory", "Return Tools", "🚀 Project Planner"]
if current_user['role'] in ["ADMIN", "ADULT"]:
    tabs.append("🔐 Manage")

current_tabs = st.tabs(tabs)

# TAB 1: Inventory & Courier
with current_tabs[0]:
    st.header("Family Inventory")
    
    c1, c2 = st.columns([5, 1], vertical_alignment="bottom")
    with c1:
        query = st.text_input("🔎 Search or Ask...", placeholder="e.g. 'Automotive tools' or 'What has Shawn borrowed?'")
    with c2:
        # UPDATED: Default value is True
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

    st.subheader("⚡ Quick Borrow")
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
        st.info("No transportable tools available.")

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

# TAB 3: Project Planner
with current_tabs[2]:
    st.header("Project Planner")
    
    if "ai_recs" not in st.session_state:
        st.session_state["ai_recs"] = None

    if st.session_state["ai_recs"] is None:
        st.info(f"Describe your job. I'll check your household, find loans, and identify missing items.")
        
        # BUG FIX #1: Wrapped in form so Ctrl+Enter triggers submit
        with st.form("project_form"):
            project_query = st.text_area("Describe your project:", placeholder="e.g. I need to rotate my tires and change the oil...")
            submit_search = st.form_submit_button("Analyze Needs")
        
        if submit_search:
            if project_query:
                with st.spinner("Consulting the inventory..."):
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

        # 1. Things you have
        if recs.get('locate_list'):
            st.success("✅ **You already own these:**")
            for item in recs['locate_list']:
                st.markdown(f"- **{item['tool_name']}** ({item.get('location', 'Home')})")
        
        # 2. Things to chase down
        if recs.get('track_down_list'):
            st.warning("⚠️ **You own these, but they are gone:**")
            for item in recs['track_down_list']:
                st.markdown(f"- **{item['tool_name']}** is with **{item['held_by']}**")

        # 3. THINGS MISSING (Bug Fix #2)
        if recs.get('missing_list'):
            st.error("🛑 **Missing Essentials (Not in Family Registry):**")
            for item in recs['missing_list']:
                st.markdown(f"**{item['tool_name']}** ({item['importance']})")
                st.caption(f"💡 *Advice: {item['advice']}*")

        # 4. The Shopping Cart
        if recs.get('borrow_list'):
            st.info("🛒 **Tools to Borrow:**")
            with st.form("smart_borrow"):
                selected_ids = []
                for item in recs['borrow_list']:
                    label = f"**{item['name']}** from {item['household']}"
                    # Only show checkbox if we have a valid ID
                    if item.get('tool_id') and item['tool_id'] != "Unknown":
                        if st.checkbox(label, value=True, help=item['reason']):
                            selected_ids.append(item['tool_id'])
                    else:
                        st.write(f"⚠️ Error: AI recommended '{item['name']}' but couldn't find a valid ID.")
                
                st.markdown("---")
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
        
        # If nothing to do
        elif not recs.get('missing_list'):
            st.info("Looks like you have everything you need at home! Good luck.")

# TAB 4: Manage Inventory
if current_user['role'] in ["ADMIN", "ADULT"]:
    with current_tabs[3]:
        st.header(f"Manage {current_user['name']}'s Inventory")
        
        # --- SECTION 1: QUICK ACTIONS ---
        with st.container(border=True):
            st.subheader("⚡ Quick Actions")
            st.caption("Move, Sell, Donate, or Report Broken tools.")
            
            # REVERTED LAYOUT: Input + Button side-by-side
            c_act_1, c_act_2 = st.columns([4, 1], vertical_alignment="bottom")
            with c_act_1:
                move_query = st.text_input("Action Description:", placeholder="e.g. 'I sold the miter saw'", key="move_input")
            with c_act_2:
                # Use secondary type for neutral look until action is needed
                preview_btn = st.button("Preview", use_container_width=True)

            # Logic checks
            if preview_btn and move_query:
                with st.spinner("Analyzing..."):
                    my_tools_df = dm.get_my_tools(current_user['name'])
                    if my_tools_df.empty:
                        st.toast("No tools found.", icon="🚫")
                    else:
                        from gemini_helper import parse_location_update
                        move_data = parse_location_update(move_query, my_tools_df)
                        
                        proposed = []
                        if move_data and move_data.get('updates'):
                            for update in move_data['updates']:
                                tid = update.get('tool_id')
                                if tid in my_tools_df['id'].values:
                                    curr = my_tools_df[my_tools_df['id'] == tid].iloc[0]
                                    action = update.get('action', 'MOVE')
                                    
                                    desc = f"❌ RETIRE ({update.get('reason', 'Gone')})" if action == "RETIRE" else f"📍 MOVE to {update.get('new_bin')}"
                                    
                                    proposed.append({
                                        "ID": tid,
                                        "Tool": curr['name'],
                                        "Action": desc,
                                        "_data": update
                                    })
                        
                        if proposed:
                            st.session_state['pending_moves'] = proposed
                            st.rerun()
                        else:
                            st.toast("No matching tools found.", icon="🤷")

            # Confirmation UI
            if st.session_state.get('pending_moves'):
                st.markdown("#### 🛡️ Verify Changes")
                df_review = pd.DataFrame(st.session_state['pending_moves'])
                st.dataframe(df_review[["Tool", "Action"]], use_container_width=True, hide_index=True)
                
                col_yes, col_no = st.columns(2)
                
                # Use standard button types (primary=colored, secondary=outline)
                if col_yes.button("Confirm Update", type="primary", use_container_width=True):
                    count = 0
                    for change in st.session_state['pending_moves']:
                        data = change['_data'] # Get raw data for action type
                        
                        if data.get('action') == 'RETIRE':
                            # For retire, we trust the raw ID
                            dm.retire_tool(change['ID'], data.get('reason', 'Retired'), current_user['name'])
                        else:
                            # FIX: Use the calculated values (_bin, _house) we stored in the preview list
                            dm.update_tool_location(change['ID'], change['_bin'], change['_house'], current_user['name'])
                        
                        count += 1
                    
                    st.toast(
                        f"""
                        **✅ Update Complete**
                        
                        We moved **{count}** tools to:
                        
                        `{change['_data'].get('new_bin', 'New Location')}`
                        """,
                        icon="📦"
                    )
                    st.session_state['pending_moves'] = None
                    time.sleep(1)
                    st.rerun()
                
                if col_no.button("Cancel", use_container_width=True):
                    st.session_state['pending_moves'] = None
                    st.rerun()

        st.markdown("---")

        # --- SECTION 2: SPREADSHEET EDITOR ---
        st.subheader("📝 Edit Details")
        
        if current_user['role'] == "ADMIN":
            edit_df = dm.con.execute("SELECT * FROM tools").df()
            st.caption("Admin Mode: Editing ALL tools.")
        else:
            edit_df = dm.get_my_tools(current_user['name'])
            st.caption("Editing ONLY tools you own.")

        # CONFIG: Enable Selection
        edited_tools = st.data_editor(
            edit_df,
            column_config={
                "id": st.column_config.TextColumn(disabled=True),
                "status": st.column_config.TextColumn(disabled=True),
                "borrower": st.column_config.TextColumn(disabled=True),
                "return_date": st.column_config.TextColumn(disabled=True),
                "owner": st.column_config.SelectboxColumn(options=ALL_OWNERS, required=True),
                "household": st.column_config.SelectboxColumn(options=ALL_HOUSEHOLDS, required=True),
                "safety_rating": st.column_config.SelectboxColumn(options=["Open", "Supervised", "Adult Only"]),
            },
            hide_index=True,
            key="tool_editor"
        )

        if st.button("💾 Save Changes"):
            dm.batch_update_tools(edited_tools, current_user['name'])
            st.toast("Inventory updated successfully!", icon="💾")
            time.sleep(1)
            st.rerun()

        # --- SECTION 3: HISTORY (Linked) ---
        st.markdown("---")
        
        # Logic: Check if a row is selected in the editor above
        # Streamlit stores selection in session state under the key + "selection"
        # But data_editor returns the edited dataframe directly. 
        # To get selection, we usually need a callback or specialized state handling.
        # SIMPLER METHOD: Just let the user pick from the dropdown, but default to the first item if they clicked?
        # Streamlit's data_editor doesn't return the "Selected Row" easily in this mode.
        # Alternative: We stick to the Dropdown for History, BUT we sort it alphabetically so it's easy.
        
        with st.expander("📜 View History / Audit Trail", expanded=False):
            # Create a clean list of names
            tool_options = edit_df['name'].sort_values().unique()
            hist_tool_name = st.selectbox("Select tool history:", tool_options)
            
            if hist_tool_name:
                hist_tid = edit_df[edit_df['name'] == hist_tool_name].iloc[0]['id']
                history = dm.get_tool_history(hist_tid)
                if not history.empty:
                    st.dataframe(history)
                else:
                    st.caption("No history records found.")

        # --- SECTION 4: ADD NEW (Admin Only) ---
        if current_user['role'] == "ADMIN":
            st.markdown("---")
            st.subheader("Add New Tool")
            
            with st.form("ai_prefill_form"):
                c_ai_1, c_ai_2 = st.columns([1, 3], vertical_alignment="bottom")
                with c_ai_1:
                    quick_owner = st.selectbox("Who Owns It?", ALL_OWNERS, index=None, placeholder="Owner...", key="ai_owner_select")
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
                            
                            st.toast("AI Generated Details - Check Step 2", icon="🤖")
                            time.sleep(0.9)
                            st.rerun() 
                        else:
                            st.error("AI could not generate details from description.")
                else:
                    st.error("Please paste a description.")

            with st.form("add_tool"):
                if 'form_name' not in st.session_state: st.session_state['form_name'] = ""
                if 'form_brand' not in st.session_state: st.session_state['form_brand'] = ""
                if 'form_model' not in st.session_state: st.session_state['form_model'] = ""
                if 'form_caps' not in st.session_state: st.session_state['form_caps'] = ""
                if 'form_stationary' not in st.session_state: st.session_state['form_stationary'] = False
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
                        st.toast(
                            f"""
                            **💾 Tool Added**
                            
                            **{new_name}** has been added to the tool registry.
                            """,
                            icon="🛠️"
                        )
                        time.sleep(1)
                        st.rerun()
        st.markdown("---")
        
        # --- SECTION 5: MAINTENANCE ---
        with st.expander("⚙️ Database Maintenance"):
            st.caption("Keep the database lean by removing old audit logs.")
            
            col_m1, col_m2 = st.columns([3, 1], vertical_alignment="bottom")
            with col_m1:
                st.write("**Purge Old History:** Removes audit trails older than 30 days.")
            with col_m2:
                if st.button("🧹 Purge Now", use_container_width=True):
                    with st.spinner("Cleaning up..."):
                        deleted_count = dm.purge_old_history(days=30)
                        time.sleep(1)
                        if deleted_count > 0:
                            st.toast(f"Cleanup Complete: Removed {deleted_count} old records.", icon="🗑️")
                        else:
                            st.toast("Database is already clean.", icon="✨")