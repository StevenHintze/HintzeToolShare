import google.generativeai as genai
import streamlit as st
import json
import time

def configure_genai():
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        return True
    except Exception as e:
        st.error(f"Config Error: {e}")
        return False

def handle_ai_error(e):
    if "429" in str(e):
        st.warning("🚦 **AI Traffic Limit:** System busy. Please wait 30s and try again.")
        return None
    st.error(f"⚠️ AI Error: {str(e)}")
    return None

# 1. SHOP TEACHER
def get_ai_advice(user_query, available_tools_df):
    if not configure_genai(): return "⚠️ API Key Missing"
    
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
        model = genai.GenerativeModel('gemini-2.5-flash') 
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        if "429" in str(e): return "🚦 System busy (Rate Limit). Please wait 30s."
        return f"⚠️ Error: {str(e)}"

# 2. SMART PARSER
def ai_parse_tool(raw_text):
    if not configure_genai(): return None
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
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

# 3. PROJECT PLANNER
def get_smart_recommendations(user_query, available_tools_df, user_household, user_name):
    if not configure_genai(): return None
    
    inventory_list = []
    for index, row in available_tools_df.iterrows():
        status = f"Borrowed by {row.get('borrower')}" if row.get('status') == 'Borrowed' else "Available"
        inventory_list.append({
            "id": row.get('id'), "name": row.get('name'), "brand": row.get('brand'),
            "household": row.get('household'), "status": status, 
            "is_stationary": row.get('is_stationary')
        })
    
    prompt = f"""
    Tool Manager. PROJECT: "{user_query}" (User: {user_name}, Loc: {user_household})
    INVENTORY: {json.dumps(inventory_list)}
    TASK: Categorize tools: locate, track_down, borrow, missing.
    OUTPUT JSON: {{ "locate_list": [], "track_down_list": [], "borrow_list": [], "missing_list": [] }}
    """
    try:
        model = genai.GenerativeModel('gemini-2.5-flash') 
        response = model.generate_content(prompt)
        clean = response.text.replace("```json", "").replace("```", "").strip()
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
        model = genai.GenerativeModel('gemini-2.5-flash')
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
        model = genai.GenerativeModel('gemini-2.5-flash')
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
        model = genai.GenerativeModel('gemini-2.5-flash')
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
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)
        clean = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean)
    except Exception as e:
        return handle_ai_error(e)