import vertexai
from vertexai.generative_models import GenerativeModel
import streamlit as st
import json
import time

def configure_genai():
    try:
        # Vertex AI Initialization
        project_id = st.secrets.get("GCP_PROJECT")
        location = st.secrets.get("GCP_LOCATION", "us-west4") # Default to Las Vegas (closest to Phoenix)
        
        if not project_id:
            st.error("⚠️ Config Error: GCP_PROJECT not found in secrets.")
            return False
            
        vertexai.init(project=project_id, location=location)
        return True
    except Exception as e:
        st.error(f"Config Error: {e}")
        return False

def handle_ai_error(e):
    if "429" in str(e) or "429" in str(e.args):
        st.warning("🚦 **AI Traffic Limit:** System busy. Please wait 30s and try again.")
        return None
    st.error(f"⚠️ AI Error: {str(e)}")
    return None

# 1. SHOP TEACHER
def get_ai_advice(user_query, available_tools_df):
    if not configure_genai(): return "⚠️ Configuration Missing"
    
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
        model = GenerativeModel('gemini-2.5-flash') 
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        if "429" in str(e): return "🚦 System busy (Rate Limit). Please wait 30s."
        return f"⚠️ Error: {str(e)}"

# 2. SMART PARSER
def ai_parse_tool(raw_text):
    if not configure_genai(): return None
    try:
        model = GenerativeModel('gemini-2.5-flash')
        prompt = f"""
        Analyze tool description. INPUT: "{raw_text}"
        REQUIREMENTS: Name (Title Case), Brand, Model, Power, Safety, Capabilities, Stationary.
        OUTPUT JSON: {{ "name": "...", "brand": "...", "model_no": "...", "power_source": "...", "safety": "...", "capabilities": "...", "is_stationary": true/false }}
        """
        response = model.generate_content(prompt)
        clean = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean)
    except Exception as e:
        return handle_ai_error(e)

# 3. PROJECT PLANNER (Fixed Logic)
def get_smart_recommendations(user_query, available_tools_df, user_household, user_name):
    if not configure_genai(): return None
    
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
            "is_mine": is_mine, # <--- NEW FLAG
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
    try:
        model = GenerativeModel('gemini-2.5-flash') 
        response = model.generate_content(prompt)
        text = response.text
        start = text.find('{')
        end = text.rfind('}') + 1
        if start != -1 and end != -1:
            return json.loads(text[start:end])
        else:
            clean = text.replace("```json", "").replace("```", "").strip()
            return json.loads(clean)
    except Exception as e:
        return handle_ai_error(e)

# 4. INVENTORY FILTER
def ai_filter_inventory(user_query, inventory_df):
    if not configure_genai(): return []
    context = ""
    for index, row in inventory_df.iterrows():
        context += f"ID: {row['id']} | Name: {row['name']} | Brand: {row['brand']} | Cap: {row['capabilities']}\n"
    
    prompt = f"""
    Search Engine. Query: "{user_query}"
    Inventory: {context}
    Return JSON list of matching IDs: {{ "match_ids": ["ID1", "ID2"] }}
    """
    try:
        model = GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)
        clean = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean).get("match_ids", [])
    except:
        return []

# 5. SMART MOVER
def parse_location_update(user_query, user_tools_df):
    if not configure_genai(): return None
    tool_list_str = ""
    for index, row in user_tools_df.iterrows():
        tool_list_str += f"- ID: {row['id']} | Name: {row['name']} | Brand: {row['brand']}\n"
        
    prompt = f"""
    Inventory Manager. REQUEST: "{user_query}"
    TOOLS: {tool_list_str}
    TASK: Identify action (MOVE or RETIRE).
    OUTPUT JSON: {{ "updates": [ {{ "tool_id": "...", "action": "MOVE/RETIRE", "new_bin": "...", "reason": "..." }} ] }}
    """
    try:
        model = GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)
        clean = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean)
    except Exception as e:
        return handle_ai_error(e)

# 6. DUPLICATE CHECKER
def check_duplicate_tool(new_tool_data, inventory_df):
    if not configure_genai(): return None
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
    try:
        model = GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)
        clean = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean)
    except:
        return None

# 7. LENDING ASSISTANT
def parse_lending_request(user_query, my_tools_df, family_list):
    if not configure_genai(): return None
    
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
    try:
        model = GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)
        clean = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean)
    except Exception as e:
        return handle_ai_error(e)
