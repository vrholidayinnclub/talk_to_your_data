# Talk To Your Data (TTYD)

An intelligent business analytics system powered by Azure OpenAI that enables natural language querying, forecasting, and ML-driven insights from your SQL database.

## 🚀 Features

### Core Capabilities
- **Natural Language Queries** - Ask questions in plain English, get SQL-powered answers
- **Time-Series Forecasting** - Predict future trends using Prophet
- **Customer Classification** - ML-powered customer segmentation with XGBoost
- **Intelligent Routing** - Agent automatically selects the right tool for each question

### ✨ New Features (v2.0)
- **📊 Automatic Chart Generation** - Plotly visualizations generated automatically from query results
- **✅ Human Approval Workflow** - Review and approve SQL queries before execution
- **💾 Conversation Memory** - Context-aware follow-up questions with session persistence
- **📈 Enhanced Return Format** - Comprehensive results with data, charts, insights, and metadata

### Interfaces
- **Interactive UI** - Beautiful Streamlit interface for data exploration
- **Enhanced CLI** - Feature-rich terminal interface with approval workflow and memory
- **Standard CLI** - Simple terminal-based testing and debugging

## 📁 Project Structure

```
talk_to_your_data/
├── agent/                      # AI Agent implementation
│   ├── __init__.py
│   └── general_agent.py       # Main agent with tool routing logic
├── tools/                      # Agent tools (modular design)
│   ├── __init__.py            # Tool exports
│   ├── execute_sql.py         # SQL query execution
│   ├── forecast_tool.py       # Time-series forecasting (Prophet)
│   ├── classification_tool.py # ML classification (XGBoost)
│   ├── display_tool.py        # Data formatting and display
│   └── chart_tool.py          # Chart generation (NEW)
├── utils/                      # Utility modules
│   ├── __init__.py
│   ├── config.py              # Configuration management
│   ├── context.py             # Database context utilities
│   └── memory.py              # Conversation memory (NEW)
├── ui/                         # Streamlit UI components
│   ├── __init__.py
│   ├── components.py          # Reusable UI elements
│   └── session.py             # Session state management
├── data/                       # Data files
│   └── Glossary.xlsx          # Database glossary
├── app.py                      # Streamlit web application
├── cli_test.py                # Standard CLI testing interface
├── cli_enhanced.py            # Enhanced CLI with all features (NEW)
├── requirements.txt           # Python dependencies
├── .env                       # Environment variables (not in git)
├── .gitignore                 # Git ignore rules
├── NEW_FEATURES.md            # New features documentation (NEW)
└── README.md                  # This file
```

## ⚙️ Setup

### 1. Install Dependencies

```powershell
pip install -r requirements.txt
```

### 2. Configure Environment

Create a `.env` file (use `.env.template` as reference):

```env
# Azure OpenAI
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key
AZURE_OPENAI_API_VERSION=2023-07-01-preview

# SQL Server
ODBC_SERVER_NAME=your-server.database.windows.net
ODBC_DATABASE_NAME=your-database
ODBC_AUTHENTICATION=ActiveDirectoryIntegrated

# Application
glossary_file_path=./data/Glossary.xlsx
sql_timeout=60
```

### 3. Run the Application

**Web UI (Streamlit):**
```powershell
streamlit run app.py
```

**CLI Mode (Terminal):**
```powershell
python cli_test.py
```

## 🎯 Usage Examples

### Web UI
1. Open browser to `http://localhost:8501`
2. Type your question in the chat input
3. View results with visualizations

### CLI Mode
```
💬 Your Question: What is the percentage of active vs inactive contracts?
💬 Your Question: Predict next quarter sales for 'Orange Lake'
💬 Your Question: Which customers are most likely to take tours?
```

## 🏗️ Architecture

### Agent System
- **GeneralAgent** - Orchestrates tool selection and execution
- **Tool Routing** - Automatically chooses the right tool based on question type
- **Iterative Reasoning** - Multi-step problem solving with up to 5 iterations

### Tools
1. **execute_sql_tool** - Direct SQL queries for data retrieval
2. **forecast_tool** - Time-series forecasting with Prophet
3. **classification_tool** - ML classification with XGBoost
4. **answer_question** - General Q&A using RAG
5. **display_data** - Format and present results

## 🔧 Development

### Adding New Tools
1. Define tool function in `tools/agent_tools.py`
2. Register tool in `agent/general_agent.py`
3. Update tool descriptions for proper routing

### Testing
- Use `cli_test.py` for rapid testing without UI overhead
- Check logs for detailed agent reasoning and tool execution

## 📝 License

Internal use only - Holiday Inn Club Vacations
