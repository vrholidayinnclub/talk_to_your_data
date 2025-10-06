import json, numpy as np, pandas as pd, streamlit as st
from config import *
from utils_context import *
from typing import Optional, Dict
from langchain_core.messages import HumanMessage
import ast
import logging
from variables import *
from utils_ttyd import *
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.metrics import classification_report, roc_auc_score
from datetime import datetime
import psutil
import gc
import warnings
warnings.filterwarnings('ignore')

# Initialize logger for this module
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def validate_classification_plan(plan_dict: Dict) -> tuple[bool, str]:
    """
    Validate AI-generated classification plan for required fields and data types.
    
    Args:
        plan_dict: Dictionary containing classification plan
        
    Returns:
        tuple: (is_valid, error_message)
    """
    required_fields = {
        'SQL': str,
        'target_column': str,
        'feature_columns': list,
        'xgboost_args': dict,
        'preprocessing_args': dict,
        'problem_type': str,
        'expected_classes': list
    }
    
    for field, expected_type in required_fields.items():
        if field not in plan_dict:
            return False, f"Missing required field: {field}"
        
        if not isinstance(plan_dict[field], expected_type):
            return False, f"Field '{field}' must be of type {expected_type.__name__}, got {type(plan_dict[field]).__name__}"
    
    # Validate problem type
    if plan_dict['problem_type'] not in ['binary', 'multiclass']:
        return False, "problem_type must be 'binary' or 'multiclass'"
    
    # Validate feature columns is not empty
    if not plan_dict['feature_columns']:
        return False, "feature_columns cannot be empty"
    
    # Validate expected classes
    if len(plan_dict['expected_classes']) < 2:
        return False, "expected_classes must have at least 2 classes"
    
    return True, "Valid"


def safe_json_parse(response_content: str) -> tuple[Dict, str]:
    """
    Safely parse AI response with multiple fallback methods.
    
    Args:
        response_content: Raw AI response string
        
    Returns:
        tuple: (parsed_dict, error_message)
    """
    # Method 1: Try ast.literal_eval
    try:
        result = ast.literal_eval(response_content)
        if isinstance(result, dict):
            return result, ""
    except (ValueError, SyntaxError) as e:
        logger.warning(f"ast.literal_eval failed: {e}")
    
    # Method 2: Try json.loads
    try:
        result = json.loads(response_content)
        if isinstance(result, dict):
            return result, ""
    except json.JSONDecodeError as e:
        logger.warning(f"json.loads failed: {e}")
    
    # Method 3: Try to extract JSON from markdown code blocks
    try:
        import re
        json_match = re.search(r'```(?:json)?\s*({.*?})\s*```', response_content, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group(1))
            if isinstance(result, dict):
                return result, ""
    except (json.JSONDecodeError, AttributeError) as e:
        logger.warning(f"Markdown JSON extraction failed: {e}")
    
    # Method 4: Try to find JSON object in the response (more flexible)
    try:
        import re
        # Look for { ... } pattern that spans multiple lines
        json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        matches = re.findall(json_pattern, response_content, re.DOTALL)
        for match in matches:
            try:
                result = json.loads(match)
                if isinstance(result, dict) and 'SQL' in result:
                    return result, ""
            except json.JSONDecodeError:
                continue
    except Exception as e:
        logger.warning(f"Flexible JSON extraction failed: {e}")
    
    return {}, f"Failed to parse AI response: {response_content[:200]}..."


def clean_duplicate_columns(sql_query: str) -> str:
    """
    Clean duplicate columns from a SQL SELECT statement.
    
    Args:
        sql_query: The SQL query string
        
    Returns:
        Cleaned SQL query with duplicate columns removed
    """
    try:
        import re
        
        # Extract the SELECT part
        select_match = re.search(r'SELECT\s+(.*?)\s+FROM', sql_query, re.IGNORECASE | re.DOTALL)
        if not select_match:
            return sql_query
        
        select_part = select_match.group(1)
        
        # Split columns and clean duplicates while preserving order
        columns = [col.strip() for col in select_part.split(',')]
        seen = set()
        unique_columns = []
        
        for col in columns:
            # Normalize column for comparison (remove extra spaces, case insensitive)
            normalized = re.sub(r'\s+', ' ', col.strip().lower())
            if normalized not in seen and col.strip():
                seen.add(normalized)
                unique_columns.append(col.strip())
        
        # Reconstruct the query
        new_select_part = ', '.join(unique_columns)
        cleaned_query = sql_query.replace(select_match.group(0), f'SELECT {new_select_part} FROM', 1)
        
        logger.info(f"Removed {len(columns) - len(unique_columns)} duplicate columns")
        return cleaned_query
        
    except Exception as e:
        logger.warning(f"Error cleaning duplicate columns: {e}")
        return sql_query


