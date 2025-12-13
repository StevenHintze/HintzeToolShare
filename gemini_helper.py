import google.genai as genai
from google.genai import types
import streamlit as st
import json
import time

# Feature Configuration
# Using gemini-2.0-flash as the new standard model
DEFAULT_MODEL = "gemini-2.0-flash" 
CHEAPEST_MODEL = "gemini-2.0-flash-lite"

def get_client():
    """Initializes and returns the Google Gen AI Client using Service Account API Key."""
    try:
        api_key = st.secrets.get("VERTEX_API_KEY")
        project_id = st.secrets.get("GCP_PROJECT")
        location = st.secrets.get("GCP_LOCATION", "us-west4")
        
        if not api_key:
            st.error("⚠️ Server Error: VERTEX_API_KEY not found in secrets.")
            return None
            
        # Initialize Client for Vertex AI with API Key (Project/Location inferred or not needed with Key)
        # Note: 'vertexai=True' enables the Vertex AI backend.
        client = genai.Client(
            vertexai=True,
            api_key=api_key
        )
        return client
    except Exception as e:
        st.error(f"Config Error: {e}")
        return None

def handle_ai_error(e):
    err_str = str(e)
    if "429" in err_str or "Quota exceeded" in err_str:
        st.warning("🚦 **AI Traffic Limit:** System busy. Please wait 30s and try again.")
        return None
    st.error(f"⚠️ AI Error: {err_str}")
    return None

def run_genai_query(prompt, model_name=DEFAULT_MODEL, expected_json=False):
    """Refactored helper to handle client init and generation."""
    client = get_client()
    if not client: return None # Config error already shown

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt
        )
        
        text = response.text
        if expected_json:
            clean = text.replace("```json", "").replace("```", "").strip()
            # Try to catch simple formatting issues
            if "{" in clean:
                return json.loads(clean)
            return {} # Or raise error?
            
        return text
    except Exception as e:
        return handle_ai_error(e)

# 1. Project Tool Manager
def get_ai_advice(user_query, available_tools_df):
    client = get_client()
    if not client: return "⚠️ Configuration Missing"
    
    tool_context = ""
    for index, row in available_tools_df.iterrows():
        details = f"{row.get('brand', '')} {row.get('model_no', '')}".strip()
        stat_note = "[STATIONARY]" if row.get('is_stationary') else ""
        tool_context += f"- {row['name']} [{details}] {stat_note} (Safety: {row['safety_rating']}, Caps: {row['capabilities']})\n"

    prompt = f"""
    You are the "Hintze Family Tool Manager." 
    Analyze the user's project and recommend tools from the INVENTORY.
    INVENTORY: {tool_context}
    USER QUESTION: "{user_query}"
    """
    try:
        response = client.models.generate_content(
            model=DEFAULT_MODEL,
            contents=prompt
        )
        return response.text
    except Exception as e:
        if "429" in str(e): return "🚦 System busy (Rate Limit). Please wait 30s."
        return f"⚠️ Error: {str(e)}"

# 2. SMART PARSER
def ai_parse_tool(raw_text):
    prompt = f"""
    Analyze tool description. INPUT: "{raw_text}"
    REQUIREMENTS: Name (Title Case), Brand, Model, Power, Safety, Capabilities, Stationary.
    OUTPUT JSON: {{ "name": "...", "brand": "...", "model_no": "...", "power_source": "...", "safety": "...", "capabilities": "...", "is_stationary": true/false }}
    """
    return run_genai_query(prompt, expected_json=True)

# 3. PROJECT PLANNER
def get_smart_recommendations(user_query, available_tools_df, user_household, user_name):
    inventory_list = []
    for index, row in available_tools_df.iterrows():
        status = f"Borrowed by {row.get('borrower')}" if row.get('status') == 'Borrowed' else "Available"
        
        def safe_get(key):
            val = row.get(key)
            if hasattr(val, 'item'): return val.item()
            return val

        # Calculate Ownership Explicitly
        owner = safe_get('owner')
        household = safe_get('household')
        is_mine = (owner == user_name) or (household == user_household)

        inventory_list.append({
            "id": safe_get('id'), 
            "name": safe_get('name'), 
            "brand": safe_get('brand'),
            "is_mine": is_mine,
            "location": f"{household} - {safe_get('bin_location')}",
            "status": status, 
            "is_stationary": safe_get('is_stationary')
        })
    
    prompt_base = f"""
    You are the Tool Manager.
    PROJECT: "{user_query}" 
    USER CONTEXT: Name: "{user_name}", Household: "{user_household}"
    INVENTORY: {json.dumps(inventory_list)}
    
    TASK: Categorize tools into lists.
    
    CRITICAL LOGIC RULES:
    1. **CHECK 'is_mine' FIRST**: If the user owns a tool (`is_mine`: true), ALWAYS put it in "locate_list", even if it's not an exact match (e.g., if project needs 'Ladder' and user owns '5ft Step Ladder', use the owned one).
    2. **NO REDUNDANT BORROWING**: Do NOT suggest borrowing a tool if the user already has a functional equivalent in "locate_list".
    3. **STATUS CHECK**: If `is_mine` is true but `status` says "Borrowed by...", put it in "track_down_list".
    4. **MISSING**: Only put tools here if the user owns NOTHING similar.
    """
    
    json_structure = """
    OUTPUT JSON structure:
    {
        "locate_list": [{"tool_name": "Exact Name from Inventory", "location": "Location field from Inventory"}],
        "track_down_list": [{"tool_name": "Exact Name", "held_by": "Borrower Name"}],
        "borrow_list": [{"name": "Tool Name", "household": "Owner House", "tool_id": "ID", "reason": "Why needed"}],
        "missing_list": [{"tool_name": "Tool Name", "importance": "High/Med/Low", "advice": "Buy/Rent", "reason": "Explanation of why this is needed"}]
    }
    """
    
    prompt = prompt_base + json_structure
    
    # Custom logic here as in original: catch structure
    res = run_genai_query(prompt, expected_json=False) # Get text first
    if not res: return None
    if isinstance(res, dict): return res # Should not happen if False above
    
    try:
        start = res.find('{')
        end = res.rfind('}') + 1
        if start != -1 and end != -1:
            return json.loads(res[start:end])
        else:
            clean = res.replace("```json", "").replace("```", "").strip()
            return json.loads(clean)
    except:
        return None

