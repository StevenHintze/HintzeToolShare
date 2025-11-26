import json
import duckdb
import streamlit as st
import pandas as pd
import os

# Connect
try:
    token = st.secrets["MOTHERDUCK_TOKEN"]
    con = duckdb.connect(f'md:hintze_inventory?motherduck_token={token}')
except:
    st.error("❌ Database Connection Failed. Check your tokens.")
    st.stop()

def upload_all():
    st.title("🔐 Registry Admin Uplink")
    
    # --- SECURITY: LOCAL CHECK ---
    # We check if the key exists in secrets. 
    # If you ONLY put this key in your local .streamlit/secrets.toml 
    # and NOT in the Cloud Dashboard, this script becomes impossible to run in the cloud.
    if "REGISTRY_KEY" not in st.secrets:
        st.error("🚫 **Security Lockout**")
        st.warning("The `REGISTRY_KEY` was not found. This script is designed to run **LOCALLY** only.")
        st.info("To run this, you must be on the Admin's physical computer with the local secrets file.")
        st.stop()

    # Security Input
    secret_input = st.text_input("Enter Registry Key to authorize update:", type="password")
    
    if st.button("🚀 Start Upload"):
        if secret_input != st.secrets["REGISTRY_KEY"]:
            st.error("⛔ Access Denied: Invalid Registry Key")
            return

        # --- 1. UPLOAD FAMILY ---
        try:
            with open('family_registry.json', 'r') as f:
                family_list = json.load(f)
            
            if isinstance(family_list, dict):
                family_list = list(family_list.values())[0] if family_list else []

            df_family = pd.DataFrame(family_list)
            
            con.execute("DROP TABLE IF EXISTS family")
            con.execute("CREATE TABLE family (name VARCHAR, role VARCHAR, household VARCHAR, email VARCHAR PRIMARY KEY)")
            con.execute("INSERT INTO family SELECT * FROM df_family")
            st.success(f"✅ Uploaded {len(family_list)} family members.")
            
        except FileNotFoundError:
            st.warning("⚠️ family_registry.json not found")
        except Exception as e:
            st.error(f"❌ Family Upload Error: {e}")

        # --- 2. UPLOAD TOOLS ---
        try:
            with open('tools_registry.json', 'r') as f:
                tool_list = json.load(f)

            # JSON Structure Repair
            if isinstance(tool_list, dict):
                for key, val in tool_list.items():
                    if isinstance(val, list):
                        tool_list = val
                        break

            # Pre-process
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
            
            # Updated Schema
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
            
            st.success(f"✅ Uploaded {len(tool_list)} tools.")
                    
        except FileNotFoundError:
            st.warning("⚠️ tools_registry.json not found")
        except Exception as e:
            st.error(f"❌ Tool Upload Error: {e}")

        st.success("🎉 Database Sync Complete!")
        # Close and kill process (Local only behavior)
        con.close()
        st.balloons()

if __name__ == "__main__":
    upload_all()