def check_memory_usage() -> Dict[str, float]:
    """
    Check current memory usage and return statistics.
    
    Returns:
        Dictionary with memory statistics
    """
    process = psutil.Process()
    memory_info = process.memory_info()
    
    return {
        'memory_mb': memory_info.rss / 1024 / 1024,
        'memory_percent': process.memory_percent(),
        'available_mb': psutil.virtual_memory().available / 1024 / 1024
    }


def classification_expert(state: State):
    """
    AI-powered classification planning agent that generates SQL queries and XGBoost parameters
    for binary/multi-class classification problems.
    """
    logger.info("Planning for classification")
    agent = create_agent()

    prompt = f"""You are an expert data scientist who prepares all the data and parameters required to train an XGBoost classification model.
                    Your goal is to group customers into meaningful groups/segments (high, at-risk, new, etc) and provide the right data and parameters for training a classification model.
                    As a preprocessing step, derive a customer_segment column to group customers into meaningful segments based on the business attributes and include the segmenation logic in your SQL query.
                    
                    With the given user question, generate an appropriate T-SQL query with proper type casting and the right parameters for XGBoost model based 
                    on the given Glossary, Schema, Table Relationships.
                    Always use the provided table relationships to join tables. 
                    ALWAYS use only the columns and tables provided in the schema.
                    NEVER invent columns. If a column does not appear in the provided schema, DO NOT use it.
                    The following columns are forbidden and MUST NOT be used under any circumstance: SMSOptInBit, EmailOptOutBit, DoNotCallBit, DoNotMarketBit, LastName.
                    NEVER USE any PII data.

                    For customer segmentation:
                    - Include customer demographics, behavioral data, transaction history as features for defining customer segments
                    - Always include a customer identifier for tracking
                    - Use meaningful segment names like "High Value", "At Risk", "Loyal", "New", "Churned" etc.
                    
                    Segmentation Guidelines:
                    - Understand the business context of the segmentation
                    - Use stratified sampling to ensure representative customer segments in the dataset.

                    For classification problems:
                    - Identify the target variable (what we want to predict/classify) and rename it according to the question.
                    - Always include a customer identifier for tracking
                    
                    Classification Guidelines:
                    - Include features like: age, location, previous purchases, tour history, package type, etc.. Do not use more than 10 features.
                    - Ensure sufficient historical data for training (ALWAYS fetch only 1000 rows.)
                    - MUST include both positive and negative examples in your SQL query
                    - Use CASE WHEN statements to create proper binary targets that include both 0 and 1 values
                    
                    Never include any ticks (`) or markdowns in your answer.
                    
                    User Question:
                    {state["question"]}

                    Glossary:
                    {state["glossary"]}

                    Schema:
                    {state["tbl_schema"]}

                    Relationships:
                    {state["relationships"]} 

                    Your Answer in JSON format like this-
                    {{
                    "SQL" : "A valid raw T-SQL query that returns features and target variable. MUST include CASE WHEN logic to create binary target with both 0 and 1 values. Keep the query concise - select only the most relevant columns (max 20-30 columns). Never duplicate columns. Never include any ticks(`) or any markdowns. Example: SELECT CustomerAge, CASE WHEN TourCount > 0 THEN 1 ELSE 0 END AS HasTraveled FROM...",
                    "target_column" : "Name of the target column for classification",
                    "feature_columns" : ["list", "of", "feature", "column", "names"],
                    "segmentation_column" : "Name of the column containing customer segments that you derived via SQL query",
                    "identifier_columns" : ["list of customer identifiers to show in the final Top-N (e.g., DimCustomerSK, CustomerID, Email)"],
                    "positive_class_label" : "name/value of the positive class you are predicting (e.g., 1 or 'Traveled')",
                    "columns_used" : ["complete", "list", "of", "all", "columns", "referenced", "in", "SQL"],
                    "segment_definition" : A brief definition of each customer segment in JSON format,
                    "xgboost_args" : {{
                        "objective": "binary:logistic or multi:softprob",
                        "n_estimators": 50-100,
                        "max_depth": 6,
                        "learning_rate": 0.1,
                        "subsample": 0.8,
                        "colsample_bytree": 0.8,
                        "random_state": 42
                    }},
                    "preprocessing_args" : {{
                        "handle_missing": true,
                        "encode_categorical": true,
                        "scale_features": false,
                        "test_size": 0.2
                    }},
                    "problem_type" : "binary or multiclass",
                    "expected_classes" : ["class1", "class2"] or ["class1", "class2", "class3"]
                    }}
                    """.strip()
    
    
    response = agent.invoke([HumanMessage(content=prompt)])
    logger.info(response)
    logger.info(f"Response from Classification Expert : {response.content}")
    
    # Safe JSON parsing with validation
    response_dict, parse_error = safe_json_parse(response.content)
    
    if parse_error:
        logger.error(f"Error parsing classification expert response: {parse_error}")
        # Try to extract SQL as fallback even if JSON parsing failed
        try:
            import re
            sql_match = re.search(r'"SQL"\s*:\s*"([^"]+)"', response.content, re.IGNORECASE)
            if sql_match:
                sql_query = sql_match.group(1).strip()
                if sql_query:
                    logger.info(f"Extracted SQL from failed JSON parse: {sql_query}")
                    state["sql_query"] = sql_query
                    return state
        except Exception as e:
            logger.warning(f"Fallback SQL extraction also failed: {e}")
        return state
    
    # Validate the parsed plan
    is_valid, validation_error = validate_classification_plan(response_dict)
    
    if not is_valid:
        logger.error(f"Invalid classification plan: {validation_error}")
        return state
    
    # Post-validate to prevent non-existent/forbidden columns
    FORBIDDEN_COLUMNS = {"smsoptinbit", "emailoptoutbit", "donotcallbit", "donotmarketbit"}
    try:
        plan = response_dict
        sql = plan.get("SQL", "")
        # If the model returned columns_used, validate; otherwise just check SQL string
        used_cols_lower = set([c.lower() for c in plan.get("columns_used", [])])
        forbidden_in_sql = [c for c in FORBIDDEN_COLUMNS if c in sql.lower()]
        forbidden_in_list = list(used_cols_lower.intersection(FORBIDDEN_COLUMNS))
        forbidden_all = sorted(set(forbidden_in_sql + forbidden_in_list))

        if forbidden_all:
            logger.error(f"Forbidden columns detected in plan: {forbidden_all}. Regenerating plan without them.")
            regen_prompt = prompt + f"\n\nDo not use these columns: {', '.join(sorted(FORBIDDEN_COLUMNS))}. Regenerate a compliant answer now."
            response2 = agent.invoke([HumanMessage(content=regen_prompt)])
            response_dict2, parse_error2 = safe_json_parse(response2.content)
            if parse_error2:
                logger.error(f"Error parsing regenerated classification response: {parse_error2}")
                return state
            is_valid2, validation_error2 = validate_classification_plan(response_dict2)
            if not is_valid2:
                logger.error(f"Invalid regenerated plan: {validation_error2}")
                return state
            response_dict = response_dict2

        # Also filter any forbidden columns from feature_columns defensively
        features = response_dict.get("feature_columns", [])
        response_dict["feature_columns"] = [c for c in features if c and c.lower() not in FORBIDDEN_COLUMNS]

        # Validate and extract SQL query
        sql_query = response_dict.get("SQL", "")
        if not isinstance(sql_query, str):
            logger.error(f"SQL query is not a string. Type: {type(sql_query)}, Value: {sql_query}")
            return state
        
        sql_query = sql_query.strip()
        if not sql_query:
            logger.error("Generated SQL query is empty")
            return state
        
        # Check for excessive SQL length (potential column duplication)
        if len(sql_query) > 50000:  # 50KB limit
            logger.warning(f"Generated SQL is extremely long ({len(sql_query)} chars) - possible column duplication")
            
            # Try to clean up duplicate columns
            try:
                sql_query = clean_duplicate_columns(sql_query)
                logger.info(f"Cleaned SQL length: {len(sql_query)} chars")
            except Exception as e:
                logger.warning(f"Could not clean SQL duplicates: {e}")
            
            # Truncate for logging
            logger.info(f"SQL Query (truncated): {sql_query[:1000]}...")
        else:
            logger.info(f"Generated SQL for classification: {sql_query}")
        
        # Avoid showing the massive raw dataset in the UI; we'll present samples later
        state["show_data"] = False
        state["classification_plan"] = response_dict
        state["sql_query"] = sql_query
        logger.info(f"Generated XGBoost args : {response_dict['xgboost_args']}")
        logger.info(f"Target column : {response_dict['target_column']}")
    except Exception as e:
        logger.error(f"Error updating state with classification plan: {e}")
        return state
    
    return state


