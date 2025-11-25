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
        tool_context += f"- {row['name']} (Safety: {row['safety_rating']}, Capabilities: {row['capabilities']})\n"

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
        # Use a widely available model to prevent 404s
        model = genai.GenerativeModel('gemini-2.5-flash') 
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"⚠️ AI Error: {str(e)}"

def ai_parse_tool(raw_text):
    """
    Takes raw text (e.g. Amazon title) and returns a JSON dictionary 
    with {name, safety, capabilities}.
    """
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        prompt = f"""
        You are an inventory assistant. Analyze this tool description and extract structured data.
        
        INPUT TEXT: "{raw_text}"
        
        REQUIREMENTS:
        1. Name: Clean, concise tool name (e.g., "Milwaukee M18 Fuel Driver").
        2. Safety: Strictly choose one: "Open", "Supervised", or "Adult Only".
           - "Open": Simple hand tools (screwdrivers, hammers).
           - "Supervised": Complex hand tools or simple power tools (soldering iron, hand drill).
           - "Adult Only": Dangerous power tools (saws, grinders, nail guns).
        3. Capabilities: A clean string of 3-5 comma-separated keywords (e.g., "drilling, driving screws").
        
        OUTPUT FORMAT:
        Return ONLY valid JSON. No markdown.
        {{
            "name": "...",
            "safety": "...",
            "capabilities": "..."
        }}
        """
        
        response = model.generate_content(prompt)
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_text)
        
    except Exception as e:
        return None