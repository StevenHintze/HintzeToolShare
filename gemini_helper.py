import google.generativeai as genai
import streamlit as st
import pandas as pd

def get_ai_advice(user_query, available_tools_df):
    """
    Sends the user's project query + current inventory to Gemini.
    """
    # 1. Configure the API
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    except Exception as e:
        return "⚠️ Error: Gemini API Key missing or invalid."

    # 2. Format the Inventory for the AI
    # We convert the DataFrame to a simple string list for the prompt
    tool_context = ""
    for index, row in available_tools_df.iterrows():
        tool_context += f"- {row['name']} (Safety: {row['safety_rating']}, Capabilities: {row['capabilities']})\n"

    # 3. Construct the "System Prompt"
    prompt = f"""
    You are the "Hintze Family Tool Manager."    

    YOUR GOAL:
    Help a family member choose the right tools for their project from the AVAILABLE INVENTORY below.
    
    RULES:
    1. ONLY recommend tools listed in the INVENTORY. Do not suggest things they don't have.
    2. If the user asks about a project (e.g., "hang a shelf"), list the specific tools they should borrow.
    3. If a tool is "Adult Only" and the project sounds dangerous, add a safety warning.
    4. Provide the current household the tools are in (assume they are in the owner's household if not borrowed).
    5. If the tool is currently borrowed, provide the name of the borrower. 
    6. Be concise and helpful.
    
    INVENTORY (Currently Available):
    {tool_context}
    
    USER QUESTION:
    "{user_query}"
    """

    # 4. Call Gemini 2.5 Flash
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"⚠️ AI Error: {str(e)}"