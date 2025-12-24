import streamlit as st
import time
import pandas as pd
import uuid
from core.data_manager import DataManager
from core.gemini_helper import parse_location_update, ai_parse_tool, check_duplicate_tool, ai_find_tools_for_deletion


def render_armory(dm: DataManager, current_user):
    st.header(f"🛡️ Manage {current_user['household']} Armory")
        
    try:
        family_df = dm.get_family_members() # Cached
        OWNER_HOMES = dict(zip(family_df['name'], family_df['household']))
        ALL_OWNERS = list(OWNER_HOMES.keys())
        ALL_HOUSEHOLDS = list(set(OWNER_HOMES.values()))
    except:
        OWNER_HOMES = {}
        ALL_OWNERS = ["Admin"]
        ALL_HOUSEHOLDS = ["Main House"]

    # Main Callback
    def save_tool_callback():
        if not st.session_state.get('tool_owner') or not st.session_state.get('tool_household'):
            st.session_state['admin_error'] = "⚠️ Please select an Owner and Location."
            return

        try:
            # We create a fresh instance or reuse 'dm' if thread-safe, 
            # but callbacks in Streamlit can be tricky. Using the passed 'dm' should be fine 
            # if it holds just the connection.
            new_id = f"TOOL_{uuid.uuid4().hex[:6].upper()}"
            
            dm.con.execute("INSERT INTO tools VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", 
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
            
            dm.clear_cache() # Refresh Cache
            
            st.toast(
                f"**💾 Tool Added**<br>**{st.session_state['tool_name']}** has been added to the registry.",
                icon="🛠️"
            )
            st.session_state['admin_error'] = None
            st.session_state['dup_warning'] = None
            
            # Clear form but KEEP defaults
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

    # --- SECTION: INVENTORY OPERATIONS ---
    st.subheader("📦 Inventory Operations")
    
    # Persistent State for Expanders
    for key in ['exp_quick', 'exp_edit', 'exp_add', 'exp_audit', 'exp_purge', 'exp_incin']:
        if key not in st.session_state: st.session_state[key] = (key == 'exp_quick') # Quick Actions open by default

    with st.expander("⚡ Quick Actions", expanded=st.session_state['exp_quick']):
        st.session_state['exp_quick'] = True
        st.caption("Naturally move, sell, donate, or report broken tools using AI.")
        
        with st.form("quick_action_form"):
            c_act_1, c_act_2 = st.columns([4, 1], vertical_alignment="bottom")
            with c_act_1:
                move_query = st.text_input("Action Description:", placeholder="e.g. 'I sold the miter saw'", key="move_input")
            with c_act_2:
                preview_btn = st.form_submit_button("Review Action", width='stretch')

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
            st.dataframe(df_review[["Tool", "Action"]], width="stretch", hide_index=True)
            c_y, c_n = st.columns(2)
            if c_y.button("Confirm Update", type="primary", width='stretch'):
                count = 0
                for change in st.session_state['pending_moves']:
                    data = change['_data']
                    dm.log_event("ADMIN_UPDATE", current_user['name'], f"{change['Action']} on {change['Tool']}")
                    if data.get('action') == 'RETIRE':
                        dm.retire_tool(change['ID'], data.get('reason', 'Retired'), current_user['name'])
                    else:
                        dm.update_tool_location(change['ID'], change['_bin'], change['_house'], current_user['name'])
                    count += 1
                dm.clear_cache()
                st.toast(f"**✅ Update Complete**\n\nProcessed **{count}** items.", icon="📦")
                st.session_state['pending_moves'] = None
                time.sleep(1)
                st.rerun()
            if c_n.button("Cancel", width='stretch'):
                st.session_state['pending_moves'] = None
                st.rerun()

    st.markdown("---")
    with st.expander("📝 Edit Tool Details", expanded=st.session_state['exp_edit']):
        st.session_state['exp_edit'] = True
        st.caption("Directly edit tool attributes in the table below.")
        if current_user['role'] == "ADMIN":
            edit_df = dm.get_all_tools() # Cached
            st.info("💡 **Admin Mode:** You are editing the entire family registry.")
        else:
            edit_df = dm.get_my_tools(current_user['name'])
            st.info(f"💡 Editing tools owned by **{current_user['name']}**.")

        edited_tools = st.data_editor(
            edit_df,
            column_config={
                "id": st.column_config.TextColumn("ID", disabled=True, width="small"),
                "status": st.column_config.TextColumn("Status", disabled=True),
                "borrower": st.column_config.TextColumn("Borrower", disabled=True),
                "return_date": st.column_config.DateColumn("Due Back", format="ddd, MMM D", disabled=True),
                "owner": st.column_config.SelectboxColumn("Owner", options=ALL_OWNERS, required=True),
                "household": st.column_config.SelectboxColumn("Household", options=ALL_HOUSEHOLDS, required=True),
                "safety_rating": st.column_config.SelectboxColumn("Safety", options=["Open", "Supervised", "Adult Only"])
            },
            hide_index=True,
            key="tool_editor",
            width='stretch'
        )
        if st.button("💾 Save Table Changes", width="stretch"):
            dm.batch_update_tools(edited_tools, current_user['name'])
            st.toast("Inventory updated successfully!", icon="💾")
            time.sleep(1)
            st.rerun()

    st.markdown("---")
    with st.expander("➕ Add New Tool", expanded=st.session_state['exp_add']):
        st.session_state['exp_add'] = True
        st.caption("Auto-fill with AI or enter manually.")
        
        with st.form("ai_prefill_form"):
            c1, c2 = st.columns([1, 3], vertical_alignment="bottom")
            with c1: 
                # FIX: Set default owner to current user
                default_owner_idx = ALL_OWNERS.index(current_user['name']) if current_user['name'] in ALL_OWNERS else None
                quick_owner = st.selectbox("Who Owns It?", ALL_OWNERS, index=default_owner_idx, key="ai_owner_select")
            with c2: 
                raw_input = st.text_input("Paste Description", key="ai_input", placeholder="e.g. 'DEWALT Drill DCD777D1'")
            # UPDATED BUTTON TEXT AND PROGRESS BAR LOGIC
            trigger_ai = st.form_submit_button("✨ Click to Generate Details with AI", width='stretch')

        if trigger_ai and raw_input:
            progress_text = "🤖 AI is analyzing your tool..."
            my_bar = st.progress(0, text=progress_text)
            
            ai_data = ai_parse_tool(raw_input)
            my_bar.progress(40, text="Parsing details...")
            
            if ai_data:
                st.session_state['tool_name'] = ai_data.get('name', '')
                st.session_state['tool_brand'] = ai_data.get('brand', '')
                st.session_state['tool_model'] = ai_data.get('model_no', '')
                st.session_state['tool_caps'] = ai_data.get('capabilities', '')
                st.session_state['tool_stationary'] = ai_data.get('is_stationary', False)
                
                # DUPLICATE CHECK
                my_bar.progress(70, text="Checking for duplicates...")
                all_inv = dm.get_all_tools() # Cached
                target_house = OWNER_HOMES.get(quick_owner, ALL_HOUSEHOLDS[0]) if quick_owner else ALL_HOUSEHOLDS[0]
                house_tools = all_inv[all_inv['household'] == target_house]
                if not house_tools.empty:
                    dup = check_duplicate_tool(ai_data, house_tools)
                    if dup and dup.get('is_duplicate'):
                        st.session_state['dup_warning'] = f"⚠️ **Possible Duplicate:** Similar to **{dup['match_name']}** already in **{target_house}** household."
                    else: st.session_state['dup_warning'] = None
                else: st.session_state['dup_warning'] = None

                try: 
                    p_list = ["Manual", "Corded", "Battery", "Gas", "Pneumatic", "Hydraulic"]
                    st.session_state['tool_power'] = ai_data.get('power_source', 'Manual') if ai_data.get('power_source', 'Manual') in p_list else "Manual"
                except: st.session_state['tool_power'] = "Manual"
                
                final_owner = quick_owner if quick_owner else current_user['name']
                st.session_state['tool_owner'] = final_owner
                st.session_state['tool_household'] = OWNER_HOMES.get(final_owner, current_user['household'])
                
                my_bar.progress(100, text="Done!")
                time.sleep(0.5)
                my_bar.empty()
                st.toast("AI Generated Details - Please Check for Accuracy.", icon="🤖")
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
            
            # Default to Current User if state is empty
            if 'tool_owner' not in st.session_state or not st.session_state['tool_owner']:
                st.session_state['tool_owner'] = current_user['name']
            if 'tool_household' not in st.session_state or not st.session_state['tool_household']:
                st.session_state['tool_household'] = current_user['household']

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
            
            st.form_submit_button("💾 Add to Tool Registry", width='stretch', on_click=save_tool_callback)

    st.markdown("---")
    with st.expander("📜 View Audit History", expanded=st.session_state['exp_audit']):
        st.session_state['exp_audit'] = True
        st.caption("Track changes and historical states for any tool.")
        hist_tool_name = st.selectbox("Select tool to investigate:", edit_df['name'].sort_values().unique())
        if hist_tool_name:
            hist_tid = edit_df[edit_df['name'] == hist_tool_name].iloc[0]['id']
            history = dm.get_tool_history(hist_tid)
            if not history.empty: 
                st.dataframe(
                    history, 
                    column_config={"change_date": st.column_config.DatetimeColumn("Date", format="D MMM, h:mm a")},
                    width="stretch"
                )
            else: st.caption("No history records found.")

    if current_user['role'] == "ADMIN":
        st.markdown("---")
        st.subheader("🛠️ Admin Tools")
        with st.expander("🧹 Clean Up Old Tool History", expanded=st.session_state['exp_purge']):
            st.session_state['exp_purge'] = True
            if st.button("🧹 Purge Stuff Older than 30 Days"):
                deleted = dm.purge_old_history(30)
                st.toast(f"Removed {deleted} old records.", icon="🗑️")
        
        st.markdown("---")
        with st.expander("🗑️ The Tool Incinerator (Admin Only)", expanded=st.session_state['exp_incin']):
            st.session_state['exp_incin'] = True
            st.markdown("#### 👻 Ghost Tool Detector")
            st.caption("Find and manage tools with missing owners.")
            if st.button("Scan for Ghost Tools"):
                st.session_state['ghost_scan_active'] = True
                
            if st.session_state.get('ghost_scan_active', False):
                ghosts = dm.get_ghost_tools()
                if not ghosts.empty:
                    count = len(ghosts)
                    st.warning(f"Found **{count}** tools haunting the database (Owners missing).")
                    st.dataframe(ghosts[['name', 'owner', 'status']], hide_index=True)
                    
                    c_adopt, c_burn = st.columns(2)
                    with c_adopt:
                        if st.button(f"Recall {count} Tools", help=f"Assign all to {current_user['name']}"):
                            dm.batch_reassign_tools(ghosts['id'].tolist(), current_user['name'], current_user['household'])
                            st.toast(f" recalled {count} tools from the void!", icon="🏡")
                            st.session_state['ghost_scan_active'] = False # Reset
                            time.sleep(1)
                            st.rerun()
                    with c_burn:
                        # Use a unique key for safety
                        if st.button(f"Incinerate {count} Ghost Tools", type="primary", key="burn_ghosts_btn"):
                            for tid in ghosts['id'].tolist():
                                dm.delete_tool(tid, current_user['name'])
                            st.toast(f"Incinerated {count} ghost tools.", icon="🔥")
                            st.session_state['ghost_scan_active'] = False # Reset
                            time.sleep(1)
                            st.rerun()
                else:
                    st.success("No ghost tools found! 👻")
                    # Optional: Auto-hide after a moment or provide a close button
                    if st.button("Close Scan"):
                        st.session_state['ghost_scan_active'] = False
                        st.rerun()

            st.divider()
            st.markdown("#### 🔥 Batch Incinerator")
            st.caption("Batch delete tools with AI filtering.")
            
            # 1. AI Filter Input
            if 'incin_filter_ids' not in st.session_state: st.session_state['incin_filter_ids'] = None
            
            with st.form("incin_filter_form"):
                c_ai_1, c_ai_2 = st.columns([4, 1], vertical_alignment="bottom")
                with c_ai_1:
                    filter_query = st.text_input("🤖 AI Filter:", placeholder="e.g., 'Delete all broken drills' or 'Tools owned by Ghost'")
                with c_ai_2:
                    submitted = st.form_submit_button("Apply Filter", width='stretch')
                
                if submitted:
                    if filter_query:
                        with st.spinner("Finding tools..."):
                            all_t = dm.get_all_tools()
                            st.session_state['incin_filter_ids'] = ai_find_tools_for_deletion(filter_query, all_t)
                    else:
                        st.session_state['incin_filter_ids'] = None
                        
            if st.button("Clear Filter"):
                st.session_state['incin_filter_ids'] = None
                st.rerun()

            # 2. Data Table
            all_tools_del = dm.get_all_tools()
            
            # Apply Filter if exists
            if st.session_state['incin_filter_ids']:
                display_df = all_tools_del[all_tools_del['id'].isin(st.session_state['incin_filter_ids'])]
                st.info(f"🤖 AI found {len(display_df)} matches.")
            else:
                display_df = all_tools_del
            
            # Selectable Dataframe
            selection = st.dataframe(
                display_df[['name', 'brand', 'owner', 'household', 'status']],
                width='stretch',
                hide_index=True,
                on_select="rerun",
                selection_mode="multi-row"
            )
            
            # 3. Action Button
            selected_rows = selection.selection.rows
            if selected_rows:
                # Get IDs from the indices (Indices are row numbers in the DISPLAYED dataframe)
                # We need to map back to the actual IDs in display_df
                selected_indices = selected_rows
                selected_ids = display_df.iloc[selected_indices]['id'].tolist()
                count = len(selected_ids)
                
                st.warning(f"You have selected {count} tools to **incinerate**.")
                
                if st.button(f"Incinerate {count} Selected Tools", type="primary"):
                    success_c = 0
                    for tid in selected_ids:
                        dm.delete_tool(tid, current_user['name'])
                        success_c += 1
                    
                    st.toast(f"Destroyed {success_c} tools.", icon="🔥")
                    st.session_state['incin_filter_ids'] = None # Reset
                    time.sleep(1.5)
                    st.rerun()
            else:
                st.caption("Select rows in the table to delete them.")
