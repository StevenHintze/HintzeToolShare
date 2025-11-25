import duckdb
import streamlit as st
import pandas as pd

class DataManager:
    def __init__(self):
        try:
            token = st.secrets["MOTHERDUCK_TOKEN"]
            self.con_str = f'md:?motherduck_token={token}'
        except FileNotFoundError:
            self.con_str = 'inventory.db' 
        
        self.con = duckdb.connect(self.con_str)
        
        # Ensure we are in the right database
        self.con.execute("CREATE DATABASE IF NOT EXISTS hintze_inventory")
        self.con.execute("USE hintze_inventory")
        
        self._init_schema()

    def _init_schema(self):
        # Tools Table
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS tools (
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
        
        # Family Table
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS family (
                name VARCHAR,
                role VARCHAR,
                household VARCHAR,
                email VARCHAR PRIMARY KEY
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
    def get_user_by_email(self, email):
        """Returns the user dictionary if email exists, else None."""
        # This is the function that was missing!
        result = self.con.execute("SELECT name, role, household FROM family WHERE email = ?", [email]).fetchone()
        
        if result:
            return {"name": result[0], "role": result[1], "household": result[2]}
        return None

    def seed_data(self, tools_list, family_list):
        # Seed Tools
        if self.con.execute("SELECT count(*) FROM tools").fetchone()[0] == 0:
            print("Seeding Tools...")
            for tool in tools_list:
                caps = tool['capabilities']
                if isinstance(caps, list): caps = ",".join(caps)
                self.con.execute("INSERT INTO tools VALUES (?, ?, ?, ?, ?, ?, ?, ?)", 
                    (tool['id'], tool['name'], tool['owner'], 'Available', None, None, caps, tool['safety']))

        # Seed Family (Handles empty lists gracefully now)
        if family_list and self.con.execute("SELECT count(*) FROM family").fetchone()[0] == 0:
            print("Seeding Family Tree...")
            for person in family_list:
                self.con.execute("INSERT INTO family VALUES (?, ?, ?, ?)", 
                    (person['name'], person['role'], person['household'], person['email']))