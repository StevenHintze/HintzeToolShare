# tools_registry.py
# This file contains ONLY logic rules. 
# Actual tool data is stored in the MotherDuck database.

def check_safety(user_role, tool_safety):
    """
    Determines if a user is allowed to borrow a specific tool.
    
    Args:
        user_role (str): "ADMIN", "ADULT", or "CHILD"
        tool_safety (str): "Open", "Supervised", or "Adult Only"
        
    Returns:
        bool: True if allowed, False if blocked.
    """
    # 1. Admins and Adults can borrow anything
    if user_role == "ADMIN": 
        return True
    if user_role == "ADULT": 
        return True
    
    # 2. Children are blocked from "Adult Only" tools
    if user_role == "CHILD" and tool_safety == "Adult Only": 
        return False
        
    # 3. Default: Allow (e.g. Child borrowing Open/Supervised)
    return True