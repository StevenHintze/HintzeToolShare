import streamlit as st
import pandas as pd
import time
from core.gemini_helper import parse_return_request

def render_return_tools(dm, current_user):
    st.header("🪃 Return Tools")
    
    # 1. Fetch Data
    all_tools = dm.get_all_tools() # Cached
    my_loans = all_tools[all_tools['borrower'] == current_user['name']]
    my_assets = all_tools[(all_tools['owner'] == current_user['name']) & (all_tools['status'] == 'Borrowed')]

    # 2. AI Interaction Section
    with st.expander("🤖 AI Assistant", expanded=True):
        st.caption("Naturally tell me what you returned or received back.")
        with st.form("ai_return_form"):
            user_input = st.text_input("Describe activity:", placeholder="e.g. 'I gave back the drill' or 'Shawn returned my saw'")
            submitted_ai = st.form_submit_button("Analyze")
        
        if submitted_ai and user_input:
            with st.spinner("Processing..."):
                result = parse_return_request(user_input, my_loans, my_assets)
                if result:
                    st.session_state['return_intent'] = result.get('intent')
                    st.session_state['return_ids'] = result.get('tool_ids', [])
                    st.rerun()
                else:
                    st.error("Could not understand the request.")

    # 3. Handle AI Processing Result (Confirmation)
    if st.session_state.get('return_ids'):
        intent = st.session_state.get('return_intent')
        ids = st.session_state['return_ids']
        
        # Filter tools based on IDs
        # We search in both lists to be safe, though intent should guide us
        target_tools = all_tools[all_tools['id'].isin(ids)]
        
        if not target_tools.empty:
            st.info(f"AI Detected: **{intent}** for {len(target_tools)} tools.")
            st.dataframe(target_tools[['name', 'borrower', 'owner', 'return_date']], hide_index=True)
            
            c_y, c_n = st.columns(2)
            if c_y.button("✅ Confirm & Process"):
                count = 0
                for tid in ids:
                    dm.return_tool(tid)
                    count += 1
                st.success(f"Processed {count} items!")
                st.session_state['return_ids'] = None
                st.session_state['return_intent'] = None
                time.sleep(3)
                st.rerun()
            
            if c_n.button("❌ Cancel"):
                st.session_state['return_ids'] = None
                st.rerun()
        else:
            st.warning("AI identified tools that I couldn't find in your active list.")
            st.session_state['return_ids'] = None

    st.divider()

    # 4. Manual Lists (Table UI)
    # Using Radio instead of Tabs to persist state during interaction
    if 'return_view_mode' not in st.session_state: st.session_state['return_view_mode'] = "Borrowed"

    _, col_mid, _ = st.columns([3, 2, 3])
    with col_mid:
        view_mode = st.radio("View:", ["Borrowed", "Lent"], horizontal=True, label_visibility="collapsed", key="return_view_radio")




    
    if view_mode == "Borrowed":
        st.subheader("🛠️ I Borrowed")
        if not my_loans.empty:
            my_loans['Due In'] = (pd.to_datetime(my_loans['return_date']) - pd.Timestamp.now()).dt.days
            def color_status(days):
                if days < 0: return "🔴 Overdue"
                if days <= 2: return "🟠 Due Soon"
                return "🟢 On Track"
            my_loans['Status'] = my_loans['Due In'].apply(color_status)

            # Updated for Multi-Select
            event_borrow = st.dataframe(
                my_loans[['name', 'brand', 'return_date', 'Status']], 
                column_config={"return_date": st.column_config.DateColumn("Return Date", format="MMM D")},
                width="stretch",
                hide_index=True,
                on_select="rerun",
                selection_mode="multi-row",
                key="borrow_table"
            )
            
            selected_indices = event_borrow.selection.rows
            if selected_indices:
                selected_rows = my_loans.iloc[selected_indices]
                st.info(f"Selected {len(selected_rows)} items to return.")
                if st.button(f"✅ Return {len(selected_rows)} Tools", key="btn_ret_me_multi"):
                    for _, row in selected_rows.iterrows():
                        dm.return_tool(row['id'])
                    st.success(f"Returned {len(selected_rows)} tools!")
                    time.sleep(3)
                    st.rerun()
        else:
            st.info("You don't owe anyone anything. Start a new project!")

    elif view_mode == "Lent":
        st.subheader("👀 Tools with Others")
        if not my_assets.empty:
            event_lend = st.dataframe(
                my_assets[['name', 'borrower', 'return_date']], 
                column_config={"return_date": st.column_config.DateColumn("Due Back", format="MMM D")},
                width="stretch",
                hide_index=True,
                on_select="rerun",
                selection_mode="multi-row",
                key="lend_table"
            )
            
            selected_indices_lend = event_lend.selection.rows
            if selected_indices_lend:
                selected_rows_lend = my_assets.iloc[selected_indices_lend]
                st.info(f"Selected {len(selected_rows_lend)} items received.")
                if st.button(f"📥 Mark {len(selected_rows_lend)} Received", key="btn_ret_own_multi"):
                    for _, row in selected_rows_lend.iterrows():
                        dm.return_tool(row['id'])
                    st.success(f"Marked {len(selected_rows_lend)} tools as returned.")
                    time.sleep(3)
                    st.rerun()
        else:
            st.info("All your tools are safe at home.")




