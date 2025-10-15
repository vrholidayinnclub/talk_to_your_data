"""
Enhanced CLI Test Interface with All Features
Demonstrates: Chart Generation, Human Approval, Memory, Enhanced Return Format
"""

import sys
import uuid
from agent.general_agent import GeneralAgent
from utils.memory import get_memory
import json


def print_separator(char="=", length=100):
    """Print a separator line."""
    print(char * length)


def print_header():
    """Print CLI header."""
    print_separator("*")
    print("🚀 TTYD Agent System - Enhanced CLI Interface")
    print_separator("*")
    print()
    print("✨ NEW FEATURES:")
    print("  1. 📊 Automatic Chart Generation")
    print("  2. ✅ Human Approval for SQL Queries")
    print("  3. 💾 Conversation Memory")
    print("  4. 📈 Enhanced Return Format (data + charts + insights)")
    print_separator()


def print_result(result: dict):
    """Print formatted result."""
    print("\n" + "=" * 100)
    print("📊 RESULT")
    print("=" * 100)
    
    # Status
    status = result.get('status', 'unknown')
    print(f"\n🔹 Status: {status.upper()}")
    
    # Answer
    if 'answer' in result:
        print(f"\n💬 Answer:")
        print(f"   {result['answer']}")
    
    # Data summary
    if 'data' in result:
        row_count = result.get('row_count', len(result['data']))
        print(f"\n📋 Data: {row_count} rows returned")
        if result['data'] and len(result['data']) > 0:
            print(f"   Sample (first 3 rows):")
            for i, row in enumerate(result['data'][:3], 1):
                print(f"   {i}. {row}")
    
    # Chart info
    if 'chart_type' in result:
        print(f"\n📊 Chart: {result['chart_type'].upper()} chart generated")
        if 'chart_insights' in result:
            print(f"   Insights: {result['chart_insights']}")
    
    # SQL query
    if 'sql_query' in result:
        print(f"\n🔍 SQL Query:")
        print(f"   {result['sql_query'][:200]}...")
    
    # Metadata
    if 'iterations' in result:
        print(f"\n⚙️  Iterations: {result['iterations']}")
    
    # Error
    if 'error' in result:
        print(f"\n❌ Error: {result['error']}")
    
    print_separator()


def print_approval_request(result: dict):
    """Print SQL approval request."""
    print("\n" + "=" * 100)
    print("⚠️  SQL APPROVAL REQUIRED")
    print("=" * 100)
    print(f"\n💬 Question: {result.get('question')}")
    print(f"\n🔍 Generated SQL Query:")
    print("-" * 100)
    print(result.get('sql_query'))
    print("-" * 100)
    print(f"\n{result.get('message')}")
    print_separator()


def main():
    """Main CLI loop."""
    print_header()
    
    # Initialize agent
    print("⏳ Initializing Enhanced Agent...")
    agent = GeneralAgent()
    memory = get_memory()
    
    # Generate or use session ID
    session_id = str(uuid.uuid4())[:8]
    print(f"✅ Agent initialized successfully!")
    print(f"💾 Session ID: {session_id}")
    print_separator()
    
    # Show memory sessions
    sessions = memory.list_sessions()
    if sessions:
        print(f"\n📚 Found {len(sessions)} previous session(s):")
        for s in sessions[:5]:
            print(f"   - {s['session_id']}: {s['interaction_count']} interactions")
        print()
    
    # Main loop
    while True:
        print("\n💬 Your Question (or 'quit'/'exit'/'help'/'memory'/'approval on/off'): ", end="")
        question = input().strip()
        
        if not question:
            continue
        
        if question.lower() in ['quit', 'exit', 'q']:
            print("\n👋 Goodbye!")
            break
        
        if question.lower() == 'help':
            print("\n📖 Example Questions:")
            print("  1. What is the percentage of active vs inactive contracts?")
            print("  2. Show me top 10 customers by sales volume")
            print("  3. Predict next quarter sales for 'Orange Lake'")
            print("  4. Which customers are most likely to take tours?")
            print("  5. What is the average sales volume by location?")
            print("\n🔧 Commands:")
            print("  - 'approval on' - Enable SQL approval workflow")
            print("  - 'approval off' - Disable SQL approval workflow")
            print("  - 'memory' - Show conversation history")
            print("  - 'clear' - Clear current session memory")
            continue
        
        if question.lower() == 'memory':
            history = memory.get_session_history(session_id)
            if history:
                print(f"\n📚 Conversation History ({len(history)} interactions):")
                for i, interaction in enumerate(history, 1):
                    print(f"\n{i}. Q: {interaction['question']}")
                    print(f"   A: {interaction['answer'][:100]}...")
                    print(f"   Time: {interaction['timestamp']}")
            else:
                print("\n📚 No conversation history yet.")
            continue
        
        if question.lower() == 'clear':
            memory.clear_session(session_id)
            print(f"\n🗑️  Cleared session {session_id}")
            session_id = str(uuid.uuid4())[:8]
            print(f"💾 New session ID: {session_id}")
            continue
        
        if question.lower().startswith('approval '):
            if 'on' in question.lower():
                require_approval = True
                print("\n✅ SQL approval workflow ENABLED")
            else:
                require_approval = False
                print("\n❌ SQL approval workflow DISABLED")
            continue
        
        # Set default approval setting
        if 'require_approval' not in locals():
            require_approval = False
        
        # Process question
        print(f"\n🚀 Processing: '{question}'")
        print_separator()
        
        try:
            result = agent.run(
                question=question,
                session_id=session_id,
                require_approval=require_approval
            )
            
            # Handle approval workflow
            if result.get('status') == 'awaiting_approval':
                print_approval_request(result)
                
                print("\n❓ Approve this SQL query? (yes/no): ", end="")
                approval = input().strip().lower()
                
                if approval in ['yes', 'y']:
                    print("\n✅ SQL Approved. Executing...")
                    result = agent.execute_approved_sql(
                        sql_query=result['sql_query'],
                        question=result['question'],
                        session_id=result.get('session_id')
                    )
                    print_result(result)
                else:
                    print("\n❌ SQL Rejected. Query not executed.")
            else:
                print_result(result)
            
        except Exception as e:
            print(f"\n❌ Error processing question: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
