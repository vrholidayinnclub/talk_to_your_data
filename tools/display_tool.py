"""
Display Tool
Formats and displays data in terminal.
"""

import json
import logging
import pandas as pd

logger = logging.getLogger(__name__)


def display_data_tool(data_json: str, title: str = "Data") -> str:
    """
    Display data in terminal.
    
    Args:
        data_json: JSON string with data
        title: Display title
        
    Returns:
        Formatted string
    """
    logger.info(f"TOOL: display_data - {title}")
    
    try:
        data_dict = json.loads(data_json)
        
        output = []
        output.append(f"\n{'=' * 80}")
        output.append(f"{title:^80}")
        output.append(f"{'=' * 80}\n")
        
        if 'data' in data_dict:
            df = pd.DataFrame(data_dict['data'])
            output.append(f"Rows: {len(df)}\n")
            output.append(df.head(10).to_string())
        elif 'forecast_data' in data_dict:
            df = pd.DataFrame(data_dict['forecast_data'])
            output.append(f"Forecast Rows: {len(df)}\n")
            output.append(df.tail(10).to_string())
        elif 'predictions' in data_dict:
            df = pd.DataFrame(data_dict['predictions'])
            output.append(f"Top Customers: {len(df)}\n")
            output.append(df.head(10).to_string())
        else:
            output.append(str(data_dict))
        
        output.append(f"\n{'=' * 80}\n")
        
        result = "\n".join(output)
        print(result)
        
        return result
        
    except Exception as e:
        logger.error(f"Display data failed: {str(e)}")
        return f"Error: {str(e)}"
