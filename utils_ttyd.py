import re
import numpy as np
import pandas as pd
import streamlit as st
import pyodbc
import plotly.express as px
from config import *
from utils_context import *
from typing import Optional, List, Dict, Any
from langchain_core.messages import HumanMessage
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import HumanMessage
import ast
import logging
from variables import *
from functools import lru_cache

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@lru_cache(maxsize=1)
def create_agent():
    logger.info("Creating Agent.")
    if AzureChatOpenAI is None or HumanMessage is None:
        raise RuntimeError("langchain-openai not installed. pip install langchain-openai")
    if not AZURE_OPENAI_API_KEY:
        raise RuntimeError("Please set AZURE_OPENAI_API_KEY (env var recommended).")
    return AzureChatOpenAI(
        deployment_name=AZURE_OPENAI_DEPLOYMENT_NAME,
        api_key=AZURE_OPENAI_API_KEY,
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_version=AZURE_OPENAI_API_VERSION,
        temperature=0.2
    )

def classify_intent(state):
    # status = st.status("Processing question...")
    logger.info(f"Classifying Intent.")
    agent = create_agent()
    prompt = f"""You are an expert identifying the intent of a user question.
    With the given question, classify it as `casual`, `business` or `prediction`.
    If the question is about predicting future values then its a `prediction` type.
    If the question is a `casual` question, answer it by yourself.

    Always answer in the below format:
    {{'question_type' : 'the question type', 'answer' : 'your answer if its `casual` type else ``'}}
    Question : {state["question"]}

    Never add any ticks (`) or markdowns in your response.

    """
    response = agent.invoke([HumanMessage(content=prompt)]).content
    logger.info(f"Response from Intent Classifier : {response}")
    response_dict = ast.literal_eval(f"""{response}""")
    state["question_type"] = response_dict["question_type"]
    answer = response_dict["answer"]

    if response_dict["question_type"] == "casual":
        st.chat_message("assistant").write(answer)
    else:
        logger.info("Processed question. Moving to next steps.")
    return state

def load_context(state):
    logger.info("Loading Context.")
    glossary, tbl_schema, sample_data = initialize()
    state["glossary"]=glossary
    state["tbl_schema"]=tbl_schema
    state["sample_data"]=sample_data
    return state

def generate_sql(state):
    agent = create_agent()

    prompt = f"""You are an expert in generating T-SQL queries to query data on Microsoft SQL Server.
                    With the given user question, generate the appropriate T-SQL query based 
                    on the given Glossary, Schema, Table Relationships and Sample Data.
                    Use only the columns and tables provided in the schema, glossary, and samples.
                    NEVER use MySQL/PostgreSQL syntax or backticks.
                    Always return raw SQL with no Markdown or code fences.

                    User Question:
                    {state["question"]}

                    Glossary:
                    {state["glossary"]}

                    Schema:
                    {state["tbl_schema"]}

                    Sample Values:
                    {state["sample_data"]}

                    Relationships:
                    {RELATIONSHIPS} """.strip()
    
    response = agent.invoke([HumanMessage(content=prompt)])
    sql_query = re.sub(r"```(?:sql)?\s*([\s\S]+?)\s*```", r"\1", response.content.strip()).strip()
    logger.info(f"Generated SQL : {sql_query}")
    state["sql_query"] = sql_query
    return state

def execute_sql(state):
    logger.info("Executing SQL")
    with pyodbc.connect(conn_str) as conn:
        logger.info("Connecting to SQL Server")
        cur = conn.cursor()
        logger.info("Running SQL query")
        cur.execute(state["sql_query"])
        if cur.description is None:
            return None
        cols = [d[0] for d in cur.description]
        logger.info(f"Columns fetched : {cols}")
        rows = cur.fetchall()
        df = pd.DataFrame.from_records(rows if rows else [], columns=cols)
        logger.info("SQL execution completed")
        state["data"] = df.to_dict()
        return state
        
def derive_insights(state):
    logger.info("Generating Insights.")
    agent = create_agent()
    if state["data"] is None and state["fcst_data"] is None:
        state["insights"] = "No data retrieved to generate insights."
    
    markdown_table=state["fcst_data"] if state["question_type"].lower()=="prediction"  else state["data"]
    prompt = f"""You are a business analyst for a hospitality based company. 
    Analyze the following data and provide a concise business insight.

    \n\n{markdown_table}"""

    state["insights"] = agent.invoke([HumanMessage(content=prompt)]).content.strip()
    logger.info(f"Insight: {state["insights"]}")

    return state

