import streamlit as st
import time
from core.gemini_helper import ai_filter_inventory
from core.tools_registry import check_safety


def render_arsenal(dm, current_user):
    st.header("🧰 Tool Arsenal (Hintze Family Tools)")
    if current_user['role'] in ["ADMIN", "ADULT"]:
        if st.button("Need to add or edit tools? Go to 🛡️ The Armory", type="secondary", icon="🔧"):
            st.session_state['nav_tab'] = "Armory"
            st.rerun()
        
    c1, c2 = st.columns([5, 1], vertical_alignment="bottom")
    with c1:
        query = st.text_input("🔎 Search or Ask...", placeholder="e.g. 'Automotive tools' or 'What has Shawn borrowed?'")
    with c2:
        use_ai = st.toggle("AI Search", value=True)

    # CACHED QUERY
    all_tools = dm.get_all_tools() 
    filtered_df = all_tools.copy()
    
    if query:
        if use_ai:
            with st.spinner("AI is filtering..."):
                match_ids = ai_filter_inventory(query, all_tools)
                filtered_df = all_tools[all_tools['id'].isin(match_ids)].copy()
        else:
            mask = (
                all_tools['name'].str.contains(query, case=False, na=False) | 
                all_tools['brand'].str.contains(query, case=False, na=False) |
                all_tools['capabilities'].str.contains(query, case=False, na=False)
            )
            filtered_df = all_tools[mask].copy()

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
        column_config={"return_date": st.column_config.DatetimeColumn("Due Back", format="ddd, MMM D")},
        width='stretch'
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
                    time.sleep(1.5)
                    st.rerun()
                else:
                    st.error("🚫 Safety Restriction.")
    else:
        st.info("No transportable tools available.")
