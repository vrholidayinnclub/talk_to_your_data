# 🚀 Quick Start Guide - TTYD v2.0

## ⚡ 30-Second Start

```bash
# Run enhanced CLI with all features
python cli_enhanced.py
```

---

## 🎯 Core Features (What You Can Do Now)

### 1. Ask Questions + Get Charts 📊
```python
from agent.general_agent import GeneralAgent

agent = GeneralAgent()
result = agent.run("What are the top 5 resorts by sales?")

print(result['answer'])        # Natural language answer
print(result['chart_type'])    # 'bar', 'line', 'pie', etc.
print(result['chart_specs'])   # Plotly config (ready to render)
print(result['data'])           # Raw data
```

### 2. Approve SQL Before Execution ✅
```python
# Enable approval
result = agent.run(
    "Show all customer emails",
    require_approval=True
)

# Review SQL
if result['status'] == 'awaiting_approval':
    print(result['sql_query'])  # Review before execution
    
    # Approve and execute
    final = agent.execute_approved_sql(
        sql_query=result['sql_query'],
        question=result['question']
    )
```

### 3. Have Conversations with Memory 💾
```python
import uuid

session_id = str(uuid.uuid4())[:8]

# First question
agent.run("What are sales for Orange Lake?", session_id=session_id)

# Follow-up (remembers context!)
agent.run("What about South Beach?", session_id=session_id)

# View history
from utils.memory import get_memory
history = get_memory().get_session_history(session_id)
```

### 4. Get Rich Results 📈
```python
result = agent.run("What are the top 5 resorts?")

# Everything you need in one response:
result['status']          # 'success'
result['answer']          # Natural language answer
result['data']            # Raw data (list of dicts)
result['row_count']       # Number of rows
result['columns']         # Column names
result['chart_type']      # Chart type
result['chart_specs']     # Plotly configuration
result['chart_insights']  # Insights about the chart
result['sql_query']       # SQL that was executed
result['iterations']      # Agent iterations
```

---

## 📋 CLI Commands

```bash
# Start enhanced CLI
python cli_enhanced.py

# Commands:
> What are the top 5 resorts?          # Ask question
> approval on                          # Enable SQL approval
> approval off                         # Disable SQL approval
> memory                               # View conversation history
> clear                                # Clear current session
> help                                 # Show help
> quit                                 # Exit
```

---

## 🎨 Example Workflows

### **Workflow 1: Quick Analysis**
```python
agent = GeneralAgent()
result = agent.run("Show me monthly sales trends")

# Use in your app:
import plotly.graph_objects as go
fig = go.Figure(result['chart_specs'])
fig.show()  # Display chart
```

### **Workflow 2: Secure Data Access**
```python
# Always require approval for sensitive queries
result = agent.run(
    "Show customer personal data",
    require_approval=True
)

# User must approve before execution
```

### **Workflow 3: Multi-Turn Conversation**
```python
session = str(uuid.uuid4())[:8]

# Build context over multiple questions
agent.run("What are our top products?", session_id=session)
agent.run("Which regions buy them?", session_id=session)
agent.run("What's the trend?", session_id=session)

# Each question uses context from previous
```

---

## 📊 What You Get Back

### **Standard Query**
```json
{
  "status": "success",
  "answer": "The top 5 resorts are Orange Lake ($270.5M)...",
  "data": [{"SiteName": "Orange Lake", "TotalSales": 270536845.15}, ...],
  "row_count": 5,
  "chart_type": "bar",
  "chart_specs": {
    "data": [{...}],
    "layout": {...}
  },
  "chart_insights": "Orange Lake leads significantly...",
  "iterations": 2
}
```

### **Approval Required**
```json
{
  "status": "awaiting_approval",
  "sql_query": "SELECT * FROM Customers WHERE...",
  "question": "Show all customers",
  "message": "Please review and approve the SQL query"
}
```

### **Error**
```json
{
  "status": "error",
  "error": "Table not found: InvalidTable",
  "sql_query": "SELECT * FROM InvalidTable"
}
```

---

## 🔧 Configuration

### **Enable/Disable Features**

```python
# Approval workflow
result = agent.run(question, require_approval=True)   # Enable
result = agent.run(question, require_approval=False)  # Disable

# Memory/Context
result = agent.run(question, session_id="abc123")     # Enable
result = agent.run(question, session_id=None)         # Disable
```

### **Memory Location**

Default: `data/memory/`

Change:
```python
from utils.memory import ConversationMemory
memory = ConversationMemory(storage_dir="custom/path")
```

---

## 🎯 Common Use Cases

### **1. Business Dashboard**
```python
# Get data + chart in one call
result = agent.run("Show monthly revenue trends")

# Render in dashboard
display_chart(result['chart_specs'])
display_answer(result['answer'])
display_data_table(result['data'])
```

### **2. Data Exploration**
```python
session = "exploration_001"

# Ask series of questions
agent.run("What are our top products?", session_id=session)
agent.run("Show me by region", session_id=session)
agent.run("What's the growth rate?", session_id=session)

# Each builds on previous context
```

### **3. Secure Querying**
```python
# Always require approval
result = agent.run(
    user_question,
    require_approval=True
)

if result['status'] == 'awaiting_approval':
    # Show SQL to admin
    # Get approval
    # Execute
    pass
```

### **4. Automated Reporting**
```python
# Generate reports with charts
questions = [
    "What are top 5 resorts by sales?",
    "Show monthly sales trends",
    "Which products are growing fastest?"
]

report = []
for q in questions:
    result = agent.run(q)
    report.append({
        'question': q,
        'answer': result['answer'],
        'chart': result['chart_specs'],
        'data': result['data']
    })

# Export report
```

---

## 📚 Documentation

- **`NEW_FEATURES.md`** - Detailed feature documentation
- **`IMPLEMENTATION_SUMMARY.md`** - Implementation status
- **`HOW_IT_WORKS.md`** - System architecture
- **`README.md`** - Project overview

---

## ✅ Quick Test

```python
# Test all features in 30 seconds
from agent.general_agent import GeneralAgent
from utils.memory import get_memory
import uuid

agent = GeneralAgent()
session = str(uuid.uuid4())[:8]

# 1. Chart generation
r1 = agent.run("What are the top 5 resorts?")
assert 'chart_type' in r1
print("✅ Charts work!")

# 2. Approval workflow
r2 = agent.run("Show customers", require_approval=True)
assert r2['status'] == 'awaiting_approval'
print("✅ Approval works!")

# 3. Memory
r3 = agent.run("What are sales?", session_id=session)
history = get_memory().get_session_history(session)
assert len(history) == 1
print("✅ Memory works!")

# 4. Enhanced return
assert 'data' in r1 and 'chart_specs' in r1
print("✅ Enhanced return works!")

print("\n🎉 All features working!")
```

---

## 🚀 Next Steps

1. **Try the enhanced CLI:** `python cli_enhanced.py`
2. **Read detailed docs:** `NEW_FEATURES.md`
3. **Integrate into your app:** Use the examples above
4. **Customize:** Adjust prompts, add features, extend tools

---

*TTYD v2.0 - Now with Charts, Approval, Memory, and Enhanced Returns!* 🎉
