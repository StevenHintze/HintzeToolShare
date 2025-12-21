import streamlit as st
import pandas as pd

def render_return_tools(dm, current_user):
    st.header("🪃 Return Tools")
    all_tools = dm.get_all_tools() # Cached
    my_loans = all_tools[all_tools['borrower'] == current_user['name']]
    
    st.subheader("🛠️ Tools I have Borrowed")
    if not my_loans.empty:
        my_loans['Due In'] = (pd.to_datetime(my_loans['return_date']) - pd.Timestamp.now()).dt.days
        def color_status(days):
            if days < 0: return "🔴 Overdue"
            if days <= 2: return "🟠 Due Soon"
            return "🟢 On Track"
        my_loans['Status'] = my_loans['Due In'].apply(color_status)

        st.dataframe(
            my_loans[['name', 'brand', 'household', 'return_date', 'Status']], 
            column_config={"return_date": st.column_config.DateColumn("Return Date", format="ddd, MMM D")},
            width="stretch"
        )
        
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
        st.dataframe(
            my_assets[['name', 'borrower', 'return_date']], 
            column_config={"return_date": st.column_config.DateColumn("Due Back", format="ddd, MMM D")},
            width="stretch"
        )
        
        tool_back = st.selectbox("Select tool received:", my_assets['name'], key="owner_return_select")
        if st.button("📥 Mark as Received"):
            tid = my_assets[my_assets['name'] == tool_back].iloc[0]['id']
            dm.return_tool(tid)
            st.success(f"Marked {tool_back} as returned.")
            st.rerun()
    else:
        st.success("All your tools are safe at home.")
