import duckdb
import streamlit as st
import pandas as pd
import uuid
import json
import datetime
import requests

# --- CACHED HELPERS (Outside Class to avoid hashing 'self') ---
# These functions handle the actual data fetching. 
# The '_con' argument tells Streamlit "Don't try to hash the database connection".

@st.cache_data(ttl=300) # Cache for 5 minutes
def _fetch_family_members(_con):
    return _con.execute("SELECT * FROM family ORDER BY name").df()

@st.cache_data(ttl=60) # Cache for 60 seconds
def _fetch_all_tools(_con):
    return _con.execute("SELECT * FROM tools").df()

@st.cache_data(ttl=60)
def _fetch_my_tools(_con, owner_name):
    return _con.execute("SELECT * FROM tools WHERE owner = ?", [owner_name]).df()

@st.cache_data(ttl=60)
def _fetch_tool_history(_con, tool_id):
    return _con.execute("""
        SELECT changed_by, change_date, previous_state 
        FROM tool_history 
        WHERE tool_id = ? 
        ORDER BY change_date DESC
    """, [tool_id]).df()

class DataManager:
    def __init__(self):
        token = None
        try:
            token = st.secrets.get("MOTHERDUCK_TOKEN")
        except FileNotFoundError:
            pass 
        
        if token:
            self.con_str = f'md:?motherduck_token={token}'
        else:
            self.con_str = 'inventory.db' 
        
        try:
            self.con = duckdb.connect(self.con_str)
            self.con.execute("SELECT 1")
        except Exception as e:
            st.error(f"❌ DB Connection Failed: {e}")
            st.stop()

        self.con.execute("CREATE DATABASE IF NOT EXISTS hintze_inventory")
        self.con.execute("USE hintze_inventory")
        self._init_schema()

    def _init_schema(self):
        # (Schema definitions same as before...)
        self.con.execute("CREATE TABLE IF NOT EXISTS tools (id VARCHAR PRIMARY KEY, name VARCHAR, brand VARCHAR, model_no VARCHAR, power_source VARCHAR, owner VARCHAR, household VARCHAR, bin_location VARCHAR, is_stationary BOOLEAN, status VARCHAR, borrower VARCHAR, return_date TIMESTAMP, capabilities VARCHAR, safety_rating VARCHAR)")
        self.con.execute("CREATE TABLE IF NOT EXISTS family (name VARCHAR, role VARCHAR, household VARCHAR, email VARCHAR PRIMARY KEY)")
        self.con.execute("CREATE TABLE IF NOT EXISTS tool_history (history_id VARCHAR, tool_id VARCHAR, changed_by VARCHAR, change_date TIMESTAMP, previous_state JSON)")
        self.con.execute("CREATE TABLE IF NOT EXISTS sessions (token VARCHAR PRIMARY KEY, email VARCHAR, created_at TIMESTAMP, expires_at TIMESTAMP)")
        self.con.execute("CREATE TABLE IF NOT EXISTS audit_logs (log_id VARCHAR PRIMARY KEY, timestamp TIMESTAMP, event_type VARCHAR, user_email VARCHAR, details VARCHAR)")

    # --- Read Methods (Now using Cache) ---
    def get_family_members(self):
        return _fetch_family_members(self.con)

    def get_all_tools(self):
        # New method to replace raw SQL in app.py
        return _fetch_all_tools(self.con)
        
    def get_available_tools(self):
        # We can filter the cached "all tools" instead of querying DB again
        df = _fetch_all_tools(self.con)
        return df[df['status'] == 'Available']
    
    def get_borrowed_tools(self):
        df = _fetch_all_tools(self.con)
        return df[df['status'] == 'Borrowed']
        
    def get_my_tools(self, owner_name):
        return _fetch_my_tools(self.con, owner_name)

    def get_tool_history(self, tool_id):
        return _fetch_tool_history(self.con, tool_id)

    # --- Write Methods (Clear Cache on Update) ---
    def clear_cache(self):
        """Forces a reload of data."""
        st.cache_data.clear()

    def _archive_tool(self, tool_id, user_name):
        current = self.con.execute("SELECT * FROM tools WHERE id = ?", [tool_id]).df()
        if not current.empty:
            record = current.iloc[0].to_dict()
            def default(o):
                if isinstance(o, (datetime.date, datetime.datetime)): return o.isoformat()
            json_state = json.dumps(record, default=default)
            hist_id = str(uuid.uuid4())
            self.con.execute("INSERT INTO tool_history VALUES (?, ?, ?, current_timestamp, ?)", [hist_id, tool_id, user_name, json_state])

    def update_tool_location(self, tool_id, new_bin, new_household, user_name):
        self._archive_tool(tool_id, user_name)
        self.con.execute("UPDATE tools SET bin_location = ?, household = ? WHERE id = ?", [new_bin, new_household, tool_id])
        self.clear_cache() # <--- Clear cache so UI updates

    def retire_tool(self, tool_id, reason, user_name):
        self._archive_tool(tool_id, user_name)
        self.con.execute("UPDATE tools SET status = 'Retired', bin_location = ? WHERE id = ?", [f"Retired: {reason}", tool_id])
        self.clear_cache()

    def batch_update_tools(self, df, user_name):
        for index, row in df.iterrows():
            self._archive_tool(row['id'], user_name)
            self.con.execute("""
                UPDATE tools 
                SET name=?, brand=?, model_no=?, household=?, bin_location=?, is_stationary=?, capabilities=?, safety_rating=?
                WHERE id=?
            """, [row['name'], row['brand'], row['model_no'], row['household'], row['bin_location'], row['is_stationary'], row['capabilities'], row['safety_rating'], row['id']])
        self.clear_cache()

    def purge_old_history(self, days=30):
        count = self.con.execute(f"SELECT count(*) FROM tool_history WHERE change_date < current_timestamp - INTERVAL '{days} days'").fetchone()[0]
        if count > 0:
            self.con.execute(f"DELETE FROM tool_history WHERE change_date < current_timestamp - INTERVAL '{days} days'")
        return count

    # --- Security Logging ---
    def log_event(self, event_type, email, details):
        log_id = str(uuid.uuid4())
        self.con.execute("INSERT INTO audit_logs VALUES (?, current_timestamp, ?, ?, ?)", [log_id, event_type, email, details])
        if event_type in ["FAILED_LOGIN", "ADMIN_UPDATE"] or "RETIRE" in details:
            self._send_discord_alert(event_type, email, details)

    def _send_discord_alert(self, event_type, email, details):
        webhook_url = st.secrets.get("DISCORD_WEBHOOK")
        if not webhook_url: return
        data = {"content": f"🚨 **{event_type}**", "embeds": [{"description": f"**User:** {email}\n**Details:** {details}"}]}
        try: requests.post(webhook_url, json=data)
        except: pass 

    # --- Standard Methods ---
    def borrow_tool(self, tool_id, user, days):
        self.con.execute(f"UPDATE tools SET status='Borrowed', borrower='{user}', return_date=current_date + INTERVAL '{days} days' WHERE id='{tool_id}'")
        self.clear_cache() # Update UI immediately
    
    def return_tool(self, tool_id):
        self.con.execute(f"UPDATE tools SET status='Available', borrower=NULL, return_date=NULL WHERE id='{tool_id}'")
        self.clear_cache()

    def extend_loan(self, tool_id, extra_days):
        self.con.execute(f"UPDATE tools SET return_date = return_date + INTERVAL '{extra_days} days' WHERE id='{tool_id}'")
        self.clear_cache()

    def get_user_by_email(self, email):
        result = self.con.execute("SELECT name, role, household FROM family WHERE email = ?", [email]).fetchone()
        if result: return {"name": result[0], "role": result[1], "household": result[2]}
        return None

    # --- Session Security ---
    def create_session(self, email):
        token = str(uuid.uuid4())
        self.con.execute(f"INSERT INTO sessions VALUES ('{token}', '{email}', current_timestamp, current_timestamp + INTERVAL '7 days')")
        return token

    def get_user_from_session(self, token):
        result = self.con.execute("SELECT email FROM sessions WHERE token = ? AND expires_at > current_timestamp", [token]).fetchone()
        if result: return self.get_user_by_email(result[0])
        return None

    def revoke_session(self, token):
        self.con.execute("DELETE FROM sessions WHERE token = ?", [token])
    
    def clean_old_sessions(self):
        self.con.execute("DELETE FROM sessions WHERE expires_at < current_timestamp")

    def seed_data(self, tools_list, family_list):
        pass