from utils.config import *
import pandas as pd
import pyodbc
import logging
import os
from dotenv import load_dotenv

# Ensure .env is loaded
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)



# TABLES and RELATIONSHIPS are now imported from config.py

def get_connection_string():
    """Get database connection string from env or build from components."""
    # Use connection string from .env if available, otherwise build from components
    conn_str = os.getenv("conn_str")
    
    if not conn_str:
        # Build from individual components
        from config import ODBC_DRIVER, ODBC_SERVER_NAME, ODBC_DATABASE_NAME, ODBC_AUTHENTICATION
        conn_str = f"Driver={ODBC_DRIVER};Server={ODBC_SERVER_NAME};Database={ODBC_DATABASE_NAME};Authentication={ODBC_AUTHENTICATION}"
    
    return conn_str

# For backward compatibility, create module-level variable
conn_str = get_connection_string()
logger.info(f"Connection string initialized: {conn_str[:50]}..." if conn_str else "Connection string is None")


def load_glossary() -> str:
    """
    Loads data related to the Database
    """
    logger.info("Loading Glossary...")
    df = pd.read_excel(glossary_file_path)
    df = df.dropna(subset=["Field", "Description", "Table"])
    return "\n".join(f"- {row['Table']}.{row['Field']}: {row['Description']}" for _, row in df.iterrows())

def connect_to_sql():
    with pyodbc.connect(conn_str) as conn:
        return conn.cursor()

def get_table_schema(cur) -> str:
    logger.info("Loading Table Schema...")
    blocks = []
    for fqtn in TABLES:
        try:
            schema, name = fqtn.split(".")
            cur.execute(
                """
                SELECT COLUMN_NAME, DATA_TYPE
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?
                ORDER BY ORDINAL_POSITION
                """,
                (schema, name)
            )
            cols = cur.fetchall()
            lines = [f"- {col} ({type})" for col, type in cols]
            blocks.append(f"Table: {fqtn}\n" + "\n".join(lines))
        except Exception as e:
            blocks.append(f"Table: {fqtn}\n- ⚠️ Unable to read columns: {e}")
    return "\n\n".join(blocks)

def get_table_sample_data(cur, rows=5) -> str:
    logger.info("Loading sample data...")
    blocks = []
    for fqtn in TABLES:
        try:
            cur.execute(f"SELECT TOP {rows} * FROM {fqtn}")
            cols = [d[0] for d in cur.description]
            rows_ = cur.fetchall()
            if not rows_:
                blocks.append(f"Samples: {fqtn}\n- (no rows)\n")
                continue
            df = pd.DataFrame.from_records(rows_, columns=cols)
            lines = []
            for c in cols:
                vals = df[c].dropna().astype(str).unique()[:3]
                if len(vals) > 0:
                    lines.append(f"- {c}: {list(vals)}")
            blocks.append(f"Samples: {fqtn}\n" + "\n".join(lines))
        except Exception as e:
            blocks.append(f"Samples: {fqtn}\n- ⚠️ Unable to sample: {e}")
    return "\n\n".join(blocks)

def get_table_metadata():
    with pyodbc.connect(conn_str) as conn:
        cur = conn.cursor()
        schema = get_table_schema(cur)
        sample_data = get_table_sample_data(cur)
    return schema, sample_data

def initialize():
    logger.info("Initializing Agent...")
    glossary = load_glossary()
    tbl_schema, sample_data = get_table_metadata()
    relationships = RELATIONSHIPS
    return glossary, tbl_schema, sample_data, relationships


