import google.generativeai as genai
import streamlit as st
import json

def get_smart_recommendations(user_query, available_tools_df):
    """
    Analyzes project and returns structured JSON with specific tool IDs to borrow.
    """
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    except Exception as e:
        return None

    # 1. Prepare Inventory Context
    inventory_list = []
    for index, row in available_tools_df.iterrows():
        # Use .get() for safety in case a column is empty or missing
        inventory_list.append({
            "id": row.get('id', 'Unknown'),
            "name": row.get('name', 'Unknown Tool'),
            "brand": row.get('brand', ''),
            "model": row.get('model_no', ''),
            "household": row.get('household', 'Unknown'),
            "specs": row.get('capabilities', ''),
            "safety": row.get('safety_rating', 'Open')
        })
    
    inventory_json = json.dumps(inventory_list)

    # 2. The "Logistics Expert" Prompt
    prompt = f"""
    You are the Hintze Family Tool Manager and Logistics Expert.
    
    USER PROJECT: "{user_query}"
    
    YOUR TASK:
    1. Select the specific tools needed from the INVENTORY below.
    2. OPTIMIZATION RULES:
       - If multiple similar tools exist (e.g. 3 drills), pick the highest quality/most capable one.
       - If tools are equal quality, prioritize picking tools from the SAME HOUSEHOLD to save the user driving time.
       - Do not recommend tools we don't have.
    
    INVENTORY JSON:
    {inventory_json}
    
    OUTPUT FORMAT:
    Return ONLY valid JSON (no markdown). Structure:
    {{
        "rationale": "Brief explanation of why you chose these tools and this household strategy.",
        "recommended_tools": [
            {{
                "tool_id": "Exact ID from inventory",
                "reason": "Why this specific tool?"
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
        st.error(f"AI Logic Error: {e}")
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