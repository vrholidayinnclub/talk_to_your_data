import os
from dotenv import load_dotenv

load_dotenv()

AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION")

ODBC_DRIVER = os.getenv("ODBC_DRIVER")
ODBC_SERVER_NAME = os.getenv("ODBC_SERVER_NAME")
ODBC_DATABASE_NAME = os.getenv("ODBC_DATABASE_NAME")
ODBC_AUTHENTICATION = os.getenv("ODBC_AUTHENTICATION")

glossary_file_path=os.getenv("glossary_file_path")
conn_str = os.getenv("conn_str")

sql_timeout = int(os.getenv("sql_timeout"))

TABLES = os.getenv("TABLES")

RELATIONSHIPS = os.getenv("RELATIONSHIPS")