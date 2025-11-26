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
        tool_context += f"- {row['name']} [{details}] (Safety: {row['safety_rating']}, Caps: {row['capabilities']})\n"

    prompt = f"""
    You are the "Hintze Family Tool Manager." 
    
    YOUR GOAL:
    Analyze the user's project and recommend the best tools from the AVAILABLE INVENTORY below.
    
    RULES:
    1. ONLY recommend tools listed in the INVENTORY.
    2. Be practical and concise.
    3. If a tool is "Adult Only" and the project seems risky, add a brief safety reminder.
    
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
    """
    Analyzes project and returns structured JSON with 4 categories of tools.
    """
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    except Exception as e:
        return None

    # 1. Prepare Inventory Context
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

    # 2. The Updated Prompt
    prompt = f"""
    You are the Hintze Family Tool Manager.
    USER PROJECT: "{user_query}"
    USER'S HOUSEHOLD: "{user_household}"
    
    YOUR TASK:
    Analyze the project. List the tools needed. Cross-reference with the INVENTORY JSON.
    
    CATEGORIES:
    1. "locate": Tools the user OWNS (same household).
    2. "track_down": Tools the user OWNS but are currently BORROWED.
    3. "borrow": Tools the user DOES NOT OWN but exist in the inventory.
    4. "missing": Essential tools for this job that are NOT in the inventory.
    
    STRICT RULES:
    - Do NOT invent tools. If it's not in the JSON, it goes in "missing".
    - If a critical tool is "missing", advise if the job is safe to proceed without it or if they need to buy/rent it.
    
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
                "tool_name": "Generic Name (e.g. Floor Jack)",
                "importance": "Critical/Optional",
                "advice": "Buy this or use the bottle jack from your truck"
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
    """
    Filters the inventory based on natural language. Returns list of Tool IDs.
    """
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    except:
        return []

    context = ""
    for index, row in inventory_df.iterrows():
        status_str = f"Borrowed by {row['borrower']}" if row['status'] == 'Borrowed' else "Available"
        context += f"ID: {row['id']} | Name: {row['name']} | Brand: {row['brand']} | Cap: {row['capabilities']} | Status: {status_str}\n"

    prompt = f"""
    You are an Inventory Search Engine.
    QUERY: "{user_query}"
    INVENTORY:
    {context}
    
    TASK:
    Return a JSON list of Tool IDs that match the query.
    - If user asks "What has Shawn borrowed?", find items with Status "Borrowed by Shawn".
    - If user asks "Automotive", find items with capabilities related to cars/trucks.
    
    OUTPUT JSON:
    {{ "match_ids": ["ID1", "ID2"] }}
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
        
        prompt = f"""
        You are an inventory assistant. Analyze this tool description and extract structured data.
        INPUT TEXT: "{raw_text}"
        REQUIREMENTS:
        1. Name: Clean, concise tool name.
        2. Brand: The manufacturer.
        3. Model: The specific model number.
        4. Power: Choose one: "Manual", "Corded", "Battery", "Gas", "Pneumatic", "Hydraulic".
        5. Safety: "Open", "Supervised", or "Adult Only".
        6. Capabilities: A clean string of 3-5 comma-separated keywords.
        7. Stationary: Boolean (true/false). True if the tool is too large/heavy to move easily (e.g. 60gal compressor, car lift, cabinet saw). False for portable tools.

        OUTPUT FORMAT:
        Return ONLY valid JSON.
        {{
            "name": "...",
            "brand": "...",
            "model_no": "...",
            "power_source": "...",
            "safety": "...",
            "capabilities": "..."
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
        
        # Mini-Context
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