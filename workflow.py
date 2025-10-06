from config import *
from utils_context import *
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from utils_forecast import * 
from utils_ttyd import *
from utils_classification import *
from variables import *

def classifer_router(state):
    if "business" in state["question_type"].strip():
        logger.info("Routing to 'generate_sql'")
        return "generate_sql"
    if "prediction" in state["question_type"].strip():
        logger.info("Routing to 'forecast_expert'")
        return "forecast_expert"
    if "classification" in state["question_type"].strip():
        logger.info("Routing to 'classification_expert'")
        return "classification_expert"
    else:
        return END
    
def forecast_router(state):
    if state["prophet_plan"] is not None:
        return "forecast"
    else:
        return "derive_insights"

def classification_router(state):
    if state["classification_plan"] is not None:
        return "classify"
    else:
        return "derive_insights"

def execute_sql_router(state):
    # Check if this is a forecasting workflow
    if state.get("prophet_plan") is not None:
        return "forecast"
    # Check if this is a classification workflow  
    elif state.get("classification_plan") is not None:
        return "classify"
    # Default to insights for business questions
    else:
        return "derive_insights"

def initialize_graph():
    memory = MemorySaver()
    graph = StateGraph(State)
    graph.add_node("classify_intent", classify_intent)
    graph.add_node("load_context", load_context)
    graph.add_node("generate_sql", generate_sql)
    graph.add_node("execute_sql", execute_sql)
    graph.add_node("derive_insights", derive_insights)
    graph.add_node("generate_chart", generate_chart)
    graph.add_node("forecast_expert", forecast_expert)
    graph.add_node("forecast", forecast)
    graph.add_node("classification_expert", classification_expert)
    graph.add_node("classify", classify)
    
    graph.add_edge(START, "load_context")
    graph.add_edge("load_context", "classify_intent")

    graph.add_conditional_edges("classify_intent", classifer_router)

    graph.add_edge("forecast_expert", "execute_sql")
    graph.add_edge("classification_expert", "execute_sql")
    graph.add_edge("generate_sql", "execute_sql")
    
    graph.add_conditional_edges("execute_sql", execute_sql_router)
    
    graph.add_edge("forecast", END)
    graph.add_edge("classify", END)
    graph.add_edge("derive_insights", "generate_chart")
    graph.add_edge("generate_chart", END)

    graph.set_entry_point("load_context")

    workflow = graph.compile(checkpointer=memory)
    return workflow