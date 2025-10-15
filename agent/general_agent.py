"""
General Agent - Single Agent with Tools
One intelligent agent that autonomously selects and uses tools.
"""

import json
import logging

from langchain_openai import AzureChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage

from utils.config import (
    AZURE_OPENAI_DEPLOYMENT_NAME,
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_API_VERSION
)
from utils.context import load_glossary, get_table_schema, connect_to_sql, RELATIONSHIPS
from utils.memory import get_memory
from tools import (
    execute_sql_tool,
    forecast_tool,
    classification_tool,
    display_data_tool,
    generate_chart_tool
)

logger = logging.getLogger(__name__)


class GeneralAgent:
    """
    General Agent that can use multiple tools to answer questions.
    
    The agent:
    1. Receives a question
    2. Analyzes what needs to be done
    3. Selects and uses appropriate tools
    4. Returns the final answer
    """
    
    def __init__(self, temperature=0, max_iterations=5):
        """
        Initialize the General Agent.
        
        Args:
            temperature: LLM temperature for reasoning
            max_iterations: Maximum reasoning iterations
        """
        self.temperature = temperature
        self.max_iterations = max_iterations
        
        # Initialize LLM
        self.llm = AzureChatOpenAI(
            deployment_name=AZURE_OPENAI_DEPLOYMENT_NAME,
            api_key=AZURE_OPENAI_API_KEY,
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_version=AZURE_OPENAI_API_VERSION,
            temperature=temperature
        )
        
        # Load context
        logger.info("Loading database context...")
        self.glossary = load_glossary()
        cur = connect_to_sql()
        self.schema = get_table_schema(cur)
        self.relationships = RELATIONSHIPS
        logger.info("Context loaded")
        
        # Define tool descriptions
        self.tools = {
            'execute_sql_tool': {
                'function': execute_sql_tool,
                'description': 'Execute T-SQL query and return current/historical data. Use for: aggregations, counts, percentages, top N queries, current state analysis. DO NOT use for predictions or forecasts.'
            },
            'forecast_tool': {
                'function': forecast_tool,
                'description': 'TIME-SERIES FORECASTING ONLY. Use when user asks to: predict, forecast, project future values, estimate next quarter/month/year. This tool handles SQL, Prophet training, and insights automatically. Input: the user question as-is.'
            },
            'classification_tool': {
                'function': classification_tool,
                'description': 'ML CUSTOMER CLASSIFICATION. Use to: identify likely buyers, segment customers, predict customer behavior, find high-value prospects. This tool handles SQL, XGBoost training, and predictions automatically. Input: the user question as-is.'
            },
            'display_data': {
                'function': display_data_tool,
                'description': 'Format and display data results. Use to present query results in a readable format.'
            },
            'generate_chart_tool': {
                'function': generate_chart_tool,
                'description': 'Generate Plotly chart specifications from data. Use after SQL queries to visualize results. Input: data_json and question.'
            }
        }
        
        # Initialize memory
        self.memory = get_memory()
        
        logger.info(f"Agent initialized with {len(self.tools)} tools")
    
    def run(self, question: str, session_id: str = None, require_approval: bool = False) -> dict:
        """
        Run the agent to answer a question.
        
        Args:
            question: User's question
            session_id: Optional session ID for conversation memory
            require_approval: If True, return SQL for approval before execution
            
        Returns:
            dict: Enhanced result with answer, data, chart_specs, insights, and metadata
        """
        logger.info("=" * 100)
        logger.info(f"AGENT RECEIVED QUESTION: {question}")
        logger.info("=" * 100)
        
        # Initialize conversation history
        messages = []
        
        # Add context from memory if session exists
        if session_id:
            context = self.memory.get_context_for_question(session_id, question)
            if context:
                messages.append(HumanMessage(content=context))
                logger.info("Added conversation context from memory")
        
        # System prompt - Following OpenAI best practices
        system_prompt = f"""# Role
You are an expert business intelligence analyst with access to specialized data analysis tools.

# Database Context
## Business Glossary
{self.glossary}

## Database Schema
{self.schema}

## Table Relationships
{self.relationships}

# Available Tools
{self._format_tools()}

# Tool Selection Guidelines

## When to use execute_sql_tool:
- Aggregations (SUM, AVG, COUNT)
- Filtering and grouping data
- Top N queries (TOP 10 customers)
- Percentage calculations
- Current state analysis
- Historical data retrieval

## When to use forecast_tool:
- Keywords: predict, forecast, project, estimate, next quarter/month/year
- Time-series predictions
- Future trend analysis
- Input: Pass the user's question exactly as-is
- Note: This tool handles SQL generation, Prophet training, and insights automatically

## When to use classification_tool:
- Keywords: likely, probable, segment, classify, identify, target
- Customer segmentation
- Behavior prediction
- Propensity modeling
- Input: Pass the user's question exactly as-is
- Note: This tool handles SQL generation, XGBoost training, and predictions automatically

# Instructions

1. **Analyze** the user's question carefully
2. **Identify** keywords and intent
3. **Select** the most appropriate tool (aim for ONE tool call)
4. **Execute** the tool with proper input
5. **Synthesize** results into a clear business answer

# Output Format

Respond with ONLY valid JSON in this exact structure:

```json
{{
    "reasoning": "Step-by-step analysis: (1) Question type, (2) Key indicators, (3) Tool selection rationale",
    "decision": "use_tool",
    "tool_name": "exact_tool_name_from_list",
    "tool_input": "appropriate input based on tool type"
}}
```

OR when you have enough information to answer:

```json
{{
    "reasoning": "Why I can answer directly without tools",
    "decision": "answer",
    "answer": "Complete, business-focused answer with specific numbers and insights"
}}
```

# Important Notes
- Respond ONLY with valid JSON (no markdown, no extra text)
- For forecast_tool and classification_tool: pass the user question as-is
- For execute_sql_tool: provide the complete T-SQL query
- Aim to complete the task in ONE tool call"""

        messages.append(HumanMessage(content=system_prompt))
        messages.append(HumanMessage(content=f"User Question: {question}"))
        
        # Iterative reasoning loop
        for iteration in range(1, self.max_iterations + 1):
            logger.info(f"\n--- ITERATION {iteration} ---")
            logger.info("Agent is thinking...")
            
            # Get agent's decision
            response = self.llm.invoke(messages)
            response_text = response.content
            
            # Parse decision
            try:
                decision = self._parse_decision(response_text)
            except Exception as e:
                logger.error(f"Failed to parse decision: {e}")
                logger.error(f"Response: {response_text}")
                continue
            
            logger.info(f"Reasoning: {decision.get('reasoning', 'N/A')}")
            logger.info(f"Decision: {decision.get('decision', 'N/A')}")
            
            # Add agent's response to history
            messages.append(AIMessage(content=response_text))
            
            # Handle decision
            if decision.get('decision') == 'answer':
                # Agent has final answer
                logger.info("Agent provided final answer")
                
                # Prepare enhanced response
                response = {
                    'status': 'success',
                    'answer': decision.get('answer', 'No answer provided'),
                    'iterations': iteration
                }
                
                # Try to generate chart if we have SQL results
                if hasattr(self, '_last_sql_result'):
                    try:
                        chart_result = generate_chart_tool(self._last_sql_result, question)
                        chart_data = json.loads(chart_result)
                        
                        if chart_data.get('success'):
                            response['chart_specs'] = chart_data.get('chart_config')
                            response['chart_type'] = chart_data.get('chart_type')
                            response['chart_insights'] = chart_data.get('insights')
                            logger.info(f"Generated {chart_data.get('chart_type')} chart")
                        
                        # Parse and include data
                        sql_data = json.loads(self._last_sql_result)
                        if 'data' in sql_data:
                            response['data'] = sql_data['data']
                            response['row_count'] = len(sql_data['data'])
                    except Exception as e:
                        logger.warning(f"Chart generation failed: {e}")
                
                # Save to memory if session exists
                if session_id:
                    self.memory.save_interaction(
                        session_id=session_id,
                        question=question,
                        answer=response['answer'],
                        data=response.get('data'),
                        metadata={
                            'iterations': iteration,
                            'chart_type': response.get('chart_type'),
                            'row_count': response.get('row_count')
                        }
                    )
                    logger.info(f"Saved interaction to memory (session: {session_id})")
                
                return response
            
            elif decision.get('decision') == 'use_tool':
                # Use tool
                tool_name = decision.get('tool_name')
                tool_input = decision.get('tool_input')
                
                logger.info(f"Using tool: {tool_name}")
                logger.info(f"Tool input: {str(tool_input)[:200]}...")
                logger.info(f"Tool input type: {type(tool_input)}, value: {tool_input}")
                
                if tool_name not in self.tools:
                    error_msg = f"Unknown tool: {tool_name}"
                    logger.error(error_msg)
                    messages.append(HumanMessage(content=error_msg))
                    continue
                
                # Human approval workflow for SQL execution
                if tool_name == 'execute_sql_tool' and require_approval:
                    logger.info("SQL execution requires approval")
                    return {
                        'status': 'awaiting_approval',
                        'sql_query': tool_input,
                        'question': question,
                        'session_id': session_id,
                        'message': 'Please review and approve the SQL query before execution'
                    }
                
                # Execute tool
                try:
                    tool_func = self.tools[tool_name]['function']
                    result = tool_func(tool_input)
                    logger.info(f"Tool result: {str(result)[:200]}...")
                    
                    # Store result for potential chart generation
                    if tool_name == 'execute_sql_tool':
                        self._last_sql_result = result
                    
                    # Add tool result to history as HumanMessage (not ToolMessage)
                    messages.append(HumanMessage(content=f"Tool '{tool_name}' returned: {result}"))
                    
                except Exception as e:
                    error_msg = f"Tool execution failed: {str(e)}"
                    logger.error(error_msg)
                    messages.append(HumanMessage(content=error_msg))
            
            else:
                logger.warning(f"Unknown decision: {decision.get('decision')}")
                messages.append(HumanMessage(content="Please provide a valid decision: 'use_tool' or 'answer'"))
        
        # Max iterations reached
        logger.warning("Max iterations reached without completing task")
        return {
            'error': 'Max iterations reached without completing task',
            'iterations': self.max_iterations
        }
    
    def execute_approved_sql(self, sql_query: str, question: str, session_id: str = None) -> dict:
        """
        Execute a pre-approved SQL query and return enhanced results.
        
        This method is called after human approval of the SQL query.
        
        Args:
            sql_query: Approved SQL query
            question: Original user question
            session_id: Optional session ID for memory
            
        Returns:
            dict: Enhanced result with data, chart, and insights
        """
        logger.info("=" * 100)
        logger.info("EXECUTING APPROVED SQL")
        logger.info(f"SQL: {sql_query[:200]}...")
        logger.info("=" * 100)
        
        try:
            # Execute SQL
            result = execute_sql_tool(sql_query)
            logger.info(f"SQL execution result: {str(result)[:200]}...")
            
            # Parse result
            sql_data = json.loads(result)
            
            if 'error' in sql_data:
                return {
                    'status': 'error',
                    'error': sql_data['error'],
                    'sql_query': sql_query
                }
            
            # Prepare response
            response = {
                'status': 'success',
                'data': sql_data.get('data', []),
                'row_count': len(sql_data.get('data', [])),
                'columns': sql_data.get('columns', []),
                'sql_query': sql_query
            }
            
            # Generate chart
            try:
                chart_result = generate_chart_tool(result, question)
                chart_data = json.loads(chart_result)
                
                if chart_data.get('success'):
                    response['chart_specs'] = chart_data.get('chart_config')
                    response['chart_type'] = chart_data.get('chart_type')
                    response['chart_insights'] = chart_data.get('insights')
                    logger.info(f"Generated {chart_data.get('chart_type')} chart")
            except Exception as e:
                logger.warning(f"Chart generation failed: {e}")
            
            # Generate answer using LLM
            answer_prompt = f"""Based on the query results, provide a clear business answer to the user's question.

Question: {question}

Data Summary:
- Rows returned: {response['row_count']}
- Columns: {', '.join(response.get('columns', []))}
- Sample data: {response['data'][:5] if response['data'] else 'No data'}

Provide a concise, business-focused answer with key insights."""

            llm_response = self.llm.invoke([HumanMessage(content=answer_prompt)])
            response['answer'] = llm_response.content
            
            # Save to memory
            if session_id:
                self.memory.save_interaction(
                    session_id=session_id,
                    question=question,
                    answer=response['answer'],
                    data=response['data'],
                    metadata={
                        'chart_type': response.get('chart_type'),
                        'row_count': response['row_count'],
                        'approved_sql': True
                    }
                )
                logger.info(f"Saved interaction to memory (session: {session_id})")
            
            return response
            
        except Exception as e:
            logger.error(f"Approved SQL execution failed: {e}")
            import traceback
            traceback.print_exc()
            return {
                'status': 'error',
                'error': str(e),
                'sql_query': sql_query
            }
    
    def _format_tools(self) -> str:
        """Format tool descriptions for the prompt."""
        lines = []
        for name, info in self.tools.items():
            lines.append(f"- {name}: {info['description']}")
        return "\n".join(lines)
    
    def _parse_decision(self, response_text: str) -> dict:
        """
        Parse agent's decision from response.
        
        Args:
            response_text: Agent's response
            
        Returns:
            dict: Parsed decision
        """
        # Try to extract JSON
        import re
        
        # Look for JSON block
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find JSON object (greedy match to get the full object)
            json_match = re.search(r'\{[^}]*(?:\{[^}]*\}[^}]*)*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                raise ValueError("No JSON found in response")
        
        # Parse JSON and handle null values
        decision = json.loads(json_str)
        
        # Ensure required fields exist
        if 'decision' not in decision:
            raise ValueError("Missing 'decision' field in response")
        
        return decision
