"""
Chart Generation Tool
Generates Plotly chart specifications based on data and question context.
"""

import json
import logging
import pandas as pd
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import HumanMessage
from utils.config import AZURE_OPENAI_DEPLOYMENT_NAME, AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_VERSION

logger = logging.getLogger(__name__)


def create_llm():
    """Create LLM client for chart generation."""
    return AzureChatOpenAI(
        deployment_name=AZURE_OPENAI_DEPLOYMENT_NAME,
        api_key=AZURE_OPENAI_API_KEY,
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_version=AZURE_OPENAI_API_VERSION,
        temperature=0
    )


def generate_chart_tool(data_json: str, question: str) -> str:
    """
    Generate Plotly chart specifications based on data and question.
    
    Workflow:
    1. Analyze data structure and question
    2. Determine appropriate chart type
    3. Generate Plotly configuration
    4. Return chart specs with insights
    
    Args:
        data_json: JSON string with query results
        question: Original user question for context
        
    Returns:
        JSON string with chart specifications and insights
    """
    logger.info("=" * 80)
    logger.info("TOOL: generate_chart_tool")
    logger.info(f"Question: {question}")
    
    try:
        # Parse data
        data = json.loads(data_json)
        
        if 'error' in data:
            return json.dumps({'error': 'Cannot generate chart from error data'})
        
        if 'data' not in data or not data['data']:
            return json.dumps({'error': 'No data available for chart generation'})
        
        # Convert to DataFrame for analysis
        df = pd.DataFrame(data['data'])
        logger.info(f"Data shape: {df.shape}")
        logger.info(f"Columns: {df.columns.tolist()}")
        
        # Analyze data and generate chart specs
        llm = create_llm()
        
        chart_prompt = f"""# Task
Analyze the data and generate appropriate Plotly chart specifications.

# Context

## User Question
{question}

## Data Sample (first 10 rows)
{df.head(10).to_dict(orient='records')}

## Data Summary
- Rows: {len(df)}
- Columns: {df.columns.tolist()}
- Numeric columns: {df.select_dtypes(include=['number']).columns.tolist()}
- Text columns: {df.select_dtypes(include=['object']).columns.tolist()}

# Chart Selection Guidelines

## Bar Chart
- Use for: Comparisons, rankings, categorical data
- Best when: Comparing values across categories (top N, by category)
- Example: Top 5 resorts by sales, Sales by region

## Line Chart
- Use for: Trends over time, time-series data
- Best when: Date/time column exists, showing progression
- Example: Sales over months, Growth trends

## Pie Chart
- Use for: Proportions, percentages, composition
- Best when: Showing parts of a whole (max 7 slices)
- Example: Market share, Distribution percentages

## Scatter Plot
- Use for: Relationships, correlations
- Best when: Two numeric variables, looking for patterns
- Example: Price vs Quantity, Age vs Spend

## Table
- Use for: Detailed data, multiple columns, exact values
- Best when: User needs specific numbers, complex data

# Instructions

1. **Analyze** the question and data structure
2. **Select** the most appropriate chart type
3. **Identify** x-axis and y-axis columns
4. **Generate** complete Plotly configuration
5. **Provide** brief insights about the visualization

# Output Format

Respond with ONLY valid JSON (no markdown, no extra text):

{{
    "chart_type": "bar|line|pie|scatter|table",
    "chart_config": {{
        "data": [{{
            "x": ["column_name_for_x_axis"],
            "y": ["column_name_for_y_axis"],
            "type": "bar|scatter|line",
            "name": "Series Name",
            "marker": {{"color": "rgb(55, 83, 109)"}}
        }}],
        "layout": {{
            "title": "Chart Title",
            "xaxis": {{"title": "X Axis Label"}},
            "yaxis": {{"title": "Y Axis Label"}},
            "showlegend": true,
            "height": 500
        }}
    }},
    "insights": "Brief 2-3 sentence insight about what the chart shows",
    "reasoning": "Why this chart type was chosen"
}}

# Example

Question: "What are the top 5 resorts by sales?"
Data: [{{"SiteName": "Orange Lake", "TotalSales": 270536845.15}}, ...]

Output:
{{
    "chart_type": "bar",
    "chart_config": {{
        "data": [{{
            "x": ["SiteName"],
            "y": ["TotalSales"],
            "type": "bar",
            "name": "Total Sales",
            "marker": {{"color": "rgb(55, 83, 109)"}}
        }}],
        "layout": {{
            "title": "Top 5 Resorts by Sales Volume",
            "xaxis": {{"title": "Resort Name"}},
            "yaxis": {{"title": "Total Sales ($)", "tickformat": "$,.0f"}},
            "showlegend": false,
            "height": 500
        }}
    }},
    "insights": "Orange Lake leads with $270.5M in sales, significantly outperforming other resorts. The top 5 resorts account for the majority of total sales volume.",
    "reasoning": "Bar chart is ideal for comparing sales across different resorts, making it easy to see rankings and relative performance."
}}

Now generate the chart specification for the user's question and data."""

        response = llm.invoke([HumanMessage(content=chart_prompt)]).content
        logger.info(f"LLM Response length: {len(response)}")
        
        # Extract JSON
        import re
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
        if json_match:
            response = json_match.group(1)
        else:
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                response = json_match.group(0)
        
        chart_specs = json.loads(response)
        
        # Add the actual data to chart config
        chart_config = chart_specs.get('chart_config', {})
        if 'data' in chart_config and len(chart_config['data']) > 0:
            # Replace column names with actual data
            for trace in chart_config['data']:
                if 'x' in trace and len(trace['x']) > 0:
                    x_col = trace['x'][0]
                    if x_col in df.columns:
                        trace['x'] = df[x_col].tolist()
                
                if 'y' in trace and len(trace['y']) > 0:
                    y_col = trace['y'][0]
                    if y_col in df.columns:
                        trace['y'] = df[y_col].tolist()
        
        logger.info(f"Chart type: {chart_specs.get('chart_type')}")
        logger.info("Chart generation completed successfully")
        
        return json.dumps({
            'success': True,
            'chart_type': chart_specs.get('chart_type'),
            'chart_config': chart_config,
            'insights': chart_specs.get('insights'),
            'reasoning': chart_specs.get('reasoning')
        })
        
    except Exception as e:
        logger.error(f"Chart generation failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return json.dumps({'error': str(e)})
