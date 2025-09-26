import os, re, json, importlib, numpy as np, pandas as pd, streamlit as st, pyodbc
import plotly.graph_objects as go
from utils_ttyd import *
from utils_context import *
import uuid
import plotly.io as pio
import logging
from workflow import *
logger = logging.getLogger(__name__)


def main():
    logger.info("Starting application.")
    image_url = "https://images.contentstack.io/v3/assets/bltba617d00249585dc/blt69e58331690e2b02/6165ae737c52211d10e30f80/holiday-inn-club-vacations-logo.png" # Replace with your image URL

    st.markdown(
    f"""
    <style>
    /* Target the Streamlit header element */
    [data-testid="stHeader"] {{
        background-image: url({image_url}); /* Your logo image */
        background-repeat: no-repeat;
        background-size: 80px; /* Adjust logo size as needed */
        background-position: 10px 10px; /* Adjust padding (left and top) */
        height: 80px; /* Adjust header height to accommodate logo and padding */
        padding-left: 100px; /* Adjust padding to make space for the logo */
        display: flex; /* Use flexbox for alignment */
        align-items: center; /* Vertically center content if needed */
    }}
    """,
    unsafe_allow_html=True,
)
    # st.logo(image_url, size='large', )  # Display the logo in the sidebar
    st.set_page_config(page_title="Talk To Your Data")

    st.title("Talk to your HICV Business Data!")
    status = st.status("Preparing assistant…", expanded=True)

    sess_id = uuid.uuid4()
    config = {"configurable":{"thread_id":sess_id}}

    state: State = {
    "messages": [],
    "question": "",
    "sql_query": None,
    "data": None,
    "show_data": True,
    "insights": None,
    "glossary": "",
    "tbl_schema": "",
    "sample_data": "",
    "question_type": "",
    "prophet_plan": None,
    "chart": None,
    "fcst_data" : None,
    "accuracy_metrics": None
                }

    workflow = initialize_graph()
    status.update(label="Assistant is ready ✅", state="complete")

    if "messages" not in st.session_state:
        st.session_state["messages"] = [{"role" : "assistant", "content" : "Welcome to Holiday Inn Club Vacations! I'm your Business Analyst and I'm here to answer your business queries. How can I assist you today? "}] 
    for msg in st.session_state["messages"]:
        if msg.get("type") == "code":
            st.chat_message(msg["role"]).code(msg["content"], language="sql")
        elif msg.get("type") == "dataframe":
            df = pd.DataFrame(msg["content"])
            st.chat_message(msg["role"]).dataframe(df, width='stretch')
        elif msg.get("type") == "plotly":
            fig = pio.from_json(msg["content"])
            st.chat_message(msg["role"]).plotly_chart(fig, width='stretch')
        else:
            st.chat_message(msg["role"]).write(msg["content"])

    try:
        
        if question :=st.chat_input():
            st.session_state.messages.append({"role": "user", "content" : question})
            st.chat_message("user").write(question)
            state["question"] = question  
            status=st.status("Processing question...", state="running")

            for step in workflow.stream(state, stream_mode="updates", config=config):
                node = list(step.keys())[0]
                logger.info(f"CurrNode: {node}")
                # st.session_state.messages.append({"role": "assistant", "content": msg})
                if (node=="generate_sql" or node == "forecast_expert") and step.get(node).get("sql_query") is not None:
                    msg = "Generated SQL Query."
                    st.session_state.messages.append({"role": "assistant", "content": msg})
                    st.session_state.messages.append({"role": "assistant", "type": "code", "content": step.get(node).get("sql_query")})
                    st.chat_message("assistant").write(msg)
                    with st.expander("SQL Query", expanded=True):
                        st.markdown("**Generated SQL Query:**")
                        st.markdown(f"```sql\n{step.get(node).get('sql_query')}\n```")

                if node=="execute_sql" and step.get(node).get("data") is not None and step.get(node).get("show_data"):
                    st.session_state.messages.append({"role": "assistant", "type": "dataframe", "content": step.get(node).get("data")})
                    st.chat_message("assistant").write(msg)
                    with st.expander("Data", expanded=True):
                        st.markdown("**Retrieved Data**")
                        st.dataframe(step.get(node).get("data"))

                if node =="derive_insights":
                    msg = f'{step.get(node).get("insights")}'
                    st.session_state.messages.append({"role": "assistant", "content": msg})
                    st.chat_message("assistant").write(msg)
                    with st.expander("Insights", expanded=True):
                        st.markdown("**Generated Insights:**")
                        st.write(msg)

                if node == "generate_chart":
                    st.session_state.messages.append({"role": "assistant", "type": "plotly", "content": step.get(node).get("chart")})
                    with st.expander("Charts", expanded=True):
                        st.markdown("**Generated Chart:**")
                        st.plotly_chart(step.get(node).get("chart"), use_container_width=True)

                if node == "forecast":
                    st.session_state.messages.append({"role": "assistant", "type": "dataframe", "content": step.get(node).get("fcst_data")})
                    with st.expander("Data", expanded=True):
                        st.markdown("**Sample Forecasted Data:**")
                        st.dataframe(step.get(node).get("fcst_data"))
                    st.session_state.messages.append({"role": "assistant", "type": "plotly", "content": step.get(node).get("chart")})
                    with st.expander("Chart", expanded=True):
                        st.markdown(f"**Forecast Accuracy Scores**  {step.get(node).get('accuracy_metrics')} ")
                        fig = pio.from_json(step.get(node).get("chart"))
                        st.plotly_chart(fig, use_container_width=True)
                    msg = f'{step.get(node).get("insights")}'
                    st.session_state.messages.append({"role": "assistant", "content": msg})
                    with st.expander("Forecasted Insights", expanded=True):
                        st.markdown("**Insights:**")
                        st.write(msg)
            status.update(label="Answer Ready ✅", state="complete")
            
    except Exception as e:
        logger.error(str(e))


if __name__ == '__main__':
    main()