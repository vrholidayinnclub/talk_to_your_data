from typing import TypedDict, Annotated, Sequence, Any
import operator
from langchain_core.messages.base import BaseMessage
from pydantic import BaseModel, Field


class State(TypedDict):
    question: str
    sql_query: str
    data: Any
    show_data: bool
    insights: str
    glossary: str
    tbl_schema: str
    sample_data: str
    question_type: str
    prophet_plan: dict
    chart: Any
    fcst_data : Any
    accuracy_metrics: dict

