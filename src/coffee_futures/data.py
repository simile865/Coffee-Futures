"""Data loading module for coffee futures"""

import pandas as pd
from pathlib import Path


def load_data(filepath: str) -> pd.DataFrame:
    """
    Load coffee futures data from file.
    
    Args:
        filepath: Path to data file (CSV or Excel)
        
    Returns:
        DataFrame with loaded data
    """
    path = Path(filepath)
    
    if path.suffix == '.csv':
        return pd.read_csv(filepath)
    elif path.suffix in ['.xls', '.xlsx']:
        return pd.read_excel(filepath)
    else:
        raise ValueError(f"Unsupported file format: {path.suffix}")
