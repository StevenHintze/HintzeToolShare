import streamlit as st
import time
from core.gemini_helper import get_smart_recommendations


def render_planner(dm, current_user):
    st.header("🏗️ Project Planner")
    if "ai_recs" not in st.session_state: st.session_state["ai_recs"] = None

    if st.session_state["ai_recs"] is None:
        st.info(f"Describe your job. I'll check your household tools, find ones you may need to borrow, and identify useful tools that are not in the family toolbox.")
        with st.form("project_form"):
            project_query = st.text_area("Describe your project:", placeholder="e.g. I need to rotate my tires and change the oil...")
            submit_search = st.form_submit_button("Analyze Needs")
        
        if submit_search:
            if project_query:
                with st.spinner("Planning and Looking for Tools..."):
                    all_tools_df = dm.get_all_tools() # Cached
                    recs = get_smart_recommendations(project_query, all_tools_df, current_user['household'], current_user['name'])
                    if recs:
                        st.session_state["ai_recs"] = recs
                        st.rerun()
    else:
        recs = st.session_state["ai_recs"]
        if st.button("← Start Over"):
            st.session_state["ai_recs"] = None
            st.rerun()

        if recs.get('locate_list'):
            st.success("✅ **You already own these:**")
            for item in recs['locate_list']:
                clean_name = item['tool_name'].replace("**", "").strip()
                st.markdown(f"- **{clean_name}** ({item.get('location', 'Home')})")
        
        if recs.get('track_down_list'):
            st.warning("⚠️ **You own these, but they are borrowed by someone**")
            for item in recs['track_down_list']:
                clean_name = item['tool_name'].replace("**", "").strip()
                st.markdown(f"- **{clean_name}** is with **{item['held_by']}**")

        if recs.get('missing_list'):
             st.error("🛑 **Missing Essentials (Not in Family Registry):**")
             for item in recs['missing_list']:
                 clean_name = item['tool_name'].replace("**", "").strip()
                 st.markdown(f"**{clean_name}** ({item['importance']})")
                 if item.get('reason'):
                      st.write(f"_{item['reason']}_")
                 st.caption(f"💡 *Advice: {item['advice']}*")

        if recs.get('borrow_list'):
            st.info("🛒 **Tools to Borrow:**")
            with st.form("smart_borrow"):
                selected_ids = []
                for item in recs['borrow_list']:
                    clean_name = item['name'].replace("**", "").strip()
                    label = f"**{clean_name}** from {item['household']}"
                    if item.get('tool_id') and item['tool_id'] != "Unknown":
                        if st.checkbox(label, value=True, help=item['reason']):
                            selected_ids.append(item['tool_id'])
                days = st.number_input("Days needed:", min_value=1, value=7)
                if st.form_submit_button("Confirm Borrow Request"):
                    if selected_ids:
                        for tid in selected_ids:
                            dm.borrow_tool(tid, current_user['name'], days)
                        st.success("Tools borrowed!")
                        st.session_state["ai_recs"] = None
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.warning("No tools selected.")
        
        elif not recs.get('missing_list'):
            st.info("Looks like you have everything you need at home! Good luck.")