def validate_dataset(df: pd.DataFrame, classification_plan: Dict) -> tuple[bool, str]:
    """
    Validate dataset has required columns and sufficient data.
    
    Args:
        df: Input dataframe
        classification_plan: Classification configuration
        
    Returns:
        tuple: (is_valid, error_message)
    """
    target_col = classification_plan.get("target_column")
    feature_cols = classification_plan.get("feature_columns", [])

    # Normalize column names for matching
    cols_lower = {c.lower(): c for c in df.columns}

    # Resolve target column robustly
    candidate_targets = []
    if isinstance(target_col, str):
        candidate_targets.append(target_col)
    candidate_targets.extend(["target_column", "target", "label", "y"])  # common aliases

    resolved_target = None
    for cand in candidate_targets:
        # exact
        if cand in df.columns:
            resolved_target = cand
            break
        # case-insensitive
        if cand.lower() in cols_lower:
            resolved_target = cols_lower[cand.lower()]
            break

    if resolved_target is None:
        return False, f"Target column '{target_col}' not found in dataset. Available columns: {list(df.columns)}"

    # Persist resolved target in plan
    target_col = resolved_target
    classification_plan["target_column"] = target_col

    # Ensure features exclude the target column and exist in df
    feature_cols = [c for c in feature_cols if c is not None]
    # case-insensitive resolution for features
    resolved_features = []
    for f in feature_cols:
        if f in df.columns:
            resolved_features.append(f)
        else:
            fl = f.lower()
            if fl in cols_lower:
                resolved_features.append(cols_lower[fl])
    # Remove target if present
    resolved_features = [c for c in resolved_features if c != target_col]

    # If too many features missing, fall back to auto-selecting numeric/categorical
    if len(resolved_features) < 2:
        logger.warning("Insufficient feature overlap; auto-selecting features from dataset")
        # Prefer non-identifier, non-target columns
        exclude = set([target_col])
        # Keep simple heuristic: include up to 20 columns aside from target
        auto_features = [c for c in df.columns if c not in exclude]
        # Avoid obvious identifiers if present
        auto_features = [c for c in auto_features if not any(k in c.lower() for k in ["id", "sk", "guid"])] or auto_features
        resolved_features = auto_features[:20]

    classification_plan["feature_columns"] = resolved_features
    
    try:
        class_counts = df[target_col].value_counts()
    except Exception:
        return False, f"Target column '{target_col}' could not be analyzed for class distribution."
    min_class_size = class_counts.min()
    
    if min_class_size < 5:
        logger.warning(f"Class imbalance detected. Smallest class has only {min_class_size} samples. Proceeding with imbalance handling.")
        classification_plan["class_imbalance_warning"] = True
    
    # Check for stratification compatibility (training will fallback if needed)
    if min_class_size < 2:
        logger.warning(f"Very small class size ({min_class_size}); disabling stratified split.")
        classification_plan["disable_stratify"] = True
    
    return True, "Valid dataset"


