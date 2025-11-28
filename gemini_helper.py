import google.generativeai as genai
import streamlit as st
import json

def configure_genai():
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        return True
    except:
        return False

# 1. SHOP TEACHER (Tab 3 Legacy / General Advice)
def get_ai_advice(user_query, available_tools_df):
    if not configure_genai(): return "⚠️ Error: API Key missing."
    
    tool_context = ""
    for index, row in available_tools_df.iterrows():
        brand = row.get('brand', '')
        model = row.get('model_no', '')
        details = f"{brand} {model}".strip()
        stat_note = "[STATIONARY]" if row.get('is_stationary') else ""
        tool_context += f"- {row['name']} [{details}] {stat_note} (Safety: {row['safety_rating']}, Caps: {row['capabilities']})\n"

    prompt = f"""
    You are the "Hintze Family Tool Manager." 
    Analyze the user's project and recommend tools from the INVENTORY.
    INVENTORY: {tool_context}
    USER QUESTION: "{user_query}"
    """
    try:
        model = genai.GenerativeModel('gemini-2.5-flash') 
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"⚠️ AI Error: {str(e)}"

# 2. SMART PARSER (Tab 4 Auto-Fill)
def ai_parse_tool(raw_text):
    if not configure_genai(): return None
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        prompt = f"""
        Analyze tool description. 
        INPUT: "{raw_text}"
        REQUIREMENTS:
        1. Name: Title Case (e.g. "DeWalt Impact Driver").
        2. Brand: Manufacturer.
        3. Model: Model number.
        4. Power: "Corded", "Battery", "Gas", "Pneumatic", "Hydraulic", or "Manual".
        5. Safety: "Open", "Supervised", or "Adult Only".
        6. Capabilities: 3-5 keywords.
        7. Stationary: Boolean (true/false).
        
        OUTPUT JSON: {{ "name": "...", "brand": "...", "model_no": "...", "power_source": "...", "safety": "...", "capabilities": "...", "is_stationary": true/false }}
        """
        response = model.generate_content(prompt)
        clean = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean)
    except:
        return None

# 3. PROJECT PLANNER (Tab 3 Smart Cart)
def get_smart_recommendations(user_query, available_tools_df, user_household):
    if not configure_genai(): return None
    
    inventory_list = []
    for index, row in available_tools_df.iterrows():
        status = f"Borrowed by {row.get('borrower')}" if row.get('status') == 'Borrowed' else "Available"
        inventory_list.append({
            "id": row.get('id'), "name": row.get('name'), "brand": row.get('brand'),
            "household": row.get('household'), "status": status, "safety": row.get('safety_rating'),
            "is_stationary": row.get('is_stationary')
        })
    
    prompt = f"""
    You are the Tool Manager.
    PROJECT: "{user_query}" (User Loc: {user_household})
    INVENTORY: {json.dumps(inventory_list)}
    TASK: Categorize tools into:
    1. "locate" (User owns, available)
    2. "track_down" (User owns, borrowed)
    3. "borrow" (User needs from others)
    4. "missing" (Not in inventory)
    OUTPUT JSON: {{ "locate_list": [], "track_down_list": [], "borrow_list": [], "missing_list": [] }}
    """
    try:
        model = genai.GenerativeModel('gemini-2.5-flash') 
        response = model.generate_content(prompt)
        clean = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean)
    except:
        return None

# 4. INVENTORY FILTER (Tab 1 Search)
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
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)
        clean = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean).get("match_ids", [])
    except:
        return []

# 5. SMART MOVER (Tab 4 Quick Actions)
def parse_location_update(user_query, user_tools_df):
    if not configure_genai(): return None
    tool_list_str = ""
    for index, row in user_tools_df.iterrows():
        tool_list_str += f"- ID: {row['id']} | Name: {row['name']} | Brand: {row['brand']}\n"
        
    prompt = f"""
    Inventory Manager.
    REQUEST: "{user_query}"
    TOOLS: {tool_list_str}
    TASK: Identify action (MOVE or RETIRE) for specific IDs.
    OUTPUT JSON: {{ "updates": [ {{ "tool_id": "...", "action": "MOVE/RETIRE", "new_bin": "...", "reason": "..." }} ] }}
    """
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)
        clean = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean)
    except:
        return None

# 6. DUPLICATE CHECKER (Tab 4 Safety)
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
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)
        clean = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean)
    except:
        return None