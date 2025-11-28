import google.generativeai as genai
import streamlit as st
import json

def get_ai_advice(user_query, available_tools_df):
    """
    Sends the user's project query + current inventory to Gemini.
    """
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    except Exception as e:
        return "⚠️ Error: Gemini API Key missing or invalid."

    # Format Inventory
    tool_context = ""
    for index, row in available_tools_df.iterrows():
        brand = row.get('brand', '')
        model = row.get('model_no', '')
        details = f"{brand} {model}".strip()
        stat_note = "[STATIONARY]" if row.get('is_stationary') else ""
        
        tool_context += f"- {row['name']} [{details}] {stat_note} (Safety: {row['safety_rating']}, Caps: {row['capabilities']})\n"

    prompt = f"""
    You are the "Hintze Family Tool Manager." 
    
    YOUR GOAL:
    Analyze the user's project and recommend the best tools.
    
    RULES:
    1. ONLY recommend tools listed in the INVENTORY.
    2. If a tool is marked [STATIONARY], warn the user they must go to the tool's location to use it.
    3. Be practical and concise.
    
    INVENTORY (Currently Available):
    {tool_context}
    
    USER QUESTION:
    "{user_query}"
    """

    try:
        model = genai.GenerativeModel('gemini-2.5-flash') 
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"⚠️ AI Error: {str(e)}"

def get_smart_recommendations(user_query, available_tools_df, user_household):
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    except Exception as e:
        return None

    inventory_list = []
    for index, row in available_tools_df.iterrows():
        status_detail = "Available"
        if row.get('status') == 'Borrowed':
            status_detail = f"Borrowed by {row.get('borrower')}"

        inventory_list.append({
            "id": row.get('id', 'Unknown'),
            "name": row.get('name', 'Unknown'),
            "brand": row.get('brand', ''),
            "household": row.get('household', 'Unknown'),
            "status": status_detail,
            "is_stationary": row.get('is_stationary', False),
            "specs": row.get('capabilities', ''),
            "safety": row.get('safety_rating', 'Open')
        })
    
    inventory_json = json.dumps(inventory_list)

    prompt = f"""
    You are the Hintze Family Tool Manager.
    USER PROJECT: "{user_query}"
    USER'S HOUSEHOLD: "{user_household}"
    
    YOUR TASK:
    Identify the best tools for the job and categorize them.
    
    CATEGORIES:
    1. "locate": Tools the user OWNS (same household).
    2. "track_down": Tools the user OWNS but are currently BORROWED.
    3. "borrow": Tools the user DOES NOT OWN.
    4. "missing": Essential tools NOT in inventory.
    
    INVENTORY JSON:
    {inventory_json}
    
    OUTPUT FORMAT (JSON ONLY):
    {{
        "rationale": "Brief strategy explanation.",
        "locate_list": [ {{"tool_name": "...", "location": "Bin/Shelf..."}} ],
        "track_down_list": [ {{"tool_name": "...", "held_by": "Name"}} ],
        "borrow_list": [
            {{
                "tool_id": "ID",
                "name": "...",
                "household": "...",
                "reason": "..."
            }}
        ],
        "missing_list": [
            {{
                "tool_name": "Name",
                "importance": "Critical/Optional",
                "advice": "..."
            }}
        ]
    }}
    """

    try:
        model = genai.GenerativeModel('gemini-2.5-flash') 
        response = model.generate_content(prompt)
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_text)
    except Exception as e:
        return None

def ai_filter_inventory(user_query, inventory_df):
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    except:
        return []

    context = ""
    for index, row in inventory_df.iterrows():
        context += f"ID: {row['id']} | Name: {row['name']} | Brand: {row['brand']} | Cap: {row['capabilities']}\n"

    prompt = f"""
    You are an Inventory Search Engine.
    QUERY: "{user_query}"
    INVENTORY:
    {context}
    TASK: Return a JSON list of Tool IDs {{ "match_ids": [...] }} that match the query.
    """
    
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)
        clean = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean).get("match_ids", [])
    except:
        return []

