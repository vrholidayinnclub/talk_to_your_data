# 🧠 How TTYD Works - Complete Flow Explanation

## 📋 Table of Contents
1. [System Initialization](#system-initialization)
2. [Question Processing Flow](#question-processing-flow)
3. [Tool Execution Details](#tool-execution-details)
4. [Example Walkthrough](#example-walkthrough)
5. [Architecture Diagram](#architecture-diagram)

---

## 🚀 System Initialization

### When You Start the System (`cli_test.py` or `app.py`)

```python
# Step 1: Load Environment Variables
- Reads .env file
- Gets Azure OpenAI credentials
- Gets SQL Server connection details

# Step 2: Initialize Agent
agent = GeneralAgent()
```

### What Happens During Agent Initialization?

```
┌─────────────────────────────────────────────────────────────┐
│                    AGENT INITIALIZATION                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. Create Azure OpenAI Client                              │
│     - Connects to: gpt-4o deployment                        │
│     - Temperature: 0 (deterministic)                        │
│                                                              │
│  2. Load Database Context                                   │
│     ├─ Glossary.xlsx → Business terms & definitions         │
│     ├─ Table Schema → All tables, columns, data types       │
│     └─ Relationships → Foreign keys, joins                  │
│                                                              │
│  3. Register Tools                                          │
│     ├─ execute_sql_tool     (SQL queries)                   │
│     ├─ forecast_tool        (Prophet forecasting)           │
│     ├─ classification_tool  (XGBoost ML)                    │
│     └─ display_data_tool    (Data formatting)               │
│                                                              │
│  ✅ Agent Ready!                                            │
└─────────────────────────────────────────────────────────────┘
```

**Time:** ~5-10 seconds  
**Memory:** Loads glossary, schema, relationships into RAM

---

## 🔄 Question Processing Flow

### When You Ask: "Predict next quarter sales for 'Orange Lake'"

```
┌──────────────────────────────────────────────────────────────────┐
│                        ITERATION LOOP                             │
│                    (Max 5 iterations)                             │
└──────────────────────────────────────────────────────────────────┘

ITERATION 1:
┌──────────────────────────────────────────────────────────────────┐
│ Step 1: Build Context                                            │
├──────────────────────────────────────────────────────────────────┤
│ System Prompt:                                                   │
│ "You are a business analyst with these tools:                    │
│  - execute_sql_tool: For data queries                            │
│  - forecast_tool: For predictions (USE THIS FOR FORECASTING!)    │
│  - classification_tool: For customer segmentation                │
│                                                                   │
│ Database Context:                                                │
│  - Glossary: [business terms]                                    │
│  - Schema: [all tables and columns]                              │
│  - Relationships: [table joins]                                  │
│                                                                   │
│ User Question: Predict next quarter sales for 'Orange Lake'      │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│ Step 2: Agent Reasoning (LLM Call #1)                            │
├──────────────────────────────────────────────────────────────────┤
│ LLM Analyzes:                                                    │
│ ✓ Keywords: "Predict", "next quarter", "sales"                  │
│ ✓ Intent: Time-series forecasting                               │
│ ✓ Tool Selection: forecast_tool (handles everything)            │
│                                                                   │
│ LLM Returns JSON:                                                │
│ {                                                                │
│   "reasoning": "User wants to predict future sales, this is     │
│                 a forecasting task",                             │
│   "decision": "use_tool",                                        │
│   "tool_name": "forecast_tool",                                  │
│   "tool_input": "Predict next quarter sales for 'Orange Lake'"  │
│ }                                                                │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│ Step 3: Execute forecast_tool                                    │
├──────────────────────────────────────────────────────────────────┤
│ Tool receives: "Predict next quarter sales for 'Orange Lake'"   │
│                                                                   │
│ Tool does 5 sub-steps:                                           │
│                                                                   │
│ 3.1 Plan Generation (LLM Call #2)                               │
│     ├─ Analyzes question                                         │
│     ├─ Generates SQL query                                       │
│     ├─ Sets Prophet parameters                                   │
│     └─ Returns JSON plan                                         │
│                                                                   │
│ 3.2 Execute SQL                                                  │
│     ├─ Runs generated SQL query                                  │
│     ├─ Fetches historical sales data                             │
│     └─ Returns ~1000 rows                                        │
│                                                                   │
│ 3.3 Train Prophet Model                                          │
│     ├─ Prepares data (ds, y columns)                             │
│     ├─ Trains time-series model                                  │
│     └─ Generates forecast                                        │
│                                                                   │
│ 3.4 Calculate Metrics                                            │
│     ├─ MAPE (Mean Absolute Percentage Error)                     │
│     └─ sMAPE (Symmetric MAPE)                                    │
│                                                                   │
│ 3.5 Generate Insights (LLM Call #3)                             │
│     ├─ Analyzes forecast results                                 │
│     ├─ Identifies trends                                         │
│     └─ Provides recommendations                                  │
│                                                                   │
│ Tool returns JSON:                                               │
│ {                                                                │
│   "success": true,                                               │
│   "forecast_data": [...90 days of predictions...],              │
│   "model_metrics": {"MAPE": 15.2, "sMAPE": 12.8},              │
│   "insights": "Sales expected to grow 12%...",                   │
│   "sql_query": "SELECT..."                                       │
│ }                                                                │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│ Step 4: Agent Processes Result                                   │
├──────────────────────────────────────────────────────────────────┤
│ Agent receives tool output                                       │
│ Adds to conversation history                                     │
└──────────────────────────────────────────────────────────────────┘

ITERATION 2:
┌──────────────────────────────────────────────────────────────────┐
│ Step 5: Final Answer Generation (LLM Call #4)                    │
├──────────────────────────────────────────────────────────────────┤
│ LLM has:                                                         │
│ - Original question                                              │
│ - Tool results (forecast data + insights)                        │
│                                                                   │
│ LLM Returns:                                                     │
│ {                                                                │
│   "reasoning": "I have the forecast results",                    │
│   "decision": "answer",                                          │
│   "answer": "Based on the forecast for Orange Lake:             │
│              - Next quarter sales: $5.2M - $6.5M                 │
│              - Expected growth: 12%                              │
│              - Confidence: 85%                                   │
│              Recommendations: ..."                               │
│ }                                                                │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│ ✅ DONE - Return to User                                         │
└──────────────────────────────────────────────────────────────────┘
```

**Total Time:** ~15-30 seconds  
**LLM Calls:** 4 (1 routing + 1 plan + 1 insights + 1 final answer)  
**Iterations:** 2

---

## 🛠️ Tool Execution Details

### Tool 1: `execute_sql_tool`

**Purpose:** Execute SQL queries and return data

```python
Input:  SQL query string
        "SELECT TOP 5 SiteName, SUM(SalesVolume) 
         FROM edw.FactSalesContract 
         GROUP BY SiteName"

Process:
1. Connect to SQL Server
2. Execute query
3. Fetch results (max 1000 rows)
4. Convert data types (Decimal → float, datetime → string)
5. Return JSON

Output: {
  "success": true,
  "data": [{...}, {...}],
  "columns": ["SiteName", "TotalSales"],
  "row_count": 5
}
```

**When to use:** Counts, aggregations, top N, percentages, current state

---

### Tool 2: `forecast_tool`

**Purpose:** Time-series forecasting with Prophet

```python
Input:  User question (natural language)
        "Predict next quarter sales for 'Orange Lake'"

Process:
1. LLM generates SQL + Prophet config
   └─ Returns: {sql, prophet_args, forecast_periods}

2. Execute SQL via execute_sql_tool
   └─ Gets historical data

3. Train Prophet model
   ├─ Fit on historical data
   └─ Generate future predictions

4. Calculate accuracy metrics
   └─ MAPE, sMAPE

5. LLM generates business insights
   └─ Analyzes trends, provides recommendations

Output: {
  "success": true,
  "forecast_data": [90 days of predictions],
  "model_metrics": {"MAPE": 15.2},
  "insights": "Business analysis...",
  "sql_query": "SELECT..."
}
```

**When to use:** Predict, forecast, project, estimate future values

---

### Tool 3: `classification_tool`

**Purpose:** ML customer classification with XGBoost

```python
Input:  User question (natural language)
        "Which customers are most likely to take tours?"

Process:
1. LLM generates SQL + XGBoost config
   └─ Returns: {sql, target_col, features, xgb_params}

2. Execute SQL via execute_sql_tool
   └─ Gets customer data

3. Preprocess data
   ├─ Handle missing values
   └─ Encode categorical variables

4. Train XGBoost model
   ├─ Split train/test
   ├─ Fit classifier
   └─ Predict probabilities

5. Get top 100 customers
   └─ Ranked by probability

6. LLM generates insights
   └─ Targeting recommendations

Output: {
  "success": true,
  "predictions": [top 100 customers],
  "model_metrics": {"accuracy": 0.87},
  "insights": "Target these segments...",
  "sql_query": "SELECT..."
}
```

**When to use:** Customer segmentation, behavior prediction, targeting

---

### Tool 4: `display_data_tool`

**Purpose:** Format data for terminal display

```python
Input:  JSON data + title

Process:
1. Parse JSON
2. Convert to DataFrame
3. Format as table
4. Print to console

Output: Formatted table string
```

**When to use:** Present results in readable format

---

## 📊 Example Walkthrough

### Question: "What are the top 5 resorts by sales?"

```
┌─────────────────────────────────────────────────────────────┐
│ ITERATION 1                                                  │
├─────────────────────────────────────────────────────────────┤
│ Agent Reasoning:                                             │
│ - Keywords: "top 5", "resorts", "sales"                      │
│ - Intent: Data aggregation query                             │
│ - Tool: execute_sql_tool                                     │
│                                                              │
│ Agent Decision:                                              │
│ {                                                            │
│   "decision": "use_tool",                                    │
│   "tool_name": "execute_sql_tool",                           │
│   "tool_input": "SELECT TOP 5 SiteName,                      │
│                  SUM(SalesVolume) AS Total                   │
│                  FROM edw.FactSalesContract                  │
│                  JOIN edw.DimSalesLocation                   │
│                  ON ... GROUP BY SiteName                    │
│                  ORDER BY Total DESC"                        │
│ }                                                            │
│                                                              │
│ Tool Execution:                                              │
│ - Connects to SQL Server                                     │
│ - Executes query                                             │
│ - Returns 5 rows                                             │
│                                                              │
│ Tool Result:                                                 │
│ {                                                            │
│   "data": [                                                  │
│     {"SiteName": "Orange Lake", "Total": 270536845.15},     │
│     {"SiteName": "South Beach", "Total": 89986938.5},       │
│     ...                                                      │
│   ]                                                          │
│ }                                                            │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ ITERATION 2                                                  │
├─────────────────────────────────────────────────────────────┤
│ Agent Reasoning:                                             │
│ - I have the data                                            │
│ - Can provide final answer                                   │
│                                                              │
│ Agent Decision:                                              │
│ {                                                            │
│   "decision": "answer",                                      │
│   "answer": "Top 5 resorts by sales:                         │
│              1. Orange Lake: $270.5M                         │
│              2. South Beach Resort: $90.0M                   │
│              3. Desert Club: $XX.XM                          │
│              ..."                                            │
│ }                                                            │
└─────────────────────────────────────────────────────────────┘

✅ COMPLETE - 2 iterations, ~5 seconds
```

---

## 🏗️ Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE                           │
│                                                                  │
│  ┌──────────────────┐              ┌──────────────────┐        │
│  │   cli_test.py    │              │     app.py       │        │
│  │  (Terminal CLI)  │              │   (Streamlit)    │        │
│  └────────┬─────────┘              └────────┬─────────┘        │
│           │                                  │                   │
│           └──────────────┬───────────────────┘                   │
└───────────────────────────┼─────────────────────────────────────┘
                            │
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│                      AGENT LAYER                                 │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │              GeneralAgent (Brain)                          │ │
│  │  - Receives question                                       │ │
│  │  - Analyzes intent                                         │ │
│  │  - Selects appropriate tool                                │ │
│  │  - Manages conversation flow                               │ │
│  │  - Returns final answer                                    │ │
│  └────────────────────────────────────────────────────────────┘ │
│                            │                                     │
│           ┌────────────────┼────────────────┐                   │
│           │                │                │                   │
└───────────┼────────────────┼────────────────┼───────────────────┘
            ↓                ↓                ↓
┌─────────────────────────────────────────────────────────────────┐
│                       TOOLS LAYER                                │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│  │ SQL Tool     │  │Forecast Tool │  │Classification Tool   │ │
│  │              │  │              │  │                      │ │
│  │ - Execute    │  │ - Plan SQL   │  │ - Plan SQL           │ │
│  │   queries    │  │ - Train      │  │ - Train XGBoost      │ │
│  │ - Return     │  │   Prophet    │  │ - Predict            │ │
│  │   data       │  │ - Generate   │  │ - Rank customers     │ │
│  │              │  │   forecast   │  │                      │ │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────────────┘ │
│         │                 │                  │                  │
└─────────┼─────────────────┼──────────────────┼──────────────────┘
          │                 │                  │
          └─────────────────┼──────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│                    UTILITIES LAYER                               │
│                                                                  │
│  ┌──────────────────┐              ┌──────────────────┐        │
│  │  utils.context   │              │   utils.config   │        │
│  │  - Load glossary │              │   - Azure OpenAI │        │
│  │  - Get schema    │              │   - SQL Server   │        │
│  │  - Connect SQL   │              │   - Settings     │        │
│  └──────────────────┘              └──────────────────┘        │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│                    EXTERNAL SERVICES                             │
│                                                                  │
│  ┌──────────────────┐              ┌──────────────────┐        │
│  │  Azure OpenAI    │              │   SQL Server     │        │
│  │  (GPT-4o)        │              │   (PolarisPRD)   │        │
│  └──────────────────┘              └──────────────────┘        │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔑 Key Concepts

### 1. **Agent = Brain**
- Decides which tool to use
- Manages conversation flow
- Iterates until task is complete

### 2. **Tools = Hands**
- Execute specific tasks
- Self-contained and independent
- Return structured results

### 3. **Utilities = Support**
- Provide shared functionality
- Database connections
- Configuration management

### 4. **LLM = Reasoning Engine**
- Understands natural language
- Generates SQL queries
- Provides business insights

---

## ⚡ Performance Characteristics

| Question Type | Tool Used | Iterations | LLM Calls | Time |
|--------------|-----------|------------|-----------|------|
| Data Query | SQL | 2 | 2 | ~5s |
| Forecast | Forecast | 2 | 4 | ~20s |
| Classification | Classification | 2 | 4 | ~25s |
| Simple Answer | None | 1 | 1 | ~3s |

---

## 🎯 Summary

**The system works in 3 main phases:**

1. **Initialization** - Load context, register tools
2. **Reasoning Loop** - Agent analyzes → selects tool → executes → processes result
3. **Answer Generation** - Format and return final answer

**Key Design Principles:**
- ✅ Modular tools (easy to add/modify)
- ✅ Iterative reasoning (handles complex questions)
- ✅ Context-aware (uses database schema)
- ✅ Self-correcting (can retry on errors)

**The magic happens when:**
- Agent correctly identifies question type
- Selects the right tool
- Tool executes successfully
- LLM generates meaningful insights

---

*For more details, see:*
- `STRUCTURE.md` - Architecture overview
- `README.md` - Setup instructions
- `REFACTORING_COMPLETE.md` - Recent changes
