import google.generativeai as genai
import streamlit as st
import json

def configure_genai():
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        return True
    except Exception as e:
        st.error(f"Config Error: {e}")
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
        
        # Helper to safely get native types (int64 -> int, bool_ -> bool)
        def safe_get(key):
            val = row.get(key)
            if hasattr(val, 'item'): return val.item() # Numpy types
            return val

        inventory_list.append({
            "id": safe_get('id'), 
            "name": safe_get('name'), 
            "brand": safe_get('brand'),
            "household": safe_get('household'), 
            "status": status, 
            "safety": safe_get('safety_rating'),
            "is_stationary": safe_get('is_stationary')
        })
    
    prompt_base = f"""
    You are the Tool Manager.
    PROJECT: "{user_query}" (User Loc: {user_household})
    INVENTORY: {json.dumps(inventory_list)}
    TASK: Categorize tools into:
    1. "locate" (User owns, available)
    2. "track_down" (User owns, borrowed)
    3. "borrow" (User needs from others)
    4. "missing" (Not in inventory)
    """
    
    json_structure = """
    OUTPUT JSON structure:
    {
        "locate_list": [{"tool_name": "Exact Name", "location": "Bin/Shelf"}],
        "track_down_list": [{"tool_name": "Exact Name", "held_by": "Borrower Name"}],
        "borrow_list": [{"name": "Tool Name", "household": "Owner House", "tool_id": "ID", "reason": "Why needed"}],
        "missing_list": [{"tool_name": "Tool Name", "importance": "High/Med/Low", "advice": "Buy/Rent", "reason": "Explanation of why this tool is needed"}]
    }
    """
    
    prompt = prompt_base + json_structure
    try:
        model = genai.GenerativeModel('gemini-2.5-flash') 
        response = model.generate_content(prompt)
        clean = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean)
    except Exception as e:
        st.error(f"AI Error: {e}")
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

# 7. LENDING ASSISTANT (Tab 5 Lending Center)
def parse_lending_request(user_query, my_tools_df, family_list):
    if not configure_genai(): return None
    
    # Context: User's owned tools
    tool_context = ""
    for index, row in my_tools_df.iterrows():
        tool_context += f"- ID: {row['id']} | Name: {row['name']} | Brand: {row['brand']} | Model: {row['model_no']}\n"
    
    # Context: Family Members
    # family_context = ", ".join([f"{f['name']} ({f['role']})" for f in family_list]) 
    # Use simple list for unambiguous name matching
    family_names = [f['name'] for f in family_list]
    
    prompt_base = f"""
    You are a Lending Assistant.
    USER REQUEST: "{user_query}"
    
    MY TOOLS:
    {tool_context}
    
    FAMILY MEMBERS LIST: {json.dumps(family_names)}
    
    TASK:
    1. Identify matching tools from "MY TOOLS". 
       - If ambiguous (e.g., user says "drill" and you have "Makita Drill" and "Corded Drill"), INCLUDE BOTH.
       - Return a list of POTENTIAL matches.
    2. Identify the borrower from "FAMILY MEMBERS".
       - CRITICAL: You MUST use the EXACT "name" from the "FAMILY MEMBERS" list.
       - If no match found, use null or empty string.
    3. Check override authorization.
    """
    
    json_schema = """
    OUTPUT JSON:
    {
      "candidates": [
          {"id": "ID", "name": "Name", "confidence": "high/medium"}
      ],
      "borrower_name": "Name",
      "force_override": true/false
    }
    """
    
    prompt = prompt_base + json_schema
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)
        clean = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean)
    except:
        return None