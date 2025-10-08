from config import *
from utils_context import *
from langchain_core.messages import HumanMessage
from utils_forecast import * 
from variables import *
from utils_ttyd import *
from prophet import Prophet
import json
import plotly.graph_objects as go
from datetime import datetime


def forecast_expert(state):
    logger.info("Planning for forecast")
    agent = create_agent()

    prompt = f"""You are an expert data analyst who prepares all the data and parameters required to train a Prophet model.
                    Your goal to provide the right data and parameters for training model.
                    With the given user question, generate the appropriate T-SQL query and the right parameters for Prophet model based 
                    on the given Glossary, Schema, Table Relationships and Sample Data.
                    Use only the columns and tables provided in the schema, glossary, and samples.
                    Always alias the date-type column as `ds` and the column to be predicted as `y`.
                    Remember to include the details for periods, freq for Prophet's `make_future_dataframe` function
                    based on the user's question along with other parameters.
                    Never include any ticks (`) or markdowns in your answer.
                    If prediction is for a week use weekly aggregated data for previous 3 year with the start date of the week representing the date for prophet model.
                    If prediction is for a month use monthly aggregated data for previous 3 year with the start date of the month representing the date for prophet model.
                    If prediction is for a quarter use monthly aggregated data for previous 5 years with the start date of the quarter representing the date for prophet model.
                    If prediction is for a year use monthly aggregated data for previous 5 years with the start date of the month representing the date for prophet model.
                    
                    User Question:
                    {state["question"]}

                    Glossary:
                    {state["glossary"]}

                    Schema:
                    {state["tbl_schema"]}

                    Sample Values:
                    {state["sample_data"]}

                    Relationships:
                    {RELATIONSHIPS} 

                    Your Answers-
                    {{
                    "SQL" : A valid raw T-SQL query enclosed between without any MySQL/PostgreSQL syntax. Never include any ticks(`) or any markdowns,\
                    "prophet_args" : in JSON format without any ticks(`) or markdowns,\
                    "make_future_dataframe_args" : Always include periods and freq details only here,\
                    }}
                    """.strip()
    
    
    response = agent.invoke([HumanMessage(content=prompt)])
    logger.info(response)
    logger.info(f"Response from Forecast Expert : {response.content}")
    
    response_dict = json.loads(response.content)
    state["show_data"] = False
    state["prophet_plan"] = response_dict
    state["sql_query"] = response_dict["SQL"]
    logger.info(f"Generated SQL for forecast : {response_dict["SQL"]}")
    logger.info(f"Generated Prophet args : {response_dict["prophet_args"]}")
    return state

def train_prophet(df, prophet_args, make_future_dataframe_args):
    ## feature engineering
    logger.info(f"Training Prophet with params : {prophet_args}")
    m = Prophet(**prophet_args)
    m.fit(df[["ds","y"]])
    logger.info("Training Complete.")
    logger.info("Forecast is progress.")
    future = m.make_future_dataframe(periods=make_future_dataframe_args["periods"], freq=make_future_dataframe_args["freq"], include_history=True)
    fcst = m.predict(future)[["ds","yhat","yhat_lower","yhat_upper"]]
    # Rename to user-friendly terms
    fcst = fcst.rename(columns={
        "ds": "Date",
        "yhat": "Forecast",
        "yhat_lower": "Lower Bound",
        "yhat_upper": "Upper Bound"
    })
    # Ensure both Date columns are datetime
    fcst["Date"] = pd.to_datetime(fcst["Date"])
    df_renamed = df.rename(columns={"ds": "Date", "y": "Actual"})
    df_renamed["Date"] = pd.to_datetime(df_renamed["Date"])
    logger.info("Forecast Complete.")
    logger.info("Merging past and future data.")
    result = fcst.merge(
        df_renamed[["Date", "Actual"]], 
        on="Date", 
        how="left"
    )
    logger.info("Data ready!")
    return m, result

