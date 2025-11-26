import duckdb
import streamlit as st
import pandas as pd
import uuid
import json
import datetime

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
        # 1. Tools Table
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
                is_stationary BOOLEAN,
                status VARCHAR, 
                borrower VARCHAR,
                return_date TIMESTAMP,
                capabilities VARCHAR, 
                safety_rating VARCHAR
            )
        """)
        
        # 2. Family Table
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS family (
                name VARCHAR,
                role VARCHAR,
                household VARCHAR,
                email VARCHAR PRIMARY KEY
            )
        """)

        # 3. NEW: History Table (The Time Machine)
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS tool_history (
                history_id VARCHAR,
                tool_id VARCHAR,
                changed_by VARCHAR,
                change_date TIMESTAMP,
                previous_state JSON
            )
        """)

    # --- Read Methods ---
    def get_available_tools(self):
        return self.con.execute("SELECT * FROM tools WHERE status = 'Available'").df()
    
    def get_borrowed_tools(self):
        return self.con.execute("SELECT * FROM tools WHERE status = 'Borrowed'").df()
        
    def get_my_tools(self, owner_name):
        return self.con.execute("SELECT * FROM tools WHERE owner = ?", [owner_name]).df()

    def get_tool_history(self, tool_id):
        # Fetch history for a specific tool
        return self.con.execute("""
            SELECT changed_by, change_date, previous_state 
            FROM tool_history 
            WHERE tool_id = ? 
            ORDER BY change_date DESC
        """, [tool_id]).df()

    # --- Write Methods (With History) ---
    def _archive_tool(self, tool_id, user_name):
        """Saves current state to history table before a change."""
        current = self.con.execute("SELECT * FROM tools WHERE id = ?", [tool_id]).df()
        if not current.empty:
            # Convert row to JSON. Handle Timestamp conversion to string for JSON serialization
            record = current.iloc[0].to_dict()
            # Helper to serialize datetimes
            def default(o):
                if isinstance(o, (datetime.date, datetime.datetime)):
                    return o.isoformat()
            
            json_state = json.dumps(record, default=default)
            hist_id = str(uuid.uuid4())
            
            self.con.execute("""
                INSERT INTO tool_history VALUES (?, ?, ?, current_timestamp, ?)
            """, [hist_id, tool_id, user_name, json_state])

    def update_tool_location(self, tool_id, new_bin, new_household, user_name):
        self._archive_tool(tool_id, user_name)
        self.con.execute("""
            UPDATE tools SET bin_location = ?, household = ? WHERE id = ?
        """, [new_bin, new_household, tool_id])

    def batch_update_tools(self, df, user_name):
        """Updates multiple tools from the Data Editor."""
        for index, row in df.iterrows():
            self._archive_tool(row['id'], user_name)
            self.con.execute("""
                UPDATE tools 
                SET name=?, brand=?, model_no=?, household=?, bin_location=?, capabilities=?, safety_rating=?
                WHERE id=?
            """, [row['name'], row['brand'], row['model_no'], row['household'], row['bin_location'], row['capabilities'], row['safety_rating'], row['id']])

    # --- Standard Methods ---
    def borrow_tool(self, tool_id, user, days):
        self.con.execute(f"UPDATE tools SET status='Borrowed', borrower='{user}', return_date=current_date + INTERVAL '{days} days' WHERE id='{tool_id}'")
    
    def return_tool(self, tool_id):
        self.con.execute(f"UPDATE tools SET status='Available', borrower=NULL, return_date=NULL WHERE id='{tool_id}'")

    def get_family_members(self):
        return self.con.execute("SELECT * FROM family ORDER BY name").df()

    def get_user_by_email(self, email):
        result = self.con.execute("SELECT name, role, household FROM family WHERE email = ?", [email]).fetchone()
        if result:
            return {"name": result[0], "role": result[1], "household": result[2]}
        return None

    def seed_data(self, tools_list, family_list):
        pass