def optimize_memory_usage(df: pd.DataFrame) -> pd.DataFrame:
    """
    Optimize dataframe memory usage by downcasting numeric types.
    
    Args:
        df: Input dataframe
        
    Returns:
        Memory-optimized dataframe
    """
    logger.info(f"Original memory usage: {df.memory_usage(deep=True).sum() / 1024**2:.2f} MB")
    
    # Downcast integers
    for col in df.select_dtypes(include=['int64']).columns:
        df[col] = pd.to_numeric(df[col], downcast='integer')
    
    # Downcast floats
    for col in df.select_dtypes(include=['float64']).columns:
        df[col] = pd.to_numeric(df[col], downcast='float')
    
    # Convert object columns to category if cardinality is low
    for col in df.select_dtypes(include=['object']).columns:
        if df[col].nunique() / len(df) < 0.5:  # Less than 50% unique values
            df[col] = df[col].astype('category')
    
    logger.info(f"Optimized memory usage: {df.memory_usage(deep=True).sum() / 1024**2:.2f} MB")
    return df


def train_xgboost(df, classification_plan):
    """
    Core XGBoost model training and classification engine.
    
    Args:
        df: DataFrame with features and target variable
        classification_plan: Dictionary containing model configuration
        
    Returns:
        tuple: (trained_model, predictions_df, metrics_dict)
    """
    logger.info(f"Training XGBoost with params : {classification_plan['xgboost_args']}")
    
    # Check memory usage before processing
    memory_stats = check_memory_usage()
    logger.info(f"Memory usage before training: {memory_stats['memory_mb']:.2f} MB ({memory_stats['memory_percent']:.1f}%)")
    
    try:
        # Validate dataset first
        is_valid, validation_error = validate_dataset(df, classification_plan)
        if not is_valid:
            logger.error(f"Dataset validation failed: {validation_error}")
            # st.error(f"Dataset validation failed: {validation_error}")
            return None, None, None, None
        
        # Extract configuration
        target_col = classification_plan["target_column"]
        feature_cols = classification_plan["feature_columns"]
        xgb_args = classification_plan["xgboost_args"]
        preprocessing_args = classification_plan["preprocessing_args"]
        
        # Optimize memory usage for large datasets
        if len(df) > 10000:
            logger.info("Large dataset detected. Optimizing memory usage...")
            df = optimize_memory_usage(df)
            gc.collect()  # Force garbage collection
        
        # Prepare features and target with error handling
        try:
            X = df[feature_cols].copy()
            y = df[target_col].copy()
            logger.info(f"Target Column : {target_col}")
            logger.info(f"y")
        except KeyError as e:
            missing_cols = [col for col in feature_cols + [target_col] if col not in df.columns]
            error_msg = f"Missing columns in dataset: {missing_cols}"
            logger.error(error_msg)
            # st.error(error_msg)
            return None, None, None, None
        
        logger.info(f"Dataset shape: {X.shape}, Target distribution: {y.value_counts().to_dict()}")
        
        # Normalize dtypes: fix category/object columns that are actually numeric
        def to_numeric_if_possible(s: pd.Series) -> pd.Series:
            # Try to coerce strings like '1,234' or '12.3%' into numbers
            try:
                s_str = s.astype(str).str.replace(',', '', regex=False).str.replace('%', '', regex=False).str.strip()
                s_num = pd.to_numeric(s_str, errors='coerce')
                # If most values became numeric, accept the conversion
                non_na_ratio = s_num.notna().mean()
                if non_na_ratio >= 0.95:
                    return s_num
            except Exception:
                pass
            return s

        for col in X.columns:
            if str(X[col].dtype) in ['category', 'object']:
                X[col] = to_numeric_if_possible(X[col])

        # Convert datetime columns to numeric timestamps (seconds since epoch)
        try:
            from pandas.api.types import is_datetime64_any_dtype
            datetime_cols = [col for col in X.columns if is_datetime64_any_dtype(X[col])]
            if datetime_cols:
                logger.info(f"Converting datetime columns to numeric: {datetime_cols}")
                for col in datetime_cols:
                    ser = pd.to_datetime(X[col], errors='coerce')
                    X[col] = (ser.astype('int64') // 10**9)
            # Also attempt to parse object columns that look like dates by name
            candidate_date_cols = [
                col for col in X.columns 
                if str(X[col].dtype) == 'object' and any(k in col.lower() for k in ['date', 'datetime', 'time'])
            ]
            for col in candidate_date_cols:
                ser = pd.to_datetime(X[col], errors='coerce')
                if ser.notna().mean() > 0.5:  # if at least half parse
                    X[col] = (ser.astype('int64') // 10**9)
        except Exception as e:
            logger.warning(f"Failed converting datetime columns: {e}")

        # Handle missing values
        if preprocessing_args.get("handle_missing", True):
            # Fill numeric columns with median
            numeric_cols = X.select_dtypes(include=[np.number]).columns
            X[numeric_cols] = X[numeric_cols].fillna(X[numeric_cols].median())
            
            # Fill categorical columns with mode
            categorical_cols = X.select_dtypes(include=['object']).columns
            for col in categorical_cols:
                X[col] = X[col].fillna(X[col].mode()[0] if len(X[col].mode()) > 0 else 'Unknown')
        
        # Encode categorical variables (both object and category dtypes)
        label_encoders = {}
        if preprocessing_args.get("encode_categorical", True):
            categorical_cols = X.select_dtypes(include=['object', 'category']).columns
            for col in categorical_cols:
                le = LabelEncoder()
                X[col] = le.fit_transform(X[col].astype(str))
                label_encoders[col] = le

        # Final safety: ensure all remaining non-numeric columns are coerced to numeric via label encoding
        non_numeric_cols = [c for c in X.columns if not np.issubdtype(X[c].dtype, np.number)]
        for col in non_numeric_cols:
            le = LabelEncoder()
            X[col] = le.fit_transform(X[col].astype(str))
            label_encoders[col] = le

        # Ensure no datetime64 columns remain (convert to epoch seconds if any slipped through)
        try:
            dt_cols_late = [c for c in X.columns if str(X[c].dtype).startswith('datetime64')]
            if dt_cols_late:
                logger.info(f"Converting lingering datetime columns to epoch seconds: {dt_cols_late}")
                for col in dt_cols_late:
                    ser = pd.to_datetime(X[col], errors='coerce')
                    X[col] = (ser.astype('int64') // 10**9)
        except Exception as e:
            logger.warning(f"Late datetime coercion failed: {e}")

        # If category dtype remains, enable XGBoost native categorical handling
        if any(str(dt) == 'category' for dt in X.dtypes) and 'enable_categorical' not in xgb_args:
            xgb_args = {**xgb_args, 'enable_categorical': True}
        
        # Check for single-class problem before encoding
        unique_classes = y.nunique()
        if unique_classes < 2:
            error_msg = f"Cannot train classifier: Only {unique_classes} unique class found in target variable. Need at least 2 classes. Target distribution: {y.value_counts().to_dict()}"
            logger.error(error_msg)
            return None, None, None, None
        
        # Encode target variable if it's categorical
        target_encoder = None
        if y.dtype == 'object':
            target_encoder = LabelEncoder()
            y = target_encoder.fit_transform(y)
        
        # Verify we still have multiple classes after encoding
        unique_encoded_classes = pd.Series(y).nunique()
        if unique_encoded_classes < 2:
            error_msg = f"After encoding, only {unique_encoded_classes} unique class remains. Original classes: {pd.Series(y).value_counts().to_dict()}"
            logger.error(error_msg)
            return None, None, None, None
        
        # Scale features if requested
        scaler = None
        if preprocessing_args.get("scale_features", False):
            scaler = StandardScaler()
            X = pd.DataFrame(scaler.fit_transform(X), columns=X.columns, index=X.index)
        
        # Split the data with improved error handling
        test_size = preprocessing_args.get("test_size", 0.2)
        
        try:
            if classification_plan.get("disable_stratify"):
                raise ValueError("Stratify disabled due to small class size")
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=test_size, random_state=42, stratify=y
            )
        except ValueError as e:
            # Fallback: try without stratification if it fails
            logger.warning(f"Stratified split failed: {e}. Trying without stratification.")
            try:
                X_train, X_test, y_train, y_test = train_test_split(
                    X, y, test_size=test_size, random_state=42
                )
            except Exception as e2:
                logger.error(f"Train-test split failed: {e2}")
                return None, None, None, None
        
        logger.info(f"Training set: {X_train.shape}, Test set: {X_test.shape}")
        
        # Handle binary class imbalance by setting scale_pos_weight if not provided
        if classification_plan.get("problem_type") == "binary" and "scale_pos_weight" not in xgb_args:
            try:
                # Attempt to compute for 0/1 targets
                pos = (y_train == 1).sum()
                neg = (y_train == 0).sum()
                if pos > 0 and neg > 0:
                    xgb_args = {**xgb_args, "scale_pos_weight": float(neg) / float(pos)}
                    logger.info(f"Auto set scale_pos_weight={xgb_args['scale_pos_weight']:.3f} for class imbalance")
            except Exception as e:
                logger.warning(f"Could not auto-set scale_pos_weight: {e}")

        # Train XGBoost model
        model = xgb.XGBClassifier(**xgb_args)
        model.fit(X_train, y_train)
        
        logger.info("Training Complete.")
        logger.info("Generating predictions...")
        
        # Make predictions
        y_pred = model.predict(X_test)
        y_pred_proba = model.predict_proba(X_test)
        
        # Create results DataFrame
        results_df = X_test.copy()
        results_df['Actual'] = y_test
        results_df['Predicted'] = y_pred
        
        # Add probability columns
        if classification_plan["problem_type"] == "binary":
            results_df['Probability'] = y_pred_proba[:, 1]  # Probability of positive class
        else:
            # For multiclass, add probability for each class
            classes = model.classes_
            for i, class_name in enumerate(classes):
                results_df[f'Prob_Class_{class_name}'] = y_pred_proba[:, i]
        
        # Calculate metrics
        metrics = {}
        
        # Classification report
        if target_encoder:
            y_test_original = target_encoder.inverse_transform(y_test)
            y_pred_original = target_encoder.inverse_transform(y_pred)
            class_report = classification_report(y_test_original, y_pred_original, output_dict=True)
        else:
            class_report = classification_report(y_test, y_pred, output_dict=True)
        
        metrics['classification_report'] = class_report
        metrics['accuracy'] = class_report['accuracy']
        
        # ROC AUC for binary classification
        if classification_plan["problem_type"] == "binary":
            try:
                auc_score = roc_auc_score(y_test, y_pred_proba[:, 1])
                metrics['roc_auc'] = auc_score
            except Exception as e:
                logger.warning(f"Could not calculate ROC AUC: {e}")
        
        # Final memory check
        final_memory = check_memory_usage()
        logger.info(f"Memory usage after training: {final_memory['memory_mb']:.2f} MB ({final_memory['memory_percent']:.1f}%)")
        
        return model, results_df, metrics
        
    except Exception as e:
        logger.error(f"Error in XGBoost training: {e}")
        # st.error(f"Error in model training: {e}")
        return None, None, None, None


def classify(state: State):
    """
    Orchestrates the classification process and UI updates.
    
    Args:
        state: LangGraph state containing classification data and plan
        
    Returns:
        Updated state with classification results
    """
    # status = st.status("Training classification model...")
    logger.info("Classification in progress.")
    
    try:
        # Ensure data is a DataFrame (execute_sql stores dict)
        raw_data = state.get("data")
        data_train = pd.DataFrame(raw_data) if not isinstance(raw_data, pd.DataFrame) else raw_data
        classification_plan = state["classification_plan"]
        
        # Train the model
        model, results_df, metrics = train_xgboost(data_train, classification_plan)
        state["metrics"] = metrics
        if model is None:
            # st.error("Model training failed. Please check the data and try again.")
            return state
        # ----------------------------
        # Business-facing results
        # ----------------------------
        # 1) Determine probability column
        prob_col = None
        if 'Probability' in results_df.columns:
            prob_col = 'Probability'
        else:
            pos_label = classification_plan.get('positive_class_label') if isinstance(classification_plan, dict) else None
            if pos_label is not None:
                cand = f"Prob_Class_{pos_label}"
                if cand in results_df.columns:
                    prob_col = cand
                else:
                    try:
                        cand2 = f"Prob_Class_{int(pos_label)}"
                        if cand2 in results_df.columns:
                            prob_col = cand2
                    except Exception:
                        pass
            if prob_col is None:
                prob_matches = [c for c in results_df.columns if c.startswith('Prob_Class_')]
                prob_col = prob_matches[0] if prob_matches else None

        # 2) Attach identifier columns from plan or heuristic
        plan_ids = classification_plan.get('identifier_columns', []) if isinstance(classification_plan, dict) else []
        heuristic_ids = [c for c in data_train.columns if any(k in c.lower() for k in [
            'dimcustomersk','customersk','customer','account','contact','email','phone','id','sk','guid'
        ])]
        id_candidates = [c for c in (list(plan_ids) + heuristic_ids) if c in data_train.columns]
        id_candidates = list(dict.fromkeys(id_candidates))
        if id_candidates:
            try:
                results_df[id_candidates] = data_train.loc[results_df.index, id_candidates]
            except Exception as e:
                logger.warning(f"Could not attach identifier columns: {e}")

        # 3) Top 100 likely customers
        top_likely_df = None
        if prob_col is not None:
            cols = (id_candidates + [prob_col]) if id_candidates else [prob_col]
            top_likely_df = results_df.sort_values(prob_col, ascending=False).loc[:, cols].head(1000).copy()
            state["classification_data"] = top_likely_df.to_dict()
    

        # Show predictions sample (limit rows) and provide download for full set
        display_cols = ['Actual', 'Predicted'] + [col for col in results_df.columns if 'Prob' in col]
        sample_df = results_df[display_cols].head(1000).copy()
        
        # Convert numpy types to native Python types for serialization
        def convert_numpy_types(obj):
            if isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, dict):
                return {k: convert_numpy_types(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_numpy_types(v) for v in obj]
            return obj
        
        # Update state with lightweight results only (avoid pushing full dataframe to websocket)
        state["classification_results"] = {
            "predictions_sample": sample_df.to_dict(),
            "metrics": convert_numpy_types(metrics),
            "training_timestamp": datetime.now().isoformat(),
            "top_likely": {} if top_likely_df is None else top_likely_df.to_dict(),
            "business_summary": {
                "probability_column": prob_col,
            }
        }
        
        logger.info("Classification process completed successfully.")
        
    except Exception as e:
        logger.error(f"Error in classification process: {e}")
        st.error(f"Classification failed: {e}")
    
    return state


def predict_new_data(model, new_data, preprocessing_objects, classification_plan):
    """
    Make predictions on new data using trained model.
    
    Args:
        model: Trained XGBoost model
        new_data: DataFrame with new data to predict
        preprocessing_objects: Dictionary with encoders and scalers
        classification_plan: Original classification configuration
        
    Returns:
        DataFrame with predictions and probabilities
    """
    try:
        # Validate input data
        feature_cols = preprocessing_objects['feature_columns']
        missing_cols = [col for col in feature_cols if col not in new_data.columns]
        
        if missing_cols:
            logger.error(f"Missing feature columns in new data: {missing_cols}")
            return None
        
        # Prepare features
        X_new = new_data[feature_cols].copy()
        
        # Check for memory constraints
        if len(X_new) > 50000:
            logger.warning(f"Large prediction dataset: {len(X_new)} rows. Consider batch processing.")
            # Process in chunks for very large datasets
            chunk_size = 10000
            results_list = []
            
            for i in range(0, len(X_new), chunk_size):
                chunk = X_new.iloc[i:i+chunk_size]
                chunk_result = _process_prediction_chunk(model, chunk, new_data.iloc[i:i+chunk_size], 
                                                       preprocessing_objects, classification_plan)
                if chunk_result is not None:
                    results_list.append(chunk_result)
            
            if results_list:
                return pd.concat(results_list, ignore_index=True)
            else:
                return None
        
        # Apply same preprocessing as training
        # Handle missing values
        numeric_cols = X_new.select_dtypes(include=[np.number]).columns
        X_new[numeric_cols] = X_new[numeric_cols].fillna(X_new[numeric_cols].median())
        
        categorical_cols = X_new.select_dtypes(include=['object']).columns
        for col in categorical_cols:
            X_new[col] = X_new[col].fillna('Unknown')
        
        # Apply label encoders
        label_encoders = preprocessing_objects['label_encoders']
        for col, encoder in label_encoders.items():
            if col in X_new.columns:
                # Handle unseen categories
                X_new[col] = X_new[col].astype(str)
                known_classes = set(encoder.classes_)
                X_new[col] = X_new[col].apply(lambda x: x if x in known_classes else 'Unknown')
                
                # If 'Unknown' is not in encoder classes, add it
                if 'Unknown' not in known_classes:
                    encoder.classes_ = np.append(encoder.classes_, 'Unknown')
                
                X_new[col] = encoder.transform(X_new[col])
        
        # Apply scaler if used
        scaler = preprocessing_objects['scaler']
        if scaler is not None:
            X_new = pd.DataFrame(scaler.transform(X_new), columns=X_new.columns, index=X_new.index)
        
        # Make predictions
        predictions = model.predict(X_new)
        probabilities = model.predict_proba(X_new)
        
        # Create results
        results = new_data.copy()
        results['Predicted'] = predictions
        
        # Add probabilities
        if classification_plan["problem_type"] == "binary":
            results['Probability'] = probabilities[:, 1]
        else:
            classes = model.classes_
            for i, class_name in enumerate(classes):
                results[f'Prob_Class_{class_name}'] = probabilities[:, i]
        
        # Decode predictions if target was encoded
        target_encoder = preprocessing_objects['target_encoder']
        if target_encoder is not None:
            results['Predicted'] = target_encoder.inverse_transform(predictions)
        
        return results
        
    except Exception as e:
        logger.error(f"Error in prediction: {e}")
        return None


def _process_prediction_chunk(model, X_chunk, data_chunk, preprocessing_objects, classification_plan):
    """
    Process a chunk of data for prediction (used for large datasets).
    
    Args:
        model: Trained model
        X_chunk: Feature chunk
        data_chunk: Original data chunk
        preprocessing_objects: Preprocessing components
        classification_plan: Classification configuration
        
    Returns:
        Predictions for the chunk
    """
    try:
        # Apply same preprocessing as training
        # Handle missing values
        numeric_cols = X_chunk.select_dtypes(include=[np.number]).columns
        X_chunk[numeric_cols] = X_chunk[numeric_cols].fillna(X_chunk[numeric_cols].median())
        
        categorical_cols = X_chunk.select_dtypes(include=['object']).columns
        for col in categorical_cols:
            X_chunk[col] = X_chunk[col].fillna('Unknown')
        
        # Apply label encoders
        label_encoders = preprocessing_objects['label_encoders']
        for col, encoder in label_encoders.items():
            if col in X_chunk.columns:
                # Handle unseen categories
                X_chunk[col] = X_chunk[col].astype(str)
                known_classes = set(encoder.classes_)
                X_chunk[col] = X_chunk[col].apply(lambda x: x if x in known_classes else 'Unknown')
                
                # If 'Unknown' is not in encoder classes, add it
                if 'Unknown' not in known_classes:
                    encoder.classes_ = np.append(encoder.classes_, 'Unknown')
                
                X_chunk[col] = encoder.transform(X_chunk[col])
        
        # Apply scaler if used
        scaler = preprocessing_objects['scaler']
        if scaler is not None:
            X_chunk = pd.DataFrame(scaler.transform(X_chunk), columns=X_chunk.columns, index=X_chunk.index)
        
        # Make predictions
        predictions = model.predict(X_chunk)
        probabilities = model.predict_proba(X_chunk)
        
        # Create results
        results = data_chunk.copy()
        results['Predicted'] = predictions
        
        # Add probabilities
        if classification_plan["problem_type"] == "binary":
            results['Probability'] = probabilities[:, 1]
        else:
            classes = model.classes_
            for i, class_name in enumerate(classes):
                results[f'Prob_Class_{class_name}'] = probabilities[:, i]
        
        # Decode predictions if target was encoded
        target_encoder = preprocessing_objects['target_encoder']
        if target_encoder is not None:
            results['Predicted'] = target_encoder.inverse_transform(predictions)
        
        return results
        
    except Exception as e:
        logger.error(f"Error processing prediction chunk: {e}")
        return None