# 4. INVENTORY FILTER
def ai_filter_inventory(user_query, inventory_df):
    context = ""
    for index, row in inventory_df.iterrows():
        context += f"ID: {row['id']} | Name: {row['name']} | Brand: {row['brand']} | Cap: {row['capabilities']}\n"
    
    prompt = f"""
    Search Engine. Query: "{user_query}"
    Inventory: {context}
    return JSON list of matching IDs: {{ "match_ids": ["ID1", "ID2"] }}
    """
    res = run_genai_query(prompt, model_name=CHEAPEST_MODEL, expected_json=True)
    if res and isinstance(res, dict):
        return res.get("match_ids", [])
    return []

# 5. SMART MOVER
def parse_location_update(user_query, user_tools_df):
    tool_list_str = ""
    for index, row in user_tools_df.iterrows():
        tool_list_str += f"- ID: {row['id']} | Name: {row['name']} | Brand: {row['brand']}\n"
        
    prompt = f"""
    Inventory Manager. REQUEST: "{user_query}"
    TOOLS: {tool_list_str}
    TASK: Identify action (MOVE or RETIRE).
    OUTPUT JSON: {{ "updates": [ {{ "tool_id": "...", "action": "MOVE/RETIRE", "new_bin": "...", "reason": "..." }} ] }}
    """
    return run_genai_query(prompt, expected_json=True)

# 6. DUPLICATE CHECKER
def check_duplicate_tool(new_tool_data, inventory_df):
    existing_list = []
    for index, row in inventory_df.iterrows():
        existing_list.append(f"Name: {row['name']} | Brand: {row['brand']} | Model: {row['model_no']} | Owner: {row['owner']}")
    
    new_str = f"{new_tool_data.get('name')} {new_tool_data.get('brand')} {new_tool_data.get('model_no')}"
    
    prompt = f"""
    Check for duplicates.
    NEW: {new_str}
    EXISTING: {json.dumps(existing_list)}
    OUTPUT JSON: {{ "is_duplicate": true/false, "match_name": "...", "match_owner": "..." }}
    """
    return run_genai_query(prompt, expected_json=True)

# 7. LENDING ASSISTANT
def parse_lending_request(user_query, my_tools_df, family_list):
    tools_ctx = ""
    for idx, row in my_tools_df.iterrows():
        tools_ctx += f"ID: {row['id']} | Name: {row['name']} | Brand: {row['brand']} | Model: {row['model_no']}\n"
    
    family_names = [f['name'] for f in family_list]
    
    prompt = f"""
    Lending Assistant. QUERY: "{user_query}"
    MY TOOLS: {tools_ctx}
    FAMILY: {json.dumps(family_names)}
    
    OUTPUT JSON:
    {{
      "candidates": [ {{"id": "ID", "name": "Name", "confidence": "high/medium"}} ],
      "borrower_name": "Name",
      "force_override": true/false
    }}
    """
    return run_genai_query(prompt, expected_json=True)

# 8. INCINERATOR AID
def ai_find_tools_for_deletion(user_query, tools_df):
    tools_ctx = ""
    for idx, row in tools_df.iterrows():
        tools_ctx += f"ID: {row['id']} | Name: {row['name']} | Owner: {row['owner']} | House: {row['household']} | Status: {row['status']}\n"
    
    prompt = f"""
    Admin Deletion Helper.
    QUERY: "{user_query}"
    INVENTORY: {tools_ctx}
    
    TASK: Return a JSON list of IDs that match the deletion criteria.
    OUTPUT JSON: {{ "delete_ids": ["ID1", "ID2"] }}
    """
    res = run_genai_query(prompt, expected_json=True)
    if res and isinstance(res, dict):
        return res.get("delete_ids", [])
    return []
