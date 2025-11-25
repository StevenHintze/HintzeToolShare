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
        self.con.execute("CREATE DATABASE IF NOT EXISTS hintze_inventory")
        self.con.execute("USE hintze_inventory")
        self._init_schema()

    def _init_schema(self):
        # Tools Table (Updated Schema)
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS tools (
                id VARCHAR PRIMARY KEY,
                name VARCHAR,
                brand VARCHAR,
                model_no VARCHAR,
                power_source VARCHAR,
                owner VARCHAR,
                household VARCHAR,
                bin_location VARCHAR,
                status VARCHAR, 
                borrower VARCHAR,
                return_date TIMESTAMP, -- RENAMED
                capabilities VARCHAR, 
                safety_rating VARCHAR
            )
        """)
        
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS family (
                name VARCHAR,
                role VARCHAR,
                household VARCHAR,
                email VARCHAR PRIMARY KEY
            )
        """)

    def get_available_tools(self):
        return self.con.execute("SELECT * FROM tools WHERE status = 'Available'").df()
    
    def get_borrowed_tools(self):
        return self.con.execute("SELECT * FROM tools WHERE status = 'Borrowed'").df()

    def borrow_tool(self, tool_id, user, days):
        # UPDATED: Set return_date
        self.con.execute(f"""
            UPDATE tools 
            SET status = 'Borrowed', 
                borrower = '{user}', 
                return_date = current_date + INTERVAL '{days} days'
            WHERE id = '{tool_id}'
        """)
    
    def return_tool(self, tool_id):
        # UPDATED: Reset return_date
        self.con.execute(f"UPDATE tools SET status='Available', borrower=NULL, return_date=NULL WHERE id='{tool_id}'")

    def get_family_members(self):
        return self.con.execute("SELECT * FROM family ORDER BY name").df()

    def get_user_by_email(self, email):
        result = self.con.execute("SELECT name, role, household FROM family WHERE email = ?", [email]).fetchone()
        if result:
            return {"name": result[0], "role": result[1], "household": result[2]}
        return None

    def seed_data(self, tools_list, family_list):
        pass # Handled by admin_upload.py