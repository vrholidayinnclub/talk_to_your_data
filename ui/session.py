"""
Session state management for Streamlit app.
"""
import streamlit as st
from agent.general_agent import GeneralAgent


def initialize_session():
    """Initialize session state variables."""
    # Initialize agent
    if "_single_agent" not in st.session_state:
        st.session_state["_single_agent"] = GeneralAgent()
    
    # Initialize message history
    if "messages" not in st.session_state:
        st.session_state["messages"] = [
            {
                "role": "assistant",
                "content": "Welcome to Holiday Inn Club Vacations! I'm your Business Analyst and I'm here to answer your business queries. How can I assist you today?"
            }
        ]
    
    return st.session_state["_single_agent"]
