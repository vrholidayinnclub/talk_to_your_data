#!/usr/bin/env python3
"""
CLI Test Interface for TTYD Agent System
Run this to test the agent flow in terminal without Streamlit UI
"""
import logging
import json
from agent.general_agent import GeneralAgent

# Configure detailed logging to see agent flow
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def print_separator(char="=", length=100):
    """Print a separator line"""
    print(char * length)

def print_result(result: dict):
    """Pretty print the agent result"""
    print_separator()
    print("📊 AGENT RESULT:")
    print_separator()
    
    # SQL Query
    if result.get("sql_query"):
        print("\n🔍 SQL Query Generated:")
        print("-" * 80)
        print(result["sql_query"])
        print("-" * 80)
    
    # Data
    if result.get("data"):
        print("\n📋 Data Retrieved:")
        print("-" * 80)
        data = result["data"]
        if isinstance(data, list) and len(data) > 0:
            # Print first few rows
            import pandas as pd
            df = pd.DataFrame(data)
            print(df.head(10).to_string())
            print(f"\n... Total rows: {len(data)}")
        else:
            print(data)
        print("-" * 80)
    
    # Answer/Insights
    if result.get("answer"):
        print("\n💡 Answer/Insights:")
        print("-" * 80)
        print(result["answer"])
        print("-" * 80)
    
    # Metrics
    if result.get("metrics") or result.get("model_metrics"):
        metrics = result.get("metrics") or result.get("model_metrics")
        print("\n📏 Metrics:")
        print("-" * 80)
        print(json.dumps(metrics, indent=2))
        print("-" * 80)
    
    # Errors
    if result.get("error"):
        print("\n❌ Error:")
        print("-" * 80)
        print(result["error"])
        print("-" * 80)

def main():
    """Main CLI loop"""
    print_separator("*")
    print("🤖 TTYD Agent System - CLI Test Interface")
    print_separator("*")
    print("\nThis interface lets you test the agent system in terminal.")
    print("You can see the complete flow of how the agent routes to different tools.\n")
    print("Commands:")
    print("  - Type your question to query the agent")
    print("  - Type 'quit' or 'exit' to stop")
    print("  - Type 'help' for example questions")
    print_separator()
    
    # Initialize agent
    print("\n⏳ Initializing General Agent...")
    try:
        agent = GeneralAgent()
        print("✅ Agent initialized successfully!\n")
    except Exception as e:
        print(f"❌ Failed to initialize agent: {e}")
        return
    
    # Main loop
    while True:
        print_separator("-")
        question = input("\n💬 Your Question: ").strip()
        
        if not question:
            continue
        
        if question.lower() in ['quit', 'exit', 'q']:
            print("\n👋 Goodbye!")
            break
        
        if question.lower() == 'help':
            print("\n📚 Example Questions:")
            print("  1. What is the percentage of active vs inactive contracts?")
            print("  2. Show me top 10 customers by sales volume")
            print("  3. Predict next quarter sales for 'Orange Lake'")
            print("  4. Which customers are most likely to take tours?")
            print("  5. What is the average sales volume by location?")
            continue
        
        # Process question
        print(f"\n🚀 Processing: '{question}'")
        print_separator()
        
        try:
            result = agent.run(question)
            print_result(result)
        except Exception as e:
            print(f"\n❌ Error processing question: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    main()
