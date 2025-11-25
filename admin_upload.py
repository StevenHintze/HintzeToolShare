import json
import duckdb
import streamlit as st
import pandas as pd

# Connect
token = st.secrets["MOTHERDUCK_TOKEN"]
con = duckdb.connect(f'md:hintze_inventory?motherduck_token={token}')

def upload_all():
    # --- 1. UPLOAD FAMILY ---
    try:
        with open('family_registry.json', 'r') as f:
            family_list = json.load(f)
        
        # Convert to DataFrame for Bulk Insert
        df_family = pd.DataFrame(family_list)
        
        con.execute("DROP TABLE IF EXISTS family")
        con.execute("CREATE TABLE family (name VARCHAR, role VARCHAR, household VARCHAR, email VARCHAR PRIMARY KEY)")
        
        # BULK INSERT (One network call instead of many)
        con.execute("INSERT INTO family SELECT * FROM df_family")
        print(f"✅ Uploaded {len(family_list)} family members.")
        
    except FileNotFoundError:
        print("⚠️ family_registry.json not found (Skipping)")

    # --- 2. UPLOAD TOOLS ---
    try:
        with open('tools_registry.json', 'r') as f:
            tool_list = json.load(f)
            
        # Pre-process data for DataFrame
        for t in tool_list:
            # Ensure capabilities is a string, not a list
            if isinstance(t['capabilities'], list):
                t['capabilities'] = ",".join(t['capabilities'])
            # Add missing defaults if needed
            if 'status' not in t: t['status'] = 'Available'
            if 'borrower' not in t: t['borrower'] = None
            if 'due_date' not in t: t['due_date'] = None

        df_tools = pd.DataFrame(tool_list)
        
        # Reorder columns to match Schema exactly
        # Schema: id, name, owner, household, status, borrower, due_date, capabilities, safety_rating
        # We rename JSON keys to match Schema if necessary (e.g. 'safety' -> 'safety_rating')
        df_tools = df_tools.rename(columns={'safety': 'safety_rating'})
        
        # Ensure column order matches the table we are about to create
        # We perform a SELECT to structure the data correctly
        
        con.execute("DROP TABLE IF EXISTS tools")
        con.execute("""
            CREATE TABLE tools (
                id VARCHAR PRIMARY KEY,
                name VARCHAR,
                owner VARCHAR,
                household VARCHAR,
                status VARCHAR, 
                borrower VARCHAR,
                due_date TIMESTAMP,
                capabilities VARCHAR, 
                safety_rating VARCHAR
            )
        """)
        
        # Use DuckDB's magic ability to read DF directly mapping columns by name is risky, 
        # so we select explicitly from the dataframe in the right order
        con.execute("""
            INSERT INTO tools 
            SELECT 
                id, name, owner, household, 
                'Available' as status, 
                NULL as borrower, 
                NULL as due_date, 
                capabilities, 
                safety_rating 
            FROM df_tools
        """)
        
        print(f"✅ Uploaded {len(tool_list)} tools.")
                
    except FileNotFoundError:
        print("⚠️ tools_registry.json not found (Skipping)")
    except Exception as e:
        print(f"❌ Error: {e}")

    print("🎉 Database Sync Complete!")

if __name__ == "__main__":
    upload_all()