def ai_parse_tool(raw_text):
    """
    Takes raw text (e.g. Amazon title) and returns a JSON dictionary.
    """
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # UPDATED: Explicit instruction for Title Case
        prompt = f"""
        You are an inventory assistant. Analyze this tool description.
        INPUT TEXT: "{raw_text}"
        REQUIREMENTS:
        1. Name: Clean, concise tool name. Use Title Case (e.g. "DeWalt Impact Driver"). Do NOT use ALL CAPS or all lowercase.
        2. Brand: The manufacturer.
        3. Model: The specific model number.
        4. Power: "Corded", "Battery", "Gas", "Pneumatic", "Hydraulic", or "Manual".
        5. Safety: "Open", "Supervised", or "Adult Only".
        6. Capabilities: A clean string of 3-5 comma-separated keywords.
        7. Stationary: Boolean (true/false). True if the tool is very large/heavy/mounted.
        
        OUTPUT FORMAT:
        Return ONLY valid JSON.
        {{
            "name": "...",
            "brand": "...",
            "model_no": "...",
            "power_source": "...",
            "safety": "...",
            "capabilities": "...",
            "is_stationary": true/false
        }}
        """
        response = model.generate_content(prompt)
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_text)
    except Exception as e:
        return None

def parse_location_update(user_query, user_tools_df):
    """
    Analyzes user query to Move OR Retire tools.
    """
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        tool_list_str = ""
        for index, row in user_tools_df.iterrows():
            tool_list_str += f"- ID: {row['id']} | Name: {row['name']} | Brand: {row['brand']}\n"
        
        prompt = f"""
        You are an Inventory Manager.
        
        USER REQUEST: "{user_query}"
        USER'S INVENTORY:
        {tool_list_str}
        
        YOUR TASK:
        1. Match tools from the inventory list to the user request.
        2. Determine the ACTION: 'MOVE' or 'RETIRE' (Sold/Broken/Donated/Deleted).
        
        OUTPUT JSON:
        {{
            "updates": [
                {{ 
                    "tool_id": "EXACT_ID", 
                    "action": "MOVE" or "RETIRE",
                    "new_bin": "Location string (if MOVE)", 
                    "new_household": "Household string (if MOVE)",
                    "reason": "Sold/Broken/etc (if RETIRE)"
                }}
            ]
        }}
        """
        response = model.generate_content(prompt)
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_text)
    except:
        return None

def check_duplicate_tool(new_tool_data, inventory_df):
    """
    Compares a potential new tool against the existing database to find duplicates.
    """
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # UPDATED CONTEXT: Now includes Owner and Household so AI doesn't guess
        existing_list = []
        for index, row in inventory_df.iterrows():
            existing_list.append(f"ID: {row['id']} | Name: {row['name']} | Brand: {row['brand']} | Model: {row['model_no']} | Owner: {row['owner']} | House: {row['household']}")
        
        existing_str = "\n".join(existing_list)
        
        new_tool_str = f"{new_tool_data.get('name')} | {new_tool_data.get('brand')} | {new_tool_data.get('model_no')}"
        
        prompt = f"""
        You are a Data Integrity Agent. Check for duplicates.
        
        NEW TOOL CANDIDATE:
        {new_tool_str}
        
        EXISTING HOUSEHOLD INVENTORY:
        {existing_str}
        
        YOUR TASK:
        Does the NEW TOOL look like a duplicate of any item in the EXISTING INVENTORY?
        - Strict Check: Matching Model Number is a definite duplicate.
        - Fuzzy Check: Matching Name + Brand is a likely duplicate.
        
        OUTPUT JSON:
        {{
            "is_duplicate": true/false,
            "match_name": "Name of the existing tool found",
            "match_owner": "Owner name from the list above",
            "match_household": "Household name from the list above",
            "reason": "Why you think it's a match"
        }}
        """
        
        response = model.generate_content(prompt)
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_text)
    except:
        return None