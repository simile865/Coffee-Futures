"""Analysis module for coffee futures data"""

import pandas as pd
import numpy as np


def analyze_futures(data: pd.DataFrame) -> dict:
    """
    Analyze coffee futures data.
    
    Args:
        data: DataFrame containing futures data
        
    Returns:
        Dictionary with analysis results
    """
    return {
        "mean": data.mean().to_dict(),
        "std": data.std().to_dict(),
        "correlation": data.corr().to_dict()
    }
