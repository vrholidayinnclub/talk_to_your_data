"""
Forecasting Tool
Time-series forecasting using Prophet.
"""

import json
import logging
import pandas as pd
import numpy as np
import re
from prophet import Prophet

from langchain_openai import AzureChatOpenAI
from langchain_core.messages import HumanMessage
from utils.config import AZURE_OPENAI_DEPLOYMENT_NAME, AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_VERSION
from utils.context import load_glossary, get_table_schema, connect_to_sql, RELATIONSHIPS
from tools.execute_sql import execute_sql_tool

logger = logging.getLogger(__name__)


def create_llm():
    """Create LLM client for forecasting."""
    return AzureChatOpenAI(
        deployment_name=AZURE_OPENAI_DEPLOYMENT_NAME,
        api_key=AZURE_OPENAI_API_KEY,
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_version=AZURE_OPENAI_API_VERSION,
        temperature=0,
        max_retries=3,
        timeout=60
    )


def forecast_tool(question: str) -> str:
    """
    Complete forecasting workflow as a tool.
    
    Steps:
    1. Plan SQL and hyperparameters
    2. Execute SQL to fetch data
    3. Train Prophet model
    4. Generate forecast
    5. Return results with insights
    
    Args:
        question: User's forecasting question
        
    Returns:
        JSON string with forecast results
    """
    logger.info("=" * 80)
    logger.info("TOOL: forecast_tool")
    logger.info(f"Question: {question}")
    
    try:
        # Load context
        glossary = load_glossary()
        cur = connect_to_sql()
        schema = get_table_schema(cur)
        
        # Step 1: Plan SQL and hyperparameters
        llm = create_llm()
        
        plan_prompt = f"""# Task
Generate a T-SQL query and Prophet forecasting parameters to answer the user's question.

# User Question
{question}

# Database Context

## Business Glossary
{glossary}

## Database Schema
{schema}

## Table Relationships
{RELATIONSHIPS}

# Requirements

## SQL Query Requirements:
1. **Date Column**: Must be aliased as 'ds' (Prophet requirement)
2. **Value Column**: Must be aliased as 'y' (Prophet requirement)
3. **Aggregation**: Choose appropriate level (daily/weekly/monthly) based on:
   - Data volume (prefer daily for <2 years, weekly for 2-5 years, monthly for >5 years)
   - Business context (sales typically daily, revenue monthly)
4. **Date Range**: Include sufficient history (minimum 1 year, prefer 2+ years)
5. **Filters**: Apply relevant WHERE clauses based on user question
6. **Data Quality**: Exclude NULL values, ensure chronological order

## Prophet Parameters:
- **seasonality_mode**: "additive" (constant seasonal effect) or "multiplicative" (proportional to trend)
- **yearly_seasonality**: true if annual patterns expected
- **weekly_seasonality**: true if weekly patterns expected (for daily data)
- **daily_seasonality**: false (usually too granular)

## Forecast Parameters:
- **periods**: Number of future periods to predict (30 for days, 12 for months, 4 for quarters)
- **freq**: 'D' for daily, 'W' for weekly, 'M' for monthly, 'Q' for quarterly

# Output Format

Respond with ONLY valid JSON (no markdown code blocks, no explanatory text):

{{
    "sql": "Complete T-SQL query with ds and y aliases",
    "prophet_args": {{
        "seasonality_mode": "multiplicative",
        "yearly_seasonality": true,
        "weekly_seasonality": false
    }},
    "make_future_dataframe_args": {{
        "periods": 90,
        "freq": "D"
    }}
}}

# Example

Question: "Predict next quarter sales for Orange Lake"

Output:
{{
    "sql": "SELECT CAST(dd.TheDate AS DATE) AS ds, SUM(fsc.SalesVolume) AS y FROM edw.FactSalesContract fsc INNER JOIN edw.DimSalesLocation dsl ON fsc.DimSalesLocationSK = dsl.DimSalesLocationSK INNER JOIN edw.DimDate dd ON fsc.DimContractDateSK = dd.DimDateSK WHERE dsl.SiteName = 'Orange Lake' AND fsc.IncludeInSales = 1 AND dd.TheDate >= DATEADD(YEAR, -2, GETDATE()) GROUP BY dd.TheDate ORDER BY dd.TheDate",
    "prophet_args": {{"seasonality_mode": "multiplicative", "yearly_seasonality": true}},
    "make_future_dataframe_args": {{"periods": 90, "freq": "D"}}
}}

Now generate the plan for the user's question."""

        response = llm.invoke([HumanMessage(content=plan_prompt)]).content
        logger.info(f"LLM Response length: {len(response)}")
        logger.info(f"LLM Response (first 500 chars): {response[:500]}")
        
        if not response or not response.strip():
            return json.dumps({'error': 'LLM returned empty response'})
        
        # Try to extract JSON if wrapped in markdown
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
        if json_match:
            response = json_match.group(1)
            logger.info("Extracted JSON from markdown code block")
        
        # Try to find JSON object in response
        if not response.strip().startswith('{'):
            json_obj_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_obj_match:
                response = json_obj_match.group(0)
                logger.info("Extracted JSON object from text")
        
        try:
            plan = json.loads(response)
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            logger.error(f"Failed to parse response: {response[:1000]}")
            return json.dumps({'error': f'Failed to parse LLM response as JSON: {str(e)}'})
        
        logger.info(f"Plan: {plan}")
        
        # Step 2: Execute SQL via shared tool for consistency
        sql_query = plan.get('sql', '')
        if not sql_query or not isinstance(sql_query, str):
            logger.error(f"Invalid SQL in plan. Type: {type(sql_query)}, Value: {sql_query}")
            return json.dumps({'error': f'Invalid SQL query in plan: {type(sql_query)}'})

        sql_query = str(sql_query).strip()
        logger.info(f"Executing SQL (via tool): {sql_query[:200]}...")

        exec_result_raw = execute_sql_tool(sql_query)
        try:
            exec_result = json.loads(exec_result_raw)
        except Exception as e:
            logger.error(f"Failed to parse execute_sql_tool result: {e} :: {exec_result_raw[:300]}")
            return json.dumps({'error': 'Failed to execute SQL'})

        if exec_result.get('error'):
            return json.dumps({'error': exec_result['error']})

        df = pd.DataFrame(exec_result.get('data') or [])
        if df.empty:
            return json.dumps({'error': 'No historical data available'})

        # Ensure correct dtypes for Prophet: ds as datetime, y as numeric
        if 'ds' not in df.columns or 'y' not in df.columns:
            logger.error(f"Expected columns ['ds','y'] not found. Columns present: {list(df.columns)}")
            return json.dumps({'error': "Forecasting requires columns 'ds' and 'y'"})

        # Parse datetime and numeric values
        df['ds'] = pd.to_datetime(df['ds'], errors='coerce')
        df['y'] = pd.to_numeric(df['y'], errors='coerce')
        # Drop invalid rows
        before_drop = len(df)
        df = df.dropna(subset=['ds', 'y'])
        after_drop = len(df)
        if after_drop == 0:
            return json.dumps({'error': 'No valid historical points after cleaning'})
        if after_drop < before_drop:
            logger.info(f"Dropped {before_drop - after_drop} invalid rows during dtype coercion")

        # Sort by date to ensure chronological order
        df = df.sort_values('ds')

        logger.info(f"Historical data: {len(df)} rows")
        
        # Step 3: Train Prophet and forecast
        prophet_args = plan.get('prophet_args', {})
        future_args = plan.get('make_future_dataframe_args', {'periods': 30, 'freq': 'D'})
        
        model = Prophet(**prophet_args)
        model.fit(df[['ds', 'y']])
        
        future = model.make_future_dataframe(
            periods=future_args['periods'],
            freq=future_args['freq'],
            include_history=True
        )
        forecast = model.predict(future)
        
        # Prepare results
        result_df = forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].copy()
        result_df = result_df.rename(columns={
            'ds': 'Date',
            'yhat': 'Forecast',
            'yhat_lower': 'Lower_Bound',
            'yhat_upper': 'Upper_Bound'
        })
        
        # Merge with actuals
        df_renamed = df.rename(columns={'ds': 'Date', 'y': 'Actual'})
        result_df = result_df.merge(df_renamed[['Date', 'Actual']], on='Date', how='left')
        
        # Calculate metrics
        mask = result_df['Actual'].notna()
        if mask.sum() > 0:
            y_true = result_df.loc[mask, 'Actual'].values
            y_pred = result_df.loc[mask, 'Forecast'].values
            mape = np.mean(np.abs((y_true - y_pred) / np.maximum(1e-9, np.abs(y_true)))) * 100
            smape = np.mean(2.0 * np.abs(y_pred - y_true) / (np.maximum(1e-9, np.abs(y_true) + np.abs(y_pred)))) * 100
        else:
            mape, smape = None, None
        
        # Convert Timestamp objects to strings BEFORE generating insights
        result_df['Date'] = result_df['Date'].dt.strftime('%Y-%m-%d')
        
        # Generate insights
        insight_prompt = f"""# Task
Analyze the time-series forecast results and provide actionable business insights.

# Context

## Original Question
{question}

## Forecast Results (Last 10 Days)
{result_df.tail(10).to_dict()}

## Model Performance
- MAPE (Mean Absolute Percentage Error): {mape:.2f}% if mape else 'N/A'
- Lower MAPE = Better accuracy (Good: <10%, Acceptable: 10-20%, Poor: >20%)

# Instructions

Provide a structured business analysis with:

1. **Key Findings** (2-3 bullet points)
   - Overall trend direction (increasing/decreasing/stable)
   - Magnitude of change (percentage or absolute values)
   - Notable patterns or anomalies

2. **Business Implications** (2-3 bullet points)
   - What this means for operations
   - Resource planning considerations
   - Risk factors or opportunities

3. **Recommendations** (2-3 actionable items)
   - Specific actions to take
   - Timeline for implementation
   - Expected outcomes

4. **Model Reliability**
   - Comment on forecast confidence based on MAPE
   - Suggest data improvements if accuracy is poor

# Output Format

Provide clear, concise insights in business language (avoid technical jargon). Focus on actionable recommendations."""

        insights = llm.invoke([HumanMessage(content=insight_prompt)]).content
        
        logger.info("Forecast completed successfully")
        logger.info("=" * 80)
        
        return json.dumps({
            'success': True,
            'forecast_data': result_df.to_dict(orient='records'),
            'model_metrics': {'MAPE': round(mape, 2) if mape else None, 'sMAPE': round(smape, 2) if smape else None},
            'insights': insights,
            'sql_query': plan['sql']
        })
        
    except Exception as e:
        logger.error(f"Forecast tool failed: {str(e)}")
        return json.dumps({'error': str(e)})
