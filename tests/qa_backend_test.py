
import toml
import pandas as pd
import json
import os
import sys

# Setup Path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock Streamlit Secrets
import streamlit as st
try:
    secrets = toml.load(".streamlit/secrets.toml")
    st.secrets = secrets
except Exception as e:
    print(f"Failed to load secrets: {e}")
    sys.exit(1)

from gemini_helper import get_smart_recommendations, parse_lending_request, parse_borrowing_request

def test_planner_logic():
    print("\n[TEST] Project Planner Logic (Split Lists)")
    # Scenario: I own a "Hammer". Shawn owns a "Drill".
    # I need a Hammer and a Drill.
    # Expected: "Hammer" in locate_list, "Drill" in borrow_list.

    user_name = "Steve"
    user_house = "Main House"
    
    data = [
        {"id": "1", "name": "Hammer", "brand": "Estwing", "owner": "Steve", "household": "Main House", "status": "Available", "is_stationary": False, "bin_location": "Garage"},
        {"id": "2", "name": "Drill", "brand": "DeWalt", "owner": "Shawn", "household": "Guest House", "status": "Available", "is_stationary": False, "bin_location": "Shed"}
    ]
    df = pd.DataFrame(data)
    
    res = get_smart_recommendations("I need a hammer and a drill", df, user_house, user_name)
    
    if res:
        print(f"Result Keys: {res.keys()}")
        locate = [t['tool_name'] for t in res.get('locate_list', [])]
        borrow = [t['name'] for t in res.get('borrow_list', [])]
        
        print(f"Locate List: {locate}")
        print(f"Borrow List: {borrow}")

        if "Hammer" in str(locate) and "Drill" in str(borrow):
            print("✅ Planner Logic PASSED: Correctly split ownership.")
        else:
            print("❌ Planner Logic FAILED: Incorrect categorization.")
    else:
        print("❌ Planner Logic FAILED: No response.")

def test_lending_logic():
    print("\n[TEST] Lending AI Parsing")
    # Scenario: Lend "Truck" to "Shawn" for "3 days"
    user_query = "Lend the truck to Shawn for 3 days"
    
    my_tools = pd.DataFrame([{"id": "T1", "name": "Truck", "brand": "RAM", "household": "Main House"}])
    family = [{"name": "Shawn"}]
    
    res = parse_lending_request(user_query, my_tools, family)
    
    if res:
        print(f"Borrower: {res.get('borrower_name')}")
        print(f"Duration: {res.get('duration_days')}")
        candidates = res.get('candidates', [])
        if candidates:
            print(f"First Candidate House: {candidates[0].get('household')}")
        
        if res.get('duration_days') == 3 and res.get('borrower_name') == "Shawn":
            print("✅ Lending Logic PASSED: Extracted duration and borrower.")
        else:
            print("❌ Lending Logic FAILED: Extraction error.")
    else:
        print("❌ Lending Logic FAILED: No response.")

def test_borrowing_logic():
    print("\n[TEST] Borrowing AI Parsing")
    # Scenario: Borrow "Shovel" for "5 days"
    user_query = "I need a shovel for 5 days"
    
    avail_tools = pd.DataFrame([{"id": "S1", "name": "Shovel", "brand": "Fiskars", "household": "Guest House"}])
    
    res = parse_borrowing_request(user_query, avail_tools)
    
    if res:
        print(f"Duration: {res.get('duration_days')}")
        candidates = res.get('candidates', [])
        if candidates:
            print(f"Refine List House: {candidates[0].get('household')}")
            
        if res.get('duration_days') == 5 and candidates and candidates[0].get('household') == "Guest House":
            print("✅ Borrowing Logic PASSED: Extracted duration and household.")
        else:
            print("❌ Borrowing Logic FAILED: Extraction error.")

if __name__ == "__main__":
    print("Starting QA Backend Tests...")
    test_planner_logic()
    test_lending_logic()
    test_borrowing_logic()
