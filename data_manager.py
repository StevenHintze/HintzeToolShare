import duckdb
import streamlit as st
import pandas as pd

class DataManager:
    def __init__(self):
        # Connect to MotherDuck using the token in .streamlit/secrets.toml
        try:
            token = st.secrets["MOTHERDUCK_TOKEN"]
            self.con_str = f'md:hintze_inventory?motherduck_token={token}'
        except FileNotFoundError:
            # Fallback for local testing if secrets are missing
            self.con_str = 'inventory.db' 
        
        self.con = duckdb.connect(self.con_str)
        self._init_schema()

    def _init_schema(self):
        # 1. Create Tools Table
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS tools (
                id VARCHAR PRIMARY KEY,
                name VARCHAR,
                owner VARCHAR,
                status VARCHAR, 
                borrower VARCHAR,
                due_date TIMESTAMP,
                capabilities VARCHAR, 
                safety_rating VARCHAR
            )
        """)
        
        # 2. Create Family Table (This handles your dynamic roles)
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS family (
                name VARCHAR PRIMARY KEY,
                role VARCHAR,
                household VARCHAR
            )
        """)

    # --- Tool Methods ---
    def get_available_tools(self):
        return self.con.execute("SELECT * FROM tools WHERE status = 'Available'").df()
    
    def get_borrowed_tools(self):
        return self.con.execute("SELECT * FROM tools WHERE status = 'Borrowed'").df()

    def borrow_tool(self, tool_id, user, days):
        self.con.execute(f"""
            UPDATE tools 
            SET status = 'Borrowed', 
                borrower = '{user}', 
                due_date = current_date + INTERVAL '{days} days'
            WHERE id = '{tool_id}'
        """)
    
    def return_tool(self, tool_id):
        self.con.execute(f"UPDATE tools SET status='Available', borrower=NULL, due_date=NULL WHERE id='{tool_id}'")

    # --- Family Methods ---
    def get_family_members(self):
        """Fetches the dynamic list of family members."""
        return self.con.execute("SELECT * FROM family ORDER BY name").df()

    def get_user_role(self, user_name):
        """Finds the role for safety checks."""
        result = self.con.execute(f"SELECT role FROM family WHERE name = '{user_name}'").fetchone()
        return result[0] if result else "CHILD"

    def seed_data(self, tools_list, family_list):
        # Seed Tools if empty
        if self.con.execute("SELECT count(*) FROM tools").fetchone()[0] == 0:
            print("Seeding Tools...")
            for tool in tools_list:
                caps = tool['capabilities']
                if isinstance(caps, list): caps = ",".join(caps)
                self.con.execute("INSERT INTO tools VALUES (?, ?, ?, ?, ?, ?, ?, ?)", 
                    (tool['id'], tool['name'], tool['owner'], 'Available', None, None, caps, tool['safety']))

        # Seed Family if empty
        if self.con.execute("SELECT count(*) FROM family").fetchone()[0] == 0:
            print("Seeding Family Tree...")
            for person in family_list:
                self.con.execute("INSERT INTO family VALUES (?, ?, ?)", 
                    (person['name'], person['role'], person['household']))