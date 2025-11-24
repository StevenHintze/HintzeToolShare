import json
import duckdb
import streamlit as st

# Connect to MotherDuck using your local secrets
token = st.secrets["MOTHERDUCK_TOKEN"]
con = duckdb.connect(f'md:hintze_inventory?motherduck_token={token}')

def upload_family():
    # 1. Load the private JSON file
    try:
        with open('family_registry.json', 'r') as f:
            family_list = json.load(f)
    except FileNotFoundError:
        print("❌ Error: family_registry.json not found!")
        return

    # 2. Reset the Family Table (Optional: clears old data to prevent duplicates)
    con.execute("DROP TABLE IF EXISTS family")
    con.execute("""
        CREATE TABLE family (
            name VARCHAR,
            role VARCHAR,
            household VARCHAR,
            email VARCHAR PRIMARY KEY
        )
    """)

    # 3. Insert the Data
    print(f"Uploading {len(family_list)} family members...")
    for person in family_list:
        con.execute("INSERT INTO family VALUES (?, ?, ?, ?)", 
            (person['name'], person['role'], person['household'], person['email']))
    
    print("✅ Success! Family data is secure in the cloud.")

if __name__ == "__main__":
    upload_family()