"""
SQL Execution Tool
Executes T-SQL queries and returns results as JSON.
"""

import json
import logging
import pandas as pd
import pyodbc
from decimal import Decimal
from datetime import date, datetime

from utils.context import conn_str

logger = logging.getLogger(__name__)


def execute_sql_tool(sql_query: str) -> str:
    """
    Execute SQL query and return results as JSON.
    
    Args:
        sql_query: T-SQL query string
        
    Returns:
        JSON string with DataFrame data
    """
    logger.info("=" * 80)
    logger.info("TOOL: execute_sql [UPDATED VERSION]")
    
    # Defensive: ensure sql_query is a string
    if not isinstance(sql_query, str):
        logger.warning(f"sql_query is not a string. Type: {type(sql_query)}, Value: {sql_query}")
        sql_query = str(sql_query)
    
    logger.info(f"SQL: {sql_query[:200]}...")
    
    try:
        # Debug connection string
        logger.info(f"Connection string type: {type(conn_str)}")
        logger.info(f"Connection string (first 100 chars): {str(conn_str)[:100]}")
        
        if not conn_str or conn_str == "None" or "None" in str(conn_str):
            logger.error("Invalid connection string - contains None values")
            return json.dumps({'error': 'Database connection not configured properly'})
        
        with pyodbc.connect(conn_str) as conn:
            cur = conn.cursor()
            cur.execute(sql_query)
            
            if cur.description is None:
                return json.dumps({'error': 'No results'})
            
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
            df = pd.DataFrame.from_records(rows if rows else [], columns=cols).head(1000)
            
            # Convert Decimal, date, datetime and other non-serializable types to native Python types
            for col in df.columns:
                if df[col].dtype == 'object':
                    # Convert Decimal to float, date/datetime to string
                    def convert_value(x):
                        if isinstance(x, Decimal):
                            return float(x)
                        elif isinstance(x, (date, datetime)):
                            return x.isoformat()
                        return x
                    df[col] = df[col].apply(convert_value)
                elif df[col].dtype == 'datetime64[ns]':
                    # Convert pandas datetime to ISO string
                    df[col] = df[col].dt.strftime('%Y-%m-%d')
            
            logger.info(f"Rows fetched: {len(df)}")
            logger.info("=" * 80)
            
            return json.dumps({
                'success': True,
                'data': df.to_dict(orient='records'),
                'columns': cols,
                'row_count': len(df)
            })
            
    except Exception as e:
        logger.error(f"SQL execution failed: {str(e)}")
        return json.dumps({'error': str(e)})
