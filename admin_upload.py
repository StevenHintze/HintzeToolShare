import json
import duckdb
import streamlit as st
import pandas as pd
import os

# Connect
token = st.secrets["MOTHERDUCK_TOKEN"]
con = duckdb.connect(f'md:hintze_inventory?motherduck_token={token}')

def upload_all():
    # --- 1. UPLOAD FAMILY ---
    try:
        with open('family_registry.json', 'r') as f:
            family_list = json.load(f)
        
        df_family = pd.DataFrame(family_list)
        
        con.execute("DROP TABLE IF EXISTS family")
        con.execute("CREATE TABLE family (name VARCHAR, role VARCHAR, household VARCHAR, email VARCHAR PRIMARY KEY)")
        con.execute("INSERT INTO family SELECT * FROM df_family")
        print(f"✅ Uploaded {len(family_list)} family members.")
        
    except FileNotFoundError:
        print("⚠️ family_registry.json not found")

    # --- 2. UPLOAD TOOLS ---
    try:
        with open('tools_registry.json', 'r') as f:
            tool_list = json.load(f)
            
        # Pre-process
        for t in tool_list:
            if isinstance(t['capabilities'], list):
                t['capabilities'] = ",".join(t['capabilities'])
            # Defaults
            t.setdefault('status', 'Available')
            t.setdefault('borrower', None)
            t.setdefault('return_date', None) # Changed from due_date
            t.setdefault('bin_location', '')
            t.setdefault('brand', '')
            t.setdefault('model_no', '')
            t.setdefault('power_source', 'Manual')
            if 'is_stationary' not in t: t['is_stationary'] = False # Default is transportable

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
                is_stationary BOOLEAN, -- <--- NEW COLUMN
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
        
        print(f"✅ Uploaded {len(tool_list)} tools.")
                
    except FileNotFoundError:
        print("⚠️ tools_registry.json not found")
    except Exception as e:
        print(f"❌ Error: {e}")

    print("🎉 Database Sync Complete!")
    con.close()
    os._exit(0)

if __name__ == "__main__":
    upload_all()