def _is_percentage_column(series: pd.Series, tol: float = 1.0) -> bool:
    """Detect if a numeric series sums to ~100% within tolerance."""
    logger.info("Looking for percentage columns from the data.")
    try:
        vals = pd.to_numeric(series, errors="coerce").dropna()
        if vals.empty:
            return False
        total = vals.sum()
        return np.isfinite(total) and abs(total - 100.0) <= tol
    except Exception as e:
        logger.error(f"Failed with error : {str(e)}")
        return False
    
def _all_numeric_cols(df: pd.DataFrame) -> List[str]:
    """Return columns that are fully numeric (after coercion)."""
    logger.info("Looking for numeric columns from the data.")
    numeric_cols = []
    for c in df.columns:
        s = pd.to_numeric(df[c], errors="coerce")
        if s.notna().sum() == len(df):
            numeric_cols.append(c)
            logger.info(c)
        logger.info(f"Numeric Columns : {numeric_cols}")
    return numeric_cols

def get_chart_specs(df):
    logger.info("Generating chart specifications")
    if df.shape[0] == 1 and df.shape[1] >= 2:
        numeric_cols = _all_numeric_cols(df)
        if len(numeric_cols) >= 2:
            row = pd.to_numeric(df.loc[df.index[0], numeric_cols], errors="coerce")
            total = float(row.sum()) if np.isfinite(row.sum()) else None
            if total is not None and abs(total - 100.0) <= 1.0:
                melted = row.reset_index()
                melted.columns = ["Category", "Percentage"]
                return {
                    "chart": {"chart_type":"pie","names":"Category","values":"Percentage","title":"Distribution (percent)"},
                    "table": melted.to_dict(orient="records"),
                    "columns": ["Category","Percentage"]
                }

        # General rules
        cat_cols = [c for c in df.columns if df[c].nunique(dropna=True) <= 20]
        num_cols = _all_numeric_cols(df)

        perc_col = next((c for c in num_cols if _is_percentage_column(pd.to_numeric(df[c], errors="coerce"))), None)
        if perc_col and cat_cols:
            return {"chart":{"chart_type":"pie","names":cat_cols[0],"values":perc_col,"title":f"{cat_cols[0]} distribution (percent)"}}

        time_cols = [c for c in df.columns if any(k in c.lower() for k in ["date","month","year","day","ds"])]
        if time_cols and num_cols:
            return {"chart":{"chart_type":"line","x":time_cols[0],"y":num_cols[0],"title":f"{num_cols[0]} by {time_cols[0]}"}}

        if cat_cols and num_cols:
            return {"chart":{"chart_type":"bar","x":cat_cols[0],"y":num_cols[0],"title":f"{num_cols[0]} by {cat_cols[0]}"}}
        
    if len(df.columns) == 1:
        logger.info(f"num cols:{df.columns}")
        return None 

    # Fallback
    logger.info("Falling Back to default chart specifications")
    x = df.columns[0] if len(df.columns) > 0 else "Category"
    y = df.columns[1] if len(df.columns) > 1 else "Value"
    chart = {"chart":{"chart_type":"bar","x":x,"y":y,"title":"Chart"}}
    return chart

def render_chart(spec: Dict[str,Any], df):
    logger.info("Rendering Chart.")
    for col in df.columns:
        coerced = pd.to_numeric(df[col], errors="coerce")
        if coerced.notna().sum() == len(df): df[col] = coerced

    ctype, title = spec.get("chart_type"), spec.get("title","Chart")

    if ctype == "pie":
        fig = px.pie(df, names=spec["names"], values=spec["values"], title=title, hole=0.3)
    elif ctype == "bar":
        fig = px.bar(df, x=spec.get("x"), y=spec.get("y"), title=title, text_auto=True)
    elif ctype == "line":
        fig = px.line(df, x=spec["x"], y=spec["y"], title=title, markers=True)
    elif ctype == "scatter":
        fig = px.scatter(df, x=spec["x"], y=spec["y"], title=title)
    else:
        logger.info(f"Unknown chart type: {ctype}")
        return
    fig.update_layout(template="plotly_white", title_font_size=18)
    return fig
    

def generate_chart(state):
    logger.info("Generating Chart.")
    df = pd.DataFrame(state["data"])
    chart_specs = get_chart_specs(df)
    logger.info(f"Chart Specifications : {chart_specs}")
    if chart_specs is None:
        state["has_figure"] = False
    else:
        fig = render_chart(chart_specs["chart"],df)
        state["chart"] = fig
    return state

