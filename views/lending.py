import streamlit as st
import time
from gemini_helper import parse_borrowing_request, parse_lending_request
from tools_registry import check_safety

def render_lending(dm, current_user):
    st.header("🤝 Lending & Borrowing Center")
    family_df = dm.get_family_members()
        
    # --- SECTION 1: BORROW TOOLS (SELF) ---
    # Maintain expanded state via session state
    if 'exp_borrow' not in st.session_state: st.session_state['exp_borrow'] = False
    if 'exp_lend' not in st.session_state: st.session_state['exp_lend'] = False

    with st.expander("⬇️ Borrow Tools (For You)", expanded=st.session_state['exp_borrow']):
        st.session_state['exp_borrow'] = True # If they are seeing this code, it's expanded or being interacted with
        st.caption("Quickly borrow tools for yourself from others.")
        # Cached query
        all_tools_borrow = dm.get_all_tools()
        # Filter: Available, Not Stationary, AND Not In My Household
        available_only = all_tools_borrow[
            (all_tools_borrow['status'] == 'Available') & 
            (all_tools_borrow['is_stationary'] != True) &
            (all_tools_borrow['household'] != current_user['household'])
        ]
        
        if not available_only.empty:
            method_b = st.radio("Input Method:", ["🤖 AI Assistant", "📝 Manual Selection"], horizontal=True, key="borrow_method")
            
            if 'borrow_stage' not in st.session_state: st.session_state['borrow_stage'] = 'manual'
            if 'borrow_data' not in st.session_state: st.session_state['borrow_data'] = None

            if method_b == "📝 Manual Selection" and st.session_state.get('borrow_stage') != 'manual':
                st.session_state['borrow_stage'] = 'manual'
                st.session_state['borrow_data'] = None

            if method_b == "🤖 AI Assistant":
                with st.container(border=True):
                    st.caption("Tell me what you need (e.g., 'I need to borrow the truck for 3 days').")
                    with st.form("ai_borrow_form"):
                        borrow_query = st.text_input("What do you need?", placeholder="Type here and press Enter...")
                        submitted_b = st.form_submit_button("Analyze Request", width='stretch')
                    
                    if submitted_b and borrow_query:
                        with st.spinner("Processing..."):
                            result_b = parse_borrowing_request(borrow_query, available_only)
                            if result_b and result_b.get('candidates'):
                                st.session_state['borrow_stage'] = 'refine'
                                st.session_state['borrow_data'] = result_b
                                st.rerun()
                            elif result_b:
                                st.warning("I couldn't find any matching tools. Please try manual selection.")
                                st.session_state['borrow_stage'] = 'manual'
                            else:
                                st.error("Could not understand request.")

            if st.session_state.get('borrow_stage') == 'refine' and st.session_state.get('borrow_data'):
                st.divider()
                st.info("🔎 I found multiple options. Select the ones you mean:")
                with st.form("refine_borrow_candidates"):
                    cands_b = st.session_state['borrow_data'].get('candidates', [])
                    selected_cands_ids_b = []
                    for c in cands_b:
                        label = f"**{c['name']}**"
                        if c.get('household'): label += f" ({c['household']})"
                        is_checked = st.checkbox(label, value=True, key=f"b_cand_{c['id']}")
                        if is_checked:
                            selected_cands_ids_b.append(c['id'])
                    
                    if st.form_submit_button("Confirm Selection"):
                        st.session_state['borrow_data']['tool_ids'] = selected_cands_ids_b
                        st.session_state['borrow_stage'] = 'verify'
                        st.rerun()

            if st.session_state.get('borrow_stage') in ['verify', 'manual'] or st.session_state.get('borrow_stage') is None:
                default_borrow_tools = []
                default_borrow_days = 7
                
                if st.session_state.get('borrow_data'):
                    data_b = st.session_state['borrow_data']
                    if data_b.get('duration_days'):
                        try: default_borrow_days = int(data_b['duration_days'])
                        except: pass
                    if data_b.get('tool_ids'):
                        pre_sel_b = available_only[available_only['id'].isin(data_b['tool_ids'])]['name'].tolist()
                        default_borrow_tools = pre_sel_b

                with st.form("manual_borrow_multi"):
                    t_options = available_only['name'].tolist()
                    selected_tools = st.multiselect("Select Tools to Borrow:", t_options, default=default_borrow_tools)
                    days_needed = st.number_input("Days Needed", min_value=1, value=default_borrow_days, key="borrow_days")
                    
                    if st.form_submit_button("Confirm Borrow Request", width='stretch'):
                        if selected_tools:
                            success_count = 0
                            for t_name in selected_tools:
                                tool_row = available_only[available_only['name'] == t_name].iloc[0]
                                if check_safety(current_user['role'], tool_row['safety_rating']):
                                    dm.borrow_tool(tool_row['id'], current_user['name'], days_needed)
                                    success_count += 1
                                else:
                                    st.error(f"🚫 Safety Restriction on {t_name}")
                            
                            if success_count > 0:
                                st.toast(f"✅ Successfully borrowed {success_count} tools!", icon="🚚")
                                st.session_state['borrow_stage'] = 'manual'
                                st.session_state['borrow_data'] = None
                                time.sleep(1.5)
                                st.rerun()
                        else:
                            st.warning("Please select at least one tool.")
        else:
            st.info("No transportable tools available from other households.")

    st.markdown("---")

    # --- SECTION 2: LEND TOOLS (OTHERS) ---
    # Auto-expand if we are in the middle of an AI flow
    lending_active = st.session_state.get('lend_stage') in ['refine', 'verify']
    if lending_active: st.session_state['exp_lend'] = True

    with st.expander("⬆️ Lend Tools (To Others)", expanded=st.session_state['exp_lend']):
        st.session_state['exp_lend'] = True
        st.caption(f"Lend tools to other family members.")
        
        admin_override = False
        if current_user['role'] == "ADMIN":
            admin_override = st.toggle("🛡️ Admin Mode: Lend Any Tool", value=False)
        
        if admin_override:
            lending_pool = dm.get_all_tools()
            lending_pool = lending_pool[lending_pool['status'] == 'Available']
            st.caption("Showing ALL available tools in registry.")
        else:
            lending_pool = dm.get_my_tools(current_user['name'])
            lending_pool = lending_pool[lending_pool['status'] == 'Available']
            st.caption(f"Showing tools owned by {current_user['name']}.")

        method = st.radio("Input Method:", ["🤖 AI Assistant", "📝 Manual Selection"], horizontal=True)
        
        if 'lend_stage' not in st.session_state: st.session_state['lend_stage'] = 'manual'
        if 'lend_data' not in st.session_state: st.session_state['lend_data'] = None

        if method == "📝 Manual Selection" and st.session_state.get('lend_stage') != 'manual':
             st.session_state['lend_stage'] = 'manual'
             st.session_state['lend_data'] = None

        if method == "🤖 AI Assistant":
            with st.container(border=True):
                st.caption("Describe what happened naturally (e.g., 'I lent the drill to Shawn').")
                with st.form("ai_lending_form"):
                    lending_query = st.text_input("Tell me what's happening:", placeholder="Type here and press Enter...")
                    submitted = st.form_submit_button("Analyze Request", width='stretch')
                
                if submitted and lending_query:
                    with st.spinner("Processing..."):
                        fam_list = dm.get_family_members().to_dict('records')
                        result = parse_lending_request(lending_query, lending_pool, fam_list)
                        
                        if result:
                            if result.get('candidates'):
                                st.session_state['lend_stage'] = 'refine'
                                st.session_state['lend_data'] = result
                            else:
                                st.warning("I couldn't find any tools matching your description. Please select manually.")
                                st.session_state['lend_stage'] = 'verify'
                                st.session_state['lend_data'] = result
                        else:
                            st.error("Could not understand request.")

        if st.session_state.get('lend_stage') == 'refine' and st.session_state.get('lend_data'):
            st.divider()
            st.info("🔎 I found multiple options. Select the ones you mean:")
            with st.form("refine_candidates"):
                cands = st.session_state['lend_data'].get('candidates', [])
                selected_cands_ids = []
                for c in cands:
                    label = f"**{c['name']}**"
                    if c.get('household'): label += f" ({c['household']})"
                    is_checked = st.checkbox(label, value=True, key=f"cand_{c['id']}")
                    if is_checked:
                        selected_cands_ids.append(c['id'])
                
                if st.form_submit_button("Confirm Selection"):
                    st.session_state['lend_data']['tool_ids'] = selected_cands_ids
                    st.session_state['lend_stage'] = 'verify'
                    st.rerun()

        if st.session_state.get('lend_stage') in ['verify', 'manual'] or st.session_state.get('lend_stage') is None: 
            st.markdown("---")
            st.subheader("Confirm Details")

            default_tools = []
            default_borrower = None
            default_days = 7
            force_safety = False
            
            if st.session_state.get('lend_data'):
                data = st.session_state['lend_data']
                member_names = family_df['name'].tolist()
                if data.get('borrower_name') in member_names:
                    default_borrower = data['borrower_name']
                
                if data.get('duration_days'):
                    try: default_days = int(data['duration_days'])
                    except: pass
                
                if data.get('tool_ids'):
                    t_ids = data['tool_ids']
                    # Filter pre-selected
                    pre_selected = lending_pool[lending_pool['id'].isin(t_ids)]['name'].tolist()
                    default_tools = pre_selected
                
                if data.get('force_override'): force_safety = True
                
                if st.session_state['lend_stage'] == 'verify':
                    st.info("👇 Please verify the details below.")

            if lending_pool.empty:
                 if admin_override:
                     st.warning("⚠️ No tools available in the entire registry.")
                 else:
                     chk = dm.get_my_tools(current_user['name'])
                     if chk.empty:
                         st.warning("⚠️ You don't have any tools in your toolbox yet.")
                     else:
                         st.warning(f"⚠️ You have {len(chk)} tools, but they are ALL currently borrowed or unavailable.")
            
            with st.form("lending_form"):
                selected_tool_names = st.multiselect("Select Tools", lending_pool['name'], default=default_tools)
                borrower = st.selectbox("Lending To:", family_df['name'], index=family_df['name'].tolist().index(default_borrower) if default_borrower else None)
                days = st.number_input("Duration (Days)", min_value=1, value=default_days)
                
                safety_warning = []
                requires_override = False
                
                if selected_tool_names and borrower:
                    b_role = family_df[family_df['name'] == borrower].iloc[0]['role']
                    for t_name in selected_tool_names:
                        t_row = lending_pool[lending_pool['name'] == t_name].iloc[0]
                        if b_role == "CHILD" and t_row['safety_rating'] == "Adult Only":
                            safety_warning.append(f"⛔ **{t_name}** is 'Adult Only' and **{borrower}** is a Child.")
                            requires_override = True
                
                if requires_override:
                    st.error("⚠️ Safety Alert")
                    for w in safety_warning: st.write(w)
                    authorized = st.checkbox("☑️ I authorize this loan and assume full responsibility for safety.", value=force_safety)
                else:
                    authorized = True

                if st.form_submit_button("Confirm Loan 🤝", width='stretch'):
                    if not selected_tool_names:
                        st.error("Select at least one tool.")
                    elif not borrower:
                        st.error("Select a borrower.")
                    elif requires_override and not authorized:
                        st.error("You must authorize the safety override to proceed.")
                    else:
                        success_count = 0
                        for t_name in selected_tool_names:
                            tid = lending_pool[lending_pool['name'] == t_name].iloc[0]['id']
                            dm.borrow_tool(tid, borrower, days)
                            success_count += 1
                        
                        dm.clear_cache()
                        st.toast(f"Successfully lent {success_count} tools to {borrower}!", icon="✅")
                        st.session_state['lend_stage'] = 'manual'
                        st.session_state['lend_data'] = None
                        time.sleep(1.5)
                        st.rerun()
