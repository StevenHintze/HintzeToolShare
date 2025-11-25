import google.generativeai as genai
import streamlit as st
import json

def get_smart_recommendations(user_query, inventory_df, user_household):
    """
    Analyzes project and returns structured JSON with 3 categories of tools.
    """
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    except Exception as e:
        return None

    # 1. Prepare Inventory Context
    inventory_list = []
    for index, row in inventory_df.iterrows():
        # We need to know WHO has it if it's borrowed
        status_detail = "Available"
        if row['status'] == 'Borrowed':
            status_detail = f"Borrowed by {row['borrower']}"

        inventory_list.append({
            "id": row['id'],
            "name": row['name'],
            "brand": row['brand'],
            "household": row['household'],
            "status": status_detail, # Critical for the "Alert" logic
            "specs": row['capabilities'],
            "safety": row['safety_rating']
        })
    
    inventory_json = json.dumps(inventory_list)

    # 2. The "Context-Aware" Prompt
    prompt = f"""
    You are the Hintze Family Tool Manager.
    
    USER PROJECT: "{user_query}"
    USER'S HOUSEHOLD: "{user_household}"
    
    YOUR TASK:
    Identify the best tools for the job and categorize them based on the user's location.
    
    CATEGORIES:
    1. "locate": Tools the user OWNS (same household) that are Available.
    2. "track_down": Tools the user OWNS but are currently BORROWED by someone else.
    3. "borrow": Tools the user DOES NOT OWN (different household) that they need to borrow.
    
    OPTIMIZATION RULES:
    - Prefer "locate" tools first (why drive if you have it?).
    - If a tool is in "track_down", do NOT tell them to borrow another one unless necessary. Just inform them who has theirs.
    - For "borrow" items, group by household to minimize driving.
    
    INVENTORY JSON:
    {inventory_json}
    
    OUTPUT FORMAT (JSON ONLY):
    {{
        "rationale": "Brief strategy explanation.",
        "locate_list": [ {{"tool_name": "...", "location": "Bin/Shelf..."}} ],
        "track_down_list": [ {{"tool_name": "...", "held_by": "Name of borrower"}} ],
        "borrow_list": [
            {{
                "tool_id": "ID",
                "name": "...",
                "household": "...",
                "reason": "..."
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

def ai_parse_tool(raw_text):
    """
    Takes raw text (e.g. Amazon title) and returns a JSON dictionary.
    """
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # Note: In f-strings, we must use double braces {{ }} for literal JSON
        prompt = f"""
        You are an inventory assistant. Analyze this tool description and extract structured data.
        
        INPUT TEXT: "{raw_text}"
        
        REQUIREMENTS:
        1. Name: Clean, concise tool name (e.g., "Milwaukee M18 Fuel Driver").
        2. Brand: The manufacturer (e.g. DeWalt). If unknown, use "".
        3. Model: The specific model number (e.g. DCF887). If none, use "".
        4. Power: "Corded", "Battery", "Gas", or "Manual".
        5. Safety: Strictly choose one: "Open", "Supervised", or "Adult Only".
        6. Capabilities: A clean string of 3-5 comma-separated keywords.
        
        OUTPUT FORMAT:
        Return ONLY valid JSON. No markdown.
        {{
            "name": "...",
            "brand": "...",
            "model_no": "...",
            "power_source": "...",
            "safety": "...",
            "capabilities": "..."
        }}
        """
        
        response = model.generate_content(prompt)
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_text)
        
    except Exception as e:
        return None

def ai_filter_inventory(user_query, inventory_df):
    """
    Filters the inventory based on natural language (e.g. "automotive tools").
    Returns a list of matching Tool IDs.
    """
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    except:
        return []

    # Simplify context to save tokens
    context = ""
    for index, row in inventory_df.iterrows():
        status_str = f"Borrowed by {row['borrower']}" if row['status'] == 'Borrowed' else "Available"
        context += f"ID: {row['id']} | Name: {row['name']} | Cap: {row['capabilities']} | Status: {status_str}\n"

    prompt = f"""
    You are an Inventory Search Engine.
    
    QUERY: "{user_query}"
    
    INVENTORY:
    {context}
    
    TASK:
    Return a JSON list of Tool IDs that match the query.
    - If user asks "What has Shawn borrowed?", find items with Status "Borrowed by Shawn".
    - If user asks "Automotive", find items with capabilities related to cars/trucks.
    - If user asks "Battery powered", find items with power_source='Battery'.
    
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