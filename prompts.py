import json

def prompt_project_advice(tool_context, user_query):
    return f"""
    You are the "Hintze Family Tool Manager." 
    Analyze the user's project and recommend tools from the INVENTORY.
    INVENTORY: {tool_context}
    USER QUESTION: <user_input>{user_query}</user_input>
    """

def prompt_tool_parser(raw_text):
    return f"""
    Analyze tool description. INPUT: <user_input>{raw_text}</user_input>
    REQUIREMENTS: Name (Title Case), Brand, Model, Power, Safety, Capabilities, Stationary.
    OUTPUT JSON: {{ "name": "...", "brand": "...", "model_no": "...", "power_source": "...", "safety": "...", "capabilities": "...", "is_stationary": true/false }}
    """

def prompt_smart_recs(user_query, user_name, user_household, my_tools, others_tools):
    json_structure = """
    OUTPUT JSON structure:
    {
        "locate_list": [{"tool_name": "Name", "location": "Location"}],
        "track_down_list": [{"tool_name": "Name", "held_by": "Borrower Name"}],
        "borrow_list": [{"name": "Tool Name", "household": "Owner House", "tool_id": "ID", "reason": "Reason"}],
        "missing_list": [{"tool_name": "Tool Name", "importance": "High/Med/Low", "advice": "Buy/Rent", "reason": "Explanation"}]
    }
    """
    
    return f"""
    You are the Hintze Family Tool Manager.
    PROJECT: <user_input>{user_query}</user_input> 
    USER CONTEXT: Name: "{user_name}", Household: "{user_household}"
    
    LIST 1: TOOLS I PHYSICALLY OWN (My Toolbox):
    {json.dumps(my_tools)}
    
    LIST 2: OTHER FAMILY MEMBERS' TOOLS (Need to borrow):
    {json.dumps(others_tools)}
    
    TASK: Categorize tools into project lists.
    
    CRITICAL LOGIC RULES:
    1. **locate_list**: ONLY use tools from "LIST 1". These must be "available".
    2. **track_down_list**: ONLY use tools from "LIST 1" that have a status "with [Name]".
    3. **borrow_list**: ONLY use tools from "LIST 2". If a tool is needed and you find it here, suggest it for borrowing.
    4. **missing_list**: If a tool is needed but NOT found in LIST 1 or LIST 2, put it here.
    5. **Functional Equivalence**: If the project needs a shovel and the user has a shovel in LIST 1, do NOT suggest borrowing one from LIST 2.
    6. **RELEVANCE**: Only include tools actually needed for the project.
    
    {json_structure}
    """

def prompt_inventory_filter(user_query, context):
    return f"""
    Search Engine. Query: <user_input>{user_query}</user_input>
    Inventory: {context}
    return JSON list of matching IDs: {{ "match_ids": ["ID1", "ID2"] }}
    """

def prompt_location_update(user_query, tool_list_str):
    return f"""
    Inventory Manager. REQUEST: <user_input>{user_query}</user_input>
    TOOLS: {tool_list_str}
    TASK: Identify action (MOVE or RETIRE).
    OUTPUT JSON: {{ "updates": [ {{ "tool_id": "...", "action": "MOVE/RETIRE", "new_bin": "...", "reason": "..." }} ] }}
    """

def prompt_duplicate_check(new_str, existing_list):
    return f"""
    Check for duplicates.
    NEW: {new_str}
    EXISTING: {json.dumps(existing_list)}
    OUTPUT JSON: {{ "is_duplicate": true/false, "match_name": "...", "match_owner": "..." }}
    """

def prompt_lending_request(user_query, tools_ctx, family_names):
    return f"""
    Lending Assistant. QUERY: <user_input>{user_query}</user_input>
    MY TOOLS: {tools_ctx}
    FAMILY: {json.dumps(family_names)}
    
    OUTPUT JSON:
    {{
      "candidates": [ {{"id": "ID", "name": "Name", "household": "House", "confidence": "high/medium"}} ],
      "borrower_name": "Name",
      "duration_days": 7,
      "force_override": true/false
    }}
    """

def prompt_deletion_helper(user_query, tools_ctx):
    return f"""
    Admin Deletion Helper.
    QUERY: <user_input>{user_query}</user_input>
    INVENTORY: {tools_ctx}
    
    TASK: Return a JSON list of IDs that match the deletion criteria.
    OUTPUT JSON: {{ "delete_ids": ["ID1", "ID2"] }}
    """

def prompt_borrowing_request(user_query, tools_ctx):
    return f"""
    Borrowing Assistant. QUERY: <user_input>{user_query}</user_input>
    AVAILABLE TOOLS: {tools_ctx}
    
    TASK: Identify tools and duration requested.
    OUTPUT JSON:
    {{
      "candidates": [ {{"id": "ID", "name": "Name", "household": "House", "confidence": "high/medium"}} ],
      "duration_days": 7
    }}
    """
