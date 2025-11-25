import streamlit as st
from data_manager import DataManager
from tools_registry import check_safety 
from gemini_helper import ai_parse_tool 
import time

st.set_page_config(page_title="HFTS", page_icon="🛠️")

# Initialize DB
dm = DataManager()
# Seed with empty lists because the Admin Script handles the data now
dm.seed_data([], []) 

# --- DYNAMIC DATA LOADING ---
try:
    family_df = dm.get_family_members()
    OWNER_HOMES = dict(zip(family_df['name'], family_df['household']))
    ALL_OWNERS = list(OWNER_HOMES.keys())
    ALL_HOUSEHOLDS = list(set(OWNER_HOMES.values()))
except:
    OWNER_HOMES = {}
    ALL_OWNERS = ["Admin"]
    ALL_HOUSEHOLDS = ["Main House"]

# --- AUTHENTICATION LOGIC ---
if "user_info" not in st.session_state:
    st.session_state["user_info"] = None

def login():
    email = st.session_state.get("email_input", "").strip().lower()
    password = st.session_state.get("password_input", "")
    
    if password == st.secrets["FAMILY_PASSWORD"]:
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
    st.session_state["user_info"] = None
    st.rerun()

# Main Interface
tabs = ["Borrow Tools", "Return Tools", "🤖 Tool Manager"]
if current_user['role'] == "ADMIN":
    tabs.append("🔐 Admin")

current_tabs = st.tabs(tabs)

# TAB 1: Borrow
with current_tabs[0]:
    st.header("Find & Borrow")
    search_query = st.text_input("🔍 I need to...", placeholder="e.g. fix a flat tire, drill concrete")
    
    available_tools = dm.get_available_tools()
    if search_query:
        available_tools = available_tools[available_tools['capabilities'].str.contains(search_query, case=False, na=False)]
    
    st.dataframe(available_tools[['name', 'household', 'safety_rating', 'capabilities', 'owner']])

    st.subheader("Checkout")
    if not available_tools.empty:
        with st.form("borrow_form"):
            selected_tool_name = st.selectbox("Select Tool", available_tools['name'])
            days_needed = st.number_input("Days Needed", min_value=1, value=3)
            if st.form_submit_button("Mark it Borrowed"):
                tool_row = available_tools[available_tools['name'] == selected_tool_name].iloc[0]
                if check_safety(current_user['role'], tool_row['safety_rating']):
                    dm.borrow_tool(tool_row['id'], current_user['name'], days_needed)
                    st.success(f"✅ Borrowed {selected_tool_name}!")
                    st.rerun()
                else:
                    st.error(f"🚫 Safety Restriction: {tool_row['safety_rating']}")
    else:
        st.info("No matching tools found.")

# TAB 2: Return
with current_tabs[1]:
    st.header("Return Tools")
    borrowed_tools = dm.get_borrowed_tools()
    if not borrowed_tools.empty:
        st.dataframe(borrowed_tools[['name', 'borrower', 'due_date']])
        tool_to_return = st.selectbox("Select Tool", borrowed_tools['name'])
        if st.button("Mark it Returned"):
            tool_id = borrowed_tools.loc[borrowed_tools['name'] == tool_to_return, 'id'].iloc[0]
            dm.return_tool(tool_id)
            st.success("✅ Returned!")
            st.rerun()
    else:
        st.success("No tools are currently borrowed.")

# TAB 3: Tool Manager
with current_tabs[2]:
    from gemini_helper import get_ai_advice 
    st.header("Ask the Tool Manager")
    project_query = st.text_area("What project are you planning?", placeholder="e.g., I need to build a planter box...")
    
    if st.button("Get Advice"):
        if project_query:
            with st.spinner("Consulting the inventory..."):
                advice = get_ai_advice(project_query, dm.get_available_tools())
                st.markdown(advice)

# TAB 4: Admin
if current_user['role'] == "ADMIN":
    with current_tabs[3]:
        st.header("Add New Tool")
        
        col_ai_1, col_ai_2, col_ai_3 = st.columns([1, 2, 1])
        with col_ai_1:
            quick_owner = st.selectbox("Who bought it?", ALL_OWNERS, key="ai_owner_select")
        with col_ai_2:
            raw_input = st.text_input("Paste Description", key="ai_input", label_visibility="collapsed")
        with col_ai_3:
            if st.button("✨ Auto-Fill", use_container_width=True):
                if raw_input:
                    with st.spinner("Analyzing..."):
                        ai_data = ai_parse_tool(raw_input)
                        if ai_data:
                            st.session_state['form_name'] = ai_data['name']
                            st.session_state['form_caps'] = ai_data['capabilities']
                            try:
                                st.session_state['form_safety_index'] = ["Open", "Supervised", "Adult Only"].index(ai_data['safety'])
                            except:
                                st.session_state['form_safety_index'] = 0
                            
                            st.session_state['form_owner'] = quick_owner
                            st.session_state['form_household'] = OWNER_HOMES.get(quick_owner, ALL_HOUSEHOLDS[0])
                            st.success("Parsed!")

        with st.form("add_tool"):
            if 'form_name' not in st.session_state: st.session_state['form_name'] = ""
            if 'form_caps' not in st.session_state: st.session_state['form_caps'] = ""
            if 'form_safety_index' not in st.session_state: st.session_state['form_safety_index'] = 0
            
            default_owner_idx = 0
            if 'form_owner' in st.session_state and st.session_state['form_owner'] in ALL_OWNERS:
                 default_owner_idx = ALL_OWNERS.index(st.session_state['form_owner'])