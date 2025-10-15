"""
Main Streamlit application entry point.
Orchestrates UI components and business logic.
"""
import streamlit as st
import logging
from agent.general_agent import GeneralAgent
from ui import render_header, render_message_history, render_result, initialize_session
from ui.components import add_user_message

logger = logging.getLogger(__name__)

def main():
    """Main application entry point."""
    logger.info("Starting application.")
    
    # Configure page
    st.set_page_config(
        page_title="Talk To Your Data",
        page_icon=":chart:",
        layout="wide"
    )
    
    # Render header
    render_header()
    
    # Initialize session and get agent
    status = st.status("Preparing assistant…")
    agent = initialize_session()
    status.update(label="Assistant is ready ✅", state="complete")
    
    # Render message history
    render_message_history()

    # Handle user input
    try:
        if question := st.chat_input():
            # Display user message
            add_user_message(question)
            
            # Process question
            status = st.status("Thinking...", state="running")
            result = agent.run(question)
            
            # Render result
            render_result(result)
            
            status.update(label="Answer Ready ✅", state="complete")
                    
    except Exception as e:
        st.error(f"‼️ Failed to get you an answer due to: {str(e)}")
        logger.error(f"Application error: {str(e)}", exc_info=True)


if __name__ == '__main__':
    main()