"""
backend/tasks.py

Celery tasks for StratLab analytics.
"""

import sys
import pathlib
from pathlib import Path

# Add project root to path
ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from celery import Celery, shared_task
from backend.compute import run_factor_model
import traceback

# Create Celery app instance
celery = Celery('stratlab')
celery.conf.update(
    broker_url='redis://redis:6379/0',
    result_backend='redis://redis:6379/0',
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)


@celery.task(bind=True)
def factor_analysis(self, file_path: str, priors: dict = None):
    """
    Run factor analysis on uploaded data.
    
    Args:
        file_path: Path to the uploaded CSV/parquet file
        priors: Dictionary of analysis parameters (e.g., {"lambda": 0.1})
    
    Returns:
        dict: Analysis results with summary, charts, etc.
    """
    try:
        # Validate file exists
        if not Path(file_path).exists():
            raise FileNotFoundError(f"Data file not found: {file_path}")
        
        # Ensure priors is a dict with only numeric values
        if priors is None:
            priors = {}
        
        # Clean priors to ensure only numeric values
        clean_priors = {}
        for key, value in priors.items():
            try:
                # Try to convert to float, skip if not possible
                clean_priors[key] = float(value)
            except (ValueError, TypeError):
                print(f"Skipping non-numeric prior: {key}={value}")
                continue
        
        # Run the analysis using our compute module
        result = run_factor_model(file_path, clean_priors)
        
        return result
        
    except Exception as e:
        # Log the full traceback for debugging
        error_traceback = traceback.format_exc()
        print(f"Task failed with error: {str(e)}")
        print(f"Full traceback: {error_traceback}")
        
        # Re-raise with a cleaner error message for specific issues
        error_msg = str(e)
        if "could not convert string to float" in error_msg:
            if "2025-01-01" in error_msg or any(char in error_msg for char in ['-', '/']):
                raise ValueError(
                    "Data processing error: Found date strings in numeric columns. "
                    "Please ensure your data has dates only in the 'Date' column and "
                    "numeric values in 'Px' and 'Ret' columns."
                )
        
        # Re-raise the original exception for other errors
        raise e


# Optional: Add a simpler test task for debugging
@celery.task
def test_data_loading(file_path: str):
    """Test task to check data loading and basic processing."""
    try:
        from backend.compute import _read_and_clean
        
        df = _read_and_clean(file_path)
        
        # Convert datetime and other non-JSON-serializable types
        dtypes_dict = {}
        for col, dtype in df.dtypes.items():
            if 'datetime' in str(dtype):
                dtypes_dict[col] = 'datetime64'
            else:
                dtypes_dict[col] = str(dtype)
        
        # Convert sample data to JSON-serializable format
        sample_data = df.head().copy()
        for col in sample_data.columns:
            if 'datetime' in str(sample_data[col].dtype):
                sample_data[col] = sample_data[col].dt.strftime('%Y-%m-%d')
        
        return {
            "success": True,
            "shape": list(df.shape),  # Convert tuple to list
            "columns": df.columns.tolist(),
            "dtypes": dtypes_dict,
            "sample_data": sample_data.to_dict(),
            "date_range": {
                "min": df["Date"].min().strftime('%Y-%m-%d'),
                "max": df["Date"].max().strftime('%Y-%m-%d')
            }
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }