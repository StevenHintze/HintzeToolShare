import streamlit as st
from data_manager import DataManager
from ontology import FAMILY_TOOLS, FAMILY_TREE, check_safety

# 1. Setup & Config
st.set_page_config(page_title="HFTS", page_icon="🛠️")
st.title("🛠️ Hintze Family Tool Share")

# Initialize Database
dm = DataManager()
dm.seed_data(FAMILY_TOOLS, FAMILY_TREE)

# 2. Sidebar - User Selection
st.sidebar.header("Pick Your Name")
family_df = dm.get_family_members()
current_user_name = st.sidebar.selectbox("Select Name", family_df['name'])
current_user_role = dm.get_user_role(current_user_name)
st.sidebar.info(f"Logged in as: **{current_user_role}**")

# Hard Reset Button (Use once to load new data, then ignore)
if st.sidebar.button("⚠️ Reset Tool List"):
    dm.con.execute("DROP TABLE IF EXISTS tools")
    dm.con.execute("DROP TABLE IF EXISTS family")
    st.warning("Updated the tool list - click refresh please.")

# 3. Main Interface
tab1, tab2 = st.tabs(["Borrow Tools", "Return Tools"])

with tab1:
    st.header("Find & Borrow")
    
    # Search Bar
    search_query = st.text_input("🔍 I need to...", placeholder="e.g. fix a flat tire, drill concrete")
    
    # Filter Logic
    available_tools = dm.get_available_tools()
    if search_query:
        # Simple case-insensitive search
        available_tools = available_tools[available_tools['capabilities'].str.contains(search_query, case=False, na=False)]
    
    st.dataframe(available_tools[['name', 'safety_rating', 'capabilities', 'owner']])

    # Borrow Form
    st.subheader("Checkout")
    if not available_tools.empty:
        with st.form("borrow_form"):
            selected_tool_name = st.selectbox("Select Tool", available_tools['name'])
            days_needed = st.number_input("How many days will you need it?", min_value=1, value=3)
            submitted = st.form_submit_button("Mark it Borrowed")
            
            if submitted:
                # Safety Check
                tool_safety = available_tools.loc[available_tools['name'] == selected_tool_name, 'safety_rating'].iloc[0]
                
                if check_safety(current_user_role, tool_safety):
                    tool_id = available_tools.loc[available_tools['name'] == selected_tool_name, 'id'].iloc[0]
                    dm.borrow_tool(tool_id, current_user_name, days_needed)
                    st.success(f"✅ Tool borrowed - have fun or good luck! {selected_tool_name}.")
                    st.rerun()
                else:
                    st.error(f"🚫 STOP: {current_user_name} ({current_user_role}) is not allowed to borrow '{selected_tool_name}' ({tool_safety}).")
    else:
        st.info("Looks like no-one has a tool that fits the bill.")

with tab2:
    st.header("Return Tools")
    borrowed_tools = dm.get_borrowed_tools()
    
    if not borrowed_tools.empty:
        st.dataframe(borrowed_tools[['name', 'borrower', 'due_date']])
        
        tool_to_return = st.selectbox("Select Tool to Return", borrowed_tools['name'])
        if st.button("Mark it Returned"):
            tool_id = borrowed_tools.loc[borrowed_tools['name'] == tool_to_return, 'id'].iloc[0]
            dm.return_tool(tool_id)
            st.success("✅ Tool returned!")
            st.rerun()
    else:
        st.success("All tools are with their owners and ready for the next project.")