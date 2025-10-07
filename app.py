import pandas as pd, streamlit as st
from utils_ttyd import *
from utils_context import *
import uuid
import plotly.io as pio
import io
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
    st.set_page_config(page_title="Talk To Your Data")

    st.title("Talk to your HICV Business Data!")
    status = st.status("Preparing assistant…")

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
    "relationships" : "",
    "question_type": "",
    "prophet_plan": None,
    "chart": None,
    "fcst_data" : None,
    "accuracy_metrics": None,
    "classification_plan": None,
    "classify_data": None,
    "metrics": None,
    "classification_results": None
    }

    workflow = initialize_graph()
    status.update(label="Assistant is ready ✅", state="complete")

    if "messages" not in st.session_state:
        st.session_state["messages"] = [{"role" : "assistant", "content" : "Welcome to Holiday Inn Club Vacations! I'm your Business Analyst and I'm here to answer your business queries. How can I assist you today? "}] 
    for msg in st.session_state["messages"]:
        if msg.get("type") == "code":
            st.chat_message(msg["role"]).code(msg["content"], language="sql", wrap_lines=True, height='stretch')
        elif msg.get("type") == "dataframe":
            df = pd.DataFrame(msg["content"])
            st.chat_message(msg["role"]).dataframe(df, width='stretch')
        # elif msg.get("type") == "plotly":
        #     fig = pio.from_json(msg["content"])
        #     st.chat_message(msg["role"]).plotly_chart(fig, width='stretch')
        else:
            st.chat_message(msg["role"]).write(msg["content"])

    try:
        if question :=st.chat_input():
            st.session_state.messages.append({"role": "user", "content" : question})
            st.chat_message("user").write(question)
            state["question"] = question  
            status=st.status("Thinking...", state="running")

            for step in workflow.stream(state, stream_mode="updates", config=config):
                node = list(step.keys())[0]
                logger.info(f"CurrNode: {node}")

                if (node=="generate_sql" or node == "forecast_expert" or node == "classification_expert") \
                    and step.get(node).get("sql_query") is not None:
                    status.update(label=f"Writing SQL to fetch the required data...", state="running")
                    content = step.get(node).get("sql_query")
                    content_type = "code"
                    
                    with st.expander("SQL Query", expanded=True):
                        st.markdown("**Generated SQL Query:**")
                        st.code(content, language="sql", wrap_lines=True, height='stretch')
                    st.session_state.messages.append({"role": "assistant", "type": content_type, "content": content})

                if node=="execute_sql" and step.get(node).get("data") is not None and step.get(node).get("show_data"):
                    status.update(label="Executing SQL ...", state="running")
                    content = step.get(node).get("data")
                    content_type = 'dataframe'
                    with st.expander("Data", expanded=True):
                        st.markdown("**Retrieved Data**")
                        st.dataframe(content)
                    st.session_state.messages.append({"role": "assistant", "type": content_type, "content": content})

                if node =="derive_insights":
                    status.update(label="Generating Insights...", state="running")
                    content = f'{step.get(node).get("insights")}'
                    content_type = 'text'
                    with st.expander("Insights", expanded=True):
                        st.markdown("**Generated Insights:**")
                        st.write(content)
                    st.session_state.messages.append({"role": "assistant", "type": content_type, "content": content})

                if node == "generate_chart":
                    status.update(label="Generating Chart...", state="running")
                    content = pio.from_json(step.get(node).get("chart"))
                    content_type = 'plotly'
                    with st.expander("Charts", expanded=True):
                        st.markdown("**Generated Chart:**")
                        st.plotly_chart(content, use_container_width=True)
                    st.session_state.messages.append({"role": "assistant", "type": content_type, "content": content})

                if node == "forecast":
                    status.update(label="Forecasting...", state="running")

                    with st.expander("Data", expanded=True):
                        content = step.get(node).get("fcst_data")
                        content_type = 'dataframe'
                        st.markdown("**📝 Sample Forecasted Data:**")
                        st.dataframe(content)
                    st.session_state.messages.append({"role": "assistant", "type": content_type, "content": content})

                    with st.expander("Chart", expanded=True):
                        content = pio.from_json(step.get(node).get("chart"))
                        content_type = 'plotly'
                        st.markdown(f"**📌 Forecast Error Rates**  {step.get(node).get('accuracy_metrics')} ")
                        st.plotly_chart(content, use_container_width=True)
                    st.session_state.messages.append({"role": "assistant", "type": content_type, "content": content})
                    
                    with st.expander("Forecasted Insights", expanded=True):
                        content = f'{step.get(node).get("insights")}'
                        content_type = 'text'
                        st.markdown("**🔮 Insights:**")
                        st.write(content)
                    st.session_state.messages.append({"role": "assistant", "type": content_type, "content": content})

                    content = f"📊 Predicted with Prophet-Model with error : {step.get(node).get('accuracy_metrics')}."
                    content_type = "text"
                    st.write(content)
                    st.session_state.messages.append({"role": "assistant", "type": content_type, "content": content})
                    status.update(label="Answer Ready ✅", state="complete")
                        
                if node == "classification_expert":
                    status.update(label="Preparing data for prediction...", state="running")
                    classification_plan = step.get(node).get("classification_plan", {})

                if node == "classify":
                    status.update(label="Predicting...", state="running")

                    st.subheader("📌 Likelihood by Customer Segments")
                    classification_results = step.get(node).get("classification_results", {})
                    segment_details = classification_plan.get("segment_definition", {})

                    total_segments = len(segment_details)
                    cols = st.columns(total_segments)
                    
                    # Loop through segments and columns together
                    for col, (name, seg) in zip(cols, segment_details.items()):
                        count = len(seg)
                        # percentage = (count / total_segments * 100) if total_segments else 0
                        col.metric(label=name, value=f"{count:,}")
                    st.write("Segmentation Details")
                    st.markdown(
                                "\n".join(f"- **{k}**: {v}" for k, v in segment_details.items())
                            )
                    if not classification_results:
                        st.warning("⚠️ Classification results are empty. Please check the input data and configuration.")
                        continue

                    content = classification_results.get("top_likely")
                    content_type = 'dataframe'
                    df_data_preview = pd.DataFrame(content)
                    csv_buf_top = io.StringIO()

                    st.subheader("🏆 Top 100 Most Likely Customers")
                    st.dataframe(df_data_preview, width='content')
                    st.session_state.messages.append({"role": "assistant", "type": content_type, "content": content})

                    df_data_preview.to_csv(csv_buf_top, index=False)
                    st.download_button(
                        label="⬇️ Download Top 100 Likely Customers (CSV)",
                        data=csv_buf_top.getvalue(),
                        file_name="top_100_likely_customers.csv",
                        mime="text/csv"
                    )

                    metrics = step.get(node).get("metrics", None)
                    content = f"📊 Predicted with XGBoost-Model with an accuracy of {round(metrics['accuracy']) * 100}%."
                    content_type = 'text'
                    st.write(content)
                    st.session_state.messages.append({"role": "assistant", "type": content_type, "content": content})
                    status.update(label="Answer Ready ✅", state="complete")
                    
                if node == END:
                    status.update(label="Answer Ready ✅", state="complete")
                    logger.info("Workflow reached the end node.")
                    
    except Exception as e:
        logger.error(str(e))


if __name__ == '__main__':
    main()