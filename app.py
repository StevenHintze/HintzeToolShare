import streamlit as st
from data_manager import DataManager
# FIX 1: Don't import FAMILY_TREE (it lives in the DB/JSON now)
from ontology import FAMILY_TOOLS, check_safety 
import time

st.set_page_config(page_title="HFTS", page_icon="🛠️")

# Initialize DB
dm = DataManager()
# FIX 2: Pass empty list [] for family so we don't overwrite the Admin data
dm.seed_data(FAMILY_TOOLS, [])

# --- AUTHENTICATION LOGIC ---
if "user_info" not in st.session_state:
    st.session_state["user_info"] = None

def login():
    # Use .get() to avoid errors if key is missing
    email = st.session_state.get("email_input", "").strip().lower()
    password = st.session_state.get("password_input", "")
    
    # 1. Check Shared Password (Gatekeeper)
    if password == st.secrets["FAMILY_PASSWORD"]:
        # 2. Check Email (Identity)
        user = dm.get_user_by_email(email)
        if user:
            st.session_state["user_info"] = user
            st.success(f"Welcome back, {user['name']}!")
            time.sleep(1)
            st.rerun()
        else:
            st.error("Email not found in the Family Registry.")
    else:
        st.error("Incorrect Family Password.")

# Show Login Screen if not logged in
if st.session_state["user_info"] is None:
    st.title("🔐 Family Login")
    st.text_input("Email Address", key="email_input")
    st.text_input("Family Password", type="password", key="password_input")
    st.button("Log In", on_click=login)
    st.stop() # Stop here until logged in

# --- APP STARTS HERE (Only runs if logged in) ---
current_user = st.session_state["user_info"]
st.title(f"🛠️ Hintze Family Tool Share")

# Sidebar Profile
st.sidebar.header("My Profile")
st.sidebar.write(f"**Name:** {current_user['name']}")
st.sidebar.write(f"**Role:** {current_user['role']}")
st.sidebar.write(f"**House:** {current_user['household']}")

if st.sidebar.button("Log Out"):
    st.session_state["user_info"] = None
    st.rerun()

# 3. Main Interface
tab1, tab2 = st.tabs(["Borrow Tools", "Return Tools"])

with tab1:
    st.header("Find & Borrow")
    
    # Search Bar
    search_query = st.text_input("🔍 I need to...", placeholder="e.g. fix a flat tire, drill concrete")
    
    # Filter Logic
    available_tools = dm.get_available_tools()
    if search_query:
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
                
                # FIX 3: Use current_user['role'] instead of current_user_role
                if check_safety(current_user['role'], tool_safety):
                    tool_id = available_tools.loc[available_tools['name'] == selected_tool_name, 'id'].iloc[0]
                    
                    # FIX 4: Use current_user['name'] instead of current_user_name
                    dm.borrow_tool(tool_id, current_user['name'], days_needed)
                    
                    st.success(f"✅ Tool borrowed - have fun or good luck! {selected_tool_name}.")
                    st.rerun()
                else:
                    # FIX 5: Use dict keys for error message
                    st.error(f"🚫 STOP: {current_user['name']} ({current_user['role']}) is not allowed to borrow '{selected_tool_name}' ({tool_safety}).")
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