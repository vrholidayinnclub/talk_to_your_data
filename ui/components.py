"""
Reusable UI components for Streamlit app.
"""
import streamlit as st
import pandas as pd
from typing import Dict, Any


def render_header():
    """Render the application header with logo and title."""
    image_url = "https://images.contentstack.io/v3/assets/bltba617d00249585dc/blt69e58331690e2b02/6165ae737c52211d10e30f80/holiday-inn-club-vacations-logo.png"
    
    st.markdown(
        f"""
        <style>
        /* Target the Streamlit header element */
        [data-testid="stHeader"] {{
            background-image: url({image_url});
            background-repeat: no-repeat;
            background-size: 80px;
            background-position: 10px 10px;
            height: 80px;
            padding-left: 100px;
            display: flex;
            align-items: center;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    
    st.title("Talk to your HICV Business Data!")


def render_message_history():
    """Render chat message history from session state."""
    for msg in st.session_state["messages"]:
        if msg.get("type") == "code":
            st.chat_message(msg["role"]).code(msg["content"], language="sql", wrap_lines=True)
        elif msg.get("type") == "dataframe":
            df = pd.DataFrame(msg["content"])
            st.chat_message(msg["role"]).dataframe(df, use_container_width=True)
        else:
            st.chat_message(msg["role"]).write(msg["content"])


def render_result(result: Dict[str, Any]):
    """
    Render agent result in Streamlit UI.
    
    Args:
        result: Dictionary containing agent response with keys:
            - sql_query: Generated SQL query (optional)
            - data: Query results (optional)
            - answer: Natural language answer
            - metrics/model_metrics: Performance metrics (optional)
    """
    # SQL Query
    if result.get("sql_query"):
        with st.expander("SQL Query", expanded=True):
            st.markdown("**Generated SQL Query:**")
            st.code(result["sql_query"], language="sql", wrap_lines=True)
        st.session_state.messages.append({
            "role": "assistant",
            "type": "code",
            "content": result["sql_query"]
        })
    
    # Data
    data_obj = result.get("data")
    if data_obj is not None:
        try:
            df = pd.DataFrame(data_obj)
        except Exception:
            df = pd.DataFrame(data_obj if isinstance(data_obj, list) else [])
        
        with st.expander("Data", expanded=True):
            st.markdown("**Retrieved Data**")
            st.dataframe(df, use_container_width=True)
        st.session_state.messages.append({
            "role": "assistant",
            "type": "dataframe",
            "content": df.to_dict(orient='records')
        })
    
    # Answer/Insights
    if result.get("answer"):
        st.chat_message("assistant").write(result["answer"])
        st.session_state.messages.append({
            "role": "assistant",
            "content": result["answer"]
        })
    
    # Metrics
    metrics = result.get("metrics") or result.get("model_metrics")
    if metrics:
        with st.expander("📏 Metrics", expanded=True):
            st.write(metrics)


def add_user_message(question: str):
    """Add user message to session and display it."""
    st.session_state.messages.append({"role": "user", "content": question})
    st.chat_message("user").write(question)
