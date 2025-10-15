"""
Classification Tool
ML-powered customer classification using XGBoost.
"""

import json
import logging
import pandas as pd
import re
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score

from langchain_openai import AzureChatOpenAI
from langchain_core.messages import HumanMessage
from utils.config import AZURE_OPENAI_DEPLOYMENT_NAME, AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_VERSION
from utils.context import load_glossary, get_table_schema, connect_to_sql, RELATIONSHIPS
from tools.execute_sql import execute_sql_tool

logger = logging.getLogger(__name__)


def create_llm():
    """Create LLM client for classification."""
    return AzureChatOpenAI(
        deployment_name=AZURE_OPENAI_DEPLOYMENT_NAME,
        api_key=AZURE_OPENAI_API_KEY,
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_version=AZURE_OPENAI_API_VERSION,
        temperature=0,
        max_retries=3,
        timeout=60
    )


def classification_tool(question: str) -> str:
    """
    Complete classification workflow as a tool.
    
    Steps:
    1. Plan SQL and hyperparameters
    2. Execute SQL to fetch data
    3. Train XGBoost model
    4. Generate predictions
    5. Return results with insights
    
    Args:
        question: User's classification question
        
    Returns:
        JSON string with classification results
    """
    logger.info("=" * 80)
    logger.info("TOOL: classification_tool")
    logger.info(f"Question: {question}")
    
    try:
        # Load context
        glossary = load_glossary()
        cur = connect_to_sql()
        schema = get_table_schema(cur)
        
        # Step 1: Plan SQL and hyperparameters
        llm = create_llm()
        
        plan_prompt = f"""# Task
Generate a T-SQL query and XGBoost classification parameters to answer the user's question.

# User Question
{question}

# Database Context

## Business Glossary
{glossary}

## Database Schema
{schema}

## Table Relationships
{RELATIONSHIPS}

# Requirements

## SQL Query Requirements:
1. **Customer Identifier**: Must include DimCustomerSK for tracking
2. **Target Variable**: Create binary target (0/1) using CASE WHEN
   - Example: CASE WHEN TourCount > 0 THEN 1 ELSE 0 END AS HasTakenTour
   - Ensure both classes (0 and 1) are present in data
3. **Feature Selection**: Choose 5-10 relevant predictive features:
   - Demographic: Age, Location, MembershipType
   - Behavioral: PurchaseHistory, EngagementScore, LastActivityDays
   - Financial: TotalSpend, AverageOrderValue, CreditScore
4. **Data Quality**:
   - Limit to 1000-5000 rows for performance
   - Exclude NULL in target variable
   - No PII (names, emails, SSN, phone numbers)
5. **Joins**: Use appropriate INNER/LEFT JOINs based on relationships

## XGBoost Parameters:
- **objective**: "binary:logistic" (for binary classification)
- **n_estimators**: 100-200 (number of trees)
- **max_depth**: 4-8 (tree depth, lower = less overfitting)
- **learning_rate**: 0.05-0.1 (smaller = more robust)
- **random_state**: 42 (for reproducibility)

## Preprocessing:
- **handle_missing**: true (fill missing values)
- **encode_categorical**: true (convert text to numbers)
- **test_size**: 0.2 (20% for validation)

# Output Format

Respond with ONLY valid JSON (no markdown code blocks, no explanatory text):

{{
    "sql": "Complete T-SQL query",
    "target_column": "name_of_target_column",
    "feature_columns": ["feature1", "feature2", "feature3"],
    "identifier_columns": ["DimCustomerSK"],
    "xgboost_args": {{
        "objective": "binary:logistic",
        "n_estimators": 100,
        "max_depth": 6,
        "learning_rate": 0.1,
        "random_state": 42
    }},
    "preprocessing_args": {{
        "handle_missing": true,
        "encode_categorical": true,
        "test_size": 0.2
    }},
    "problem_type": "binary"
}}

# Example

Question: "Which customers are most likely to take tours?"

Output:
{{
    "sql": "SELECT TOP 2000 dc.DimCustomerSK, CASE WHEN COUNT(ft.FactTourSK) > 0 THEN 1 ELSE 0 END AS HasTakenTour, dc.Age, dc.MembershipYears, SUM(fsc.SalesVolume) AS TotalSpend, COUNT(DISTINCT fsc.FactSalesContractSK) AS PurchaseCount, dsl.Region FROM edw.DimCustomer dc LEFT JOIN edw.FactTour ft ON dc.DimCustomerSK = ft.DimCustomerSK LEFT JOIN edw.FactSalesContract fsc ON dc.DimCustomerSK = fsc.DimCustomerSK LEFT JOIN edw.DimSalesLocation dsl ON fsc.DimSalesLocationSK = dsl.DimSalesLocationSK WHERE dc.IsActive = 1 GROUP BY dc.DimCustomerSK, dc.Age, dc.MembershipYears, dsl.Region",
    "target_column": "HasTakenTour",
    "feature_columns": ["Age", "MembershipYears", "TotalSpend", "PurchaseCount", "Region"],
    "identifier_columns": ["DimCustomerSK"],
    "xgboost_args": {{"objective": "binary:logistic", "n_estimators": 150, "max_depth": 6, "learning_rate": 0.1, "random_state": 42}},
    "preprocessing_args": {{"handle_missing": true, "encode_categorical": true, "test_size": 0.2}},
    "problem_type": "binary"
}}

Now generate the plan for the user's question."""

        response = llm.invoke([HumanMessage(content=plan_prompt)]).content
        logger.info(f"LLM Response length: {len(response)}")
        logger.info(f"LLM Response (first 500 chars): {response[:500]}")
        
        if not response or not response.strip():
            return json.dumps({'error': 'LLM returned empty response'})
        
        # Try to extract JSON if wrapped in markdown
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
        if json_match:
            response = json_match.group(1)
            logger.info("Extracted JSON from markdown code block")
        
        # Try to find JSON object in response
        if not response.strip().startswith('{'):
            json_obj_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_obj_match:
                response = json_obj_match.group(0)
                logger.info("Extracted JSON object from text")
        
        try:
            plan = json.loads(response)
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            logger.error(f"Failed to parse response: {response[:1000]}")
            return json.dumps({'error': f'Failed to parse LLM response as JSON: {str(e)}'})
        
        logger.info(f"Plan: {plan}")
        
        # Step 2: Execute SQL via shared tool for consistency
        sql_query = plan.get('sql', '')
        if not sql_query or not isinstance(sql_query, str):
            logger.error(f"Invalid SQL in plan. Type: {type(sql_query)}, Value: {sql_query}")
            return json.dumps({'error': f'Invalid SQL query in plan: {type(sql_query)}'})

        sql_query = str(sql_query).strip()
        logger.info(f"Executing SQL (via tool): {sql_query[:200]}...")

        exec_result_raw = execute_sql_tool(sql_query)
        try:
            exec_result = json.loads(exec_result_raw)
        except Exception as e:
            logger.error(f"Failed to parse execute_sql_tool result: {e} :: {exec_result_raw[:300]}")
            return json.dumps({'error': 'Failed to execute SQL'})

        if exec_result.get('error'):
            return json.dumps({'error': exec_result['error']})

        df = pd.DataFrame(exec_result.get('data') or [])
        if df.empty:
            return json.dumps({'error': 'No customer data available'})

        logger.info(f"Customer data: {len(df)} rows")
        
        # Step 3: Train XGBoost
        target_col = plan['target_column']
        feature_cols = plan['feature_columns']
        identifier_cols = plan.get('identifier_columns', [])
        xgb_args = plan.get('xgboost_args', {})
        preprocess_args = plan.get('preprocessing_args', {})
        
        X = df[feature_cols].copy()
        y = df[target_col].copy()
        
        # Handle missing values
        for col in X.columns:
            if X[col].dtype in ['float64', 'int64']:
                X[col].fillna(X[col].median(), inplace=True)
            else:
                X[col].fillna('Unknown', inplace=True)
        
        # Encode categorical
        for col in X.select_dtypes(include=['object']).columns:
            le = LabelEncoder()
            X[col] = le.fit_transform(X[col].astype(str))
        
        # Split and train
        test_size = preprocess_args.get('test_size', 0.2)
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=test_size, random_state=42)
        
        model = xgb.XGBClassifier(**xgb_args)
        model.fit(X_train, y_train)
        
        # Predict
        y_pred = model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        
        # Predict on full dataset
        df['Probability'] = model.predict_proba(X)[:, 1]
        df['Predicted'] = model.predict(X)
        
        # Get top 100
        top_100 = df.nlargest(100, 'Probability')[identifier_cols + ['Probability', 'Predicted']]
        
        # Generate insights
        insight_prompt = f"""# Task
Analyze the customer classification results and provide actionable targeting recommendations.

# Context

## Original Question
{question}

## Top 10 Predicted Customers
{top_100.head(10).to_dict()}

## Model Performance
- Accuracy: {accuracy * 100:.1f}%
- Interpretation: Percentage of correct predictions on test data
- Good: >80%, Acceptable: 70-80%, Poor: <70%

# Instructions

Provide a structured business analysis with:

1. **Customer Segments Identified** (2-3 bullet points)
   - Common characteristics of high-probability customers
   - Key differentiators from low-probability customers
   - Segment size and potential reach

2. **Targeting Strategy** (2-3 bullet points)
   - Which customers to prioritize (top X%)
   - Recommended channels or approaches
   - Expected conversion rates

3. **Action Plan** (3-4 specific steps)
   - Immediate actions (next 1-2 weeks)
   - Campaign design recommendations
   - Resource allocation suggestions
   - Success metrics to track

4. **Model Confidence**
   - Comment on prediction reliability based on accuracy
   - Suggest improvements if accuracy is low
   - Recommend A/B testing approach

# Output Format

Provide clear, actionable recommendations in business language. Focus on ROI and practical implementation."""

        insights = llm.invoke([HumanMessage(content=insight_prompt)]).content
        
        logger.info("Classification completed successfully")
        logger.info("=" * 80)
        
        return json.dumps({
            'success': True,
            'predictions': top_100.to_dict(orient='records'),
            'model_metrics': {'accuracy': round(accuracy, 4)},
            'insights': insights,
            'sql_query': plan['sql']
        })
        
    except Exception as e:
        logger.error(f"Classification tool failed: {str(e)}")
        return json.dumps({'error': str(e)})
