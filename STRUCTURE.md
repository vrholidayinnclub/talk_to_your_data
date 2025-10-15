# Project Structure

## Overview
Clean, modular architecture following best practices for maintainability and scalability.

## Directory Layout

```
talk_to_your_data/
│
├── agent/                      # AI Agent (Brain of the system)
│   ├── __init__.py
│   └── general_agent.py       # Orchestrates tool selection and execution
│
├── tools/                      # Modular Tools (One file per tool)
│   ├── __init__.py            # Tool exports
│   ├── execute_sql.py         # SQL query execution
│   ├── forecast_tool.py       # Time-series forecasting (Prophet)
│   ├── classification_tool.py # ML classification (XGBoost)
│   └── display_tool.py        # Data formatting and display
│
├── utils/                      # Shared Utilities
│   ├── __init__.py
│   ├── config.py              # Environment configuration
│   └── context.py             # Database context & metadata
│
├── ui/                         # Streamlit UI Components
│   ├── __init__.py
│   ├── components.py          # Reusable UI widgets
│   └── session.py             # Session state management
│
├── data/                       # Data Assets
│   └── Glossary.xlsx          # Database glossary
│
├── app.py                      # Streamlit web app entry point
├── cli_test.py                # CLI testing interface
├── requirements.txt           # Python dependencies
├── .env                       # Environment variables (gitignored)
├── .gitignore                 # Git ignore rules
└── README.md                  # Documentation
```

## Design Principles

### 1. **Single Responsibility**
- Each file has one clear purpose
- Tools are independent and self-contained
- Easy to understand and modify

### 2. **Modularity**
- Tools can be added/removed without affecting others
- Clear separation of concerns
- Reusable components

### 3. **Scalability**
- Easy to add new tools
- Simple to extend functionality
- Clean import structure

### 4. **Maintainability**
- Consistent naming conventions
- Clear file organization
- Well-documented code

## Import Structure

### From Agent
```python
from tools import execute_sql_tool, forecast_tool, classification_tool
from utils.config import AZURE_OPENAI_*
from utils.context import load_glossary, get_table_schema
```

### From Tools
```python
from utils.config import *
from utils.context import conn_str, load_glossary
from tools.execute_sql import execute_sql_tool  # Tools can call each other
```

### From UI
```python
from agent.general_agent import GeneralAgent
from ui import render_header, render_message_history
```

## Tool Architecture

Each tool follows this pattern:

1. **Import dependencies** - Only what's needed
2. **Define helper functions** - Tool-specific utilities
3. **Main tool function** - Single entry point
4. **Error handling** - Comprehensive try/catch
5. **Logging** - Detailed execution logs
6. **Return JSON** - Standardized output format

## Benefits of This Structure

✅ **Easy Navigation** - Find any component quickly  
✅ **Clear Dependencies** - Understand relationships  
✅ **Simple Testing** - Test tools independently  
✅ **Team Collaboration** - Multiple developers can work simultaneously  
✅ **Professional** - Industry-standard organization  

## Next Steps

1. Recreate `agent/general_agent.py` with proper imports
2. Test each tool independently
3. Verify CLI and web UI functionality
4. Add unit tests for each tool