def plot_forecast(df_fc: pd.DataFrame, title: str):
    df_fc = df_fc.sort_values(by="Date", ascending=False).head(24)
    fig = go.Figure()
    
    # Format hover template to show values
    hover_temp = "<b>Date:</b> %{x}<br><b>Value:</b> %{y:,.0f}"
    
    if "Actual" in df_fc.columns and df_fc["Actual"].notna().any():
        fig.add_trace(go.Scatter(
            x=df_fc["Date"], 
            y=df_fc["Actual"], 
            mode="lines", 
            name="Historical Values",
            hovertemplate=hover_temp + "<br><b>Type:</b> Actual<extra></extra>",
            line=dict(color="royalblue")
        ))
    
    # Add forecast line
    fig.add_trace(go.Scatter(
        x=df_fc["Date"], 
        y=df_fc["Forecast"], 
        mode="lines", 
        name="Predicted Values",
        hovertemplate=hover_temp + "<br><b>Type:</b> Forecast<extra></extra>",
        line=dict(color="orange")
    ))
    
    # Add confidence interval
    if "Lower Bound" in df_fc.columns and "Upper Bound" in df_fc.columns:
        fig.add_trace(go.Scatter(
            x=pd.concat([df_fc["Date"], df_fc["Date"][::-1]]),
            y=pd.concat([df_fc["Upper Bound"], df_fc["Lower Bound"][::-1]]),
            fill="toself", 
            mode="lines", 
            line=dict(width=0),
            fillcolor="rgba(255, 165, 0, 0.2)",
            name="Confidence Range",
            hoverinfo="skip"
        ))
    
    # Improve layout
    fig.update_layout(
        template="plotly_white",
        title=dict(
            text=title,
            font=dict(size=18)
        ),
        xaxis_title="Date",
        yaxis_title="Value",
        hovermode="x unified",
        showlegend=True,
        legend=dict(
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=0.01
        )
    )
    
    return fig.to_json()

def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    mask = np.isfinite(y_true) & np.isfinite(y_pred)
    y_true, y_pred = y_true[mask], y_pred[mask]
    if len(y_true) == 0:
        return f"""\n\n MAPE: nAN \n sMAPE: nAN \n\n """
    mae = str(round(np.mean(np.abs(y_true - y_pred))))
    mape = str(round(np.mean(np.abs((y_true - y_pred) / np.maximum(1e-9, np.abs(y_true)))) * 100.0))
    smape = str(round(np.mean(2.0 * np.abs(y_pred - y_true) / (np.maximum(1e-9, np.abs(y_true) + np.abs(y_pred)))) * 100.0))
    return f"""\n 📝MAPE:  {mape}% \t 📝sMAPE:  {smape}%"""

def forecast(state):
    logger.info("Forecast in progress.")
    data_train = pd.DataFrame(state["data"])
    prophet_args = state["prophet_plan"]["prophet_args"]
    make_future_dataframe_args = state["prophet_plan"]["make_future_dataframe_args"]
    model, df_fcst = train_prophet(data_train, prophet_args, make_future_dataframe_args)
    state["accuracy_metrics"] = compute_metrics(df_fcst["Actual"], df_fcst["Forecast"])
    logger.info("Forecast Complete.")
    logger.info(f"Forecast Accuracy: {state["accuracy_metrics"]}")

    agent = create_agent()
    prompt = f"""With the given user question and the forecasted data provide a consise answert
                Also provide a short and concised business insight based on the same.

                Question:
                {state["question"]}

                Forecast Data:
                {df_fcst.head().to_dict()}

                Always answer in one short sentence.
                Never add any ticks (`) or markdowns in your response.
                """
    response = agent.invoke([HumanMessage(content=prompt)]).content
    logger.info(f"Response from Insight Generator for Forecast Data: {response}")
    state["insights"] = response
    state["fcst_data"] = df_fcst.to_dict()
    state["chart"] = plot_forecast(df_fcst, title="Forecast vs Actuals")
    logger.info("Forecast Chart Generated.")
    return state