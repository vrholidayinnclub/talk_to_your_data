from config import *
import pandas as pd
import pyodbc
from utils_ttyd import *
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TABLES = ["edw.DimCustomer",
        "edw.FactTour",
        "edw.FactSalesContract",
        "edw.DimDate",
        "edw.DimSalesLocation"]

RELATIONSHIPS = """ All joins (Join on SK keys per specifics + guidelines):
                    - DimCustomerSK: DimCustomer, FactTour, FactSalesContract
                    - DimLocationSK: DimSalesLocation, FactTour
                    - DimSalesLocationSK: DimSalesLocation, FactTour, FactSalesContract
                    - DimCampaignHierarchySK: FactTour, FactSalesContract
                    - DimTourSK: FactTour, FactSalesContract

                    Specific Join Relationships:
                    - FactTour joins FactSalesContract using ContractSK (preferred for accurate joins)
                    - Avoid joining fact tables directly via DimCustomerSK unless ContractSK is unavailable
                    - Use DimDate and DimSalesLocation only as dimensions
                """

conn_str = f"Driver={ODBC_DRIVER};\
            Server={ODBC_SERVER_NAME};\
            Database={ODBC_DATABASE_NAME};\
            Authentication={ODBC_AUTHENTICATION}"

# conn_str = "Driver={ODBC Driver 17 for SQL Server};\
#             Server=dc03-azsqldb03.database.windows.net;\
#             Database=PolarisQA;\
#             Authentication=ActiveDirectoryIntegrated"

def load_glossary() -> str:
    """
    Loads data related to the Database
    """
    df = pd.read_excel(glossary_file_path)
    df = df.dropna(subset=["Field", "Description", "Table"])
    return "\n".join(f"- {row['Table']}.{row['Field']}: {row['Description']}" for _, row in df.iterrows())

def connect_to_sql():
    with pyodbc.connect(conn_str) as conn:
        return conn.cursor()

def get_table_schema(cur) -> str:
    blocks = []
    for fqtn in TABLES:
        try:
            schema, name = fqtn.split(".")
            cur.execute(f"""
                SELECT COLUMN_NAME, DATA_TYPE
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = {schema} AND TABLE_NAME = {name}
                ORDER BY ORDINAL_POSITION""")
            cols = cur.fetchall()
            lines = [f"- {col} ({type})" for col, type in cols]
            blocks.append(f"Table: {fqtn}\n" + "\n".join(lines))
        except Exception as e:
            blocks.append(f"Table: {fqtn}\n- ⚠️ Unable to read columns: {e}")
    return "\n\n".join(blocks)

def get_table_sample_data(cur, rows=5) -> str:
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
    logger.info(f"Connection string: {conn_str}")
    glossary = load_glossary()
    tbl_schema, sample_data = get_table_metadata()
    return glossary, tbl_schema, sample_data