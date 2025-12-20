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
    
    # 2. Children are restricted
    if user_role == "CHILD":
        # Allow only explicitly safe categories
        if tool_safety in ["Open", "Supervised"]:
            return True
        # Block "Adult Only" and any unknown/undefined ratings
        return False
        
    # 3. Default: Allow (Adults/Admins)
    return True