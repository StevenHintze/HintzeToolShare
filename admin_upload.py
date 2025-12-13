import json
import duckdb
import streamlit as st
import pandas as pd
import os

# --- SETUP & CONNECTION ---
st.set_page_config(page_title="Admin Uplink", page_icon="📡")

try:
    token = st.secrets["MOTHERDUCK_TOKEN"]
    con = duckdb.connect(f'md:hintze_inventory?motherduck_token={token}')
except:
    st.error("❌ Database Connection Failed. Check your tokens.")
    st.stop()

# --- LOCAL SECURITY CHECK ---
if "REGISTRY_KEY" not in st.secrets:
    st.error("🚫 **Security Lockout**")
    st.warning("The `REGISTRY_KEY` was not found. This script is designed to run **LOCALLY** only.")
    st.stop()

# --- HELPER FUNCTIONS ---
def update_family():
    """Reads family_registry.json and replaces the DB table."""
    try:
        with open('family_registry.json', 'r') as f:
            family_list = json.load(f)
        
        if isinstance(family_list, dict):
            family_list = list(family_list.values())[0] if family_list else []

        df_family = pd.DataFrame(family_list)
        
        con.execute("DROP TABLE IF EXISTS family")
        con.execute("CREATE TABLE family (name VARCHAR, role VARCHAR, household VARCHAR, email VARCHAR PRIMARY KEY)")
        con.execute("INSERT INTO family SELECT * FROM df_family")
        st.success(f"✅ Success! Updated {len(family_list)} family members.")
        return True
        
    except FileNotFoundError:
        st.error("⚠️ family_registry.json not found")
        return False
    except Exception as e:
        st.error(f"❌ Family Upload Error: {e}")
        return False

def update_tools():
    """Reads tools_registry.json and replaces the DB table."""
    try:
        with open('tools_registry.json', 'r') as f:
            tool_list = json.load(f)

        if isinstance(tool_list, dict):
            for key, val in tool_list.items():
                if isinstance(val, list):
                    tool_list = val
                    break

        # Pre-process defaults
        for t in tool_list:
            if isinstance(t['capabilities'], list):
                t['capabilities'] = ",".join(t['capabilities'])
            
            t.setdefault('status', 'Available')
            t.setdefault('borrower', None)
            t.setdefault('return_date', None)
            t.setdefault('bin_location', '')
            t.setdefault('brand', '')
            t.setdefault('model_no', '')
            t.setdefault('power_source', 'Manual')
            t.setdefault('is_stationary', False)

        df_tools = pd.DataFrame(tool_list)
        df_tools = df_tools.rename(columns={'safety': 'safety_rating'})
        
        con.execute("DROP TABLE IF EXISTS tools")
        
        con.execute("""
            CREATE TABLE tools (
                id VARCHAR PRIMARY KEY,
                name VARCHAR,
                brand VARCHAR,
                model_no VARCHAR,
                power_source VARCHAR,
                owner VARCHAR,
                household VARCHAR,
                bin_location VARCHAR,
                is_stationary BOOLEAN,
                status VARCHAR, 
                borrower VARCHAR,
                return_date TIMESTAMP,
                capabilities VARCHAR, 
                safety_rating VARCHAR
            )
        """)
        
        con.execute("""
            INSERT INTO tools 
            SELECT 
                id, name, brand, model_no, power_source, 
                owner, household, bin_location, is_stationary,
                'Available' as status, 
                NULL as borrower, 
                NULL as return_date, 
                capabilities, 
                safety_rating 
            FROM df_tools
        """)
        
        st.success(f"✅ Success! Uploaded {len(tool_list)} tools.")
        return True
                
    except FileNotFoundError:
        st.error("⚠️ tools_registry.json not found")
        return False
    except Exception as e:
        st.error(f"❌ Tool Upload Error: {e}")
        return False

# --- MAIN UI ---
st.title("🔐 Registry Admin Uplink")
st.info("This interface pushes your local JSON files to the Cloud Database.")

secret_input = st.text_input("Enter Registry Key to unlock controls:", type="password")

if secret_input == st.secrets["REGISTRY_KEY"]:
    st.success("🔓 Access Granted")
    st.markdown("---")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("Family Only")
        st.caption("Updates names, emails, and roles.")
        if st.button("Update Family 👥", use_container_width=True):
            update_family()
            
    with col2:
        st.subheader("Tools Only")
        st.caption("Overwrites tool list (Resets borrow status).")
        if st.button("Update Tools 🛠️", use_container_width=True):
            update_tools()
            
    with col3:
        st.subheader("Nuclear Option")
        st.caption("Wipes and re-uploads everything.")
        if st.button("Update Everything 🚀", type="primary", use_container_width=True):
            f = update_family()
            t = update_tools()
            if f and t:
                st.balloons()
                st.success("Full System Sync Complete!")

elif secret_input:
    st.error("⛔ Access Denied: Invalid Registry Key")