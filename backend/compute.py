"""
backend/compute.py

Defensive analytics engine for StratLab.
Uses parse_to_float to coerce any value into float where possible,
filtering out date strings or other garbage before calculations.
"""

from pathlib import Path
import json
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression


def parse_to_float(value) -> float | None:
    """
    Attempt to convert `value` to float.
    - If already numeric, returns float(value).
    - If string, first tries float(); if that fails, returns None.
    - Specifically handles date strings like '2025-01-01'
    """
    if value is None:
        return None
    if isinstance(value, (float, int)):
        return float(value)
    if isinstance(value, str):
        # Check if it looks like a date string (YYYY-MM-DD format)
        if len(value) == 10 and value.count('-') == 2:
            try:
                year, month, day = value.split('-')
                if len(year) == 4 and len(month) == 2 and len(day) == 2:
                    # It's likely a date string, return None
                    return None
            except:
                pass
    try:
        # Try direct conversion
        return float(value)
    except (ValueError, TypeError):
        return None


def safe_float_conversion_wrapper(func):
    """Decorator to catch and debug float conversion errors"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if "could not convert string to float" in str(e):
                print(f"ERROR in {func.__name__}: {str(e)}")
                print(f"Args: {args}")
                print(f"Kwargs: {kwargs}")
                # Try to identify problematic data
                for i, arg in enumerate(args):
                    if hasattr(arg, 'dtypes'):  # It's a DataFrame
                        print(f"DataFrame arg {i} dtypes:")
                        print(arg.dtypes)
                        print(f"DataFrame arg {i} sample data:")
                        print(arg.head())
            raise e
    return wrapper


def _read_and_clean(path: str | Path) -> pd.DataFrame:
    """
    Load data into pandas, parse Date, compute returns.
    Returns DataFrame with columns: Date, Symbol, Px, Ret (all numeric as needed).
    """
    p = Path(path)
    if p.suffix.lower() == ".parquet":
        df = pd.read_parquet(p)
    else:
        df = pd.read_csv(p, parse_dates=["Date"], infer_datetime_format=True)

    # Normalize and coerce types
    df = df.rename(columns={c: c.strip() for c in df.columns})
    df["Symbol"] = df["Symbol"].astype(str)
    df["Px"] = pd.to_numeric(df["Px"], errors="coerce")
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Symbol", "Px", "Date"])

    # Compute returns per symbol
    df = df.sort_values(["Symbol", "Date"])
    df["Ret"] = df.groupby("Symbol")["Px"].pct_change()
    df = df.dropna(subset=["Ret"])
    return df[["Date", "Symbol", "Px", "Ret"]]


def _var_es(arr: np.ndarray, level: float = 0.99) -> tuple[float, float]:
    """
    Compute parametric VaR & ES under Gaussian assumption.
    Input arr must be a 1D float array with no NaNs.
    """
    if arr.size == 0:
        return 0.0, 0.0
    mu = float(arr.mean())
    sigma = float(arr.std(ddof=1)) if arr.size > 1 else 0.0
    if sigma == 0.0:
        loss = max(0.0, -mu)
        return loss, loss
    z = abs(np.quantile(np.random.normal(size=100_000), 1 - level))
    var = mu - z * sigma
    es = mu - sigma * np.exp(-z**2 / 2) / (np.sqrt(2 * np.pi) * (1 - level))
    return float(max(0.0, -var)), float(max(0.0, -es))


def compute_risk(df: pd.DataFrame, level: float = 0.99) -> pd.DataFrame:
    """
    Compute VaR/ES per symbol.
    Uses parse_to_float on every return value to filter out any non-numeric entries.
    """
    records = []
    for sym, grp in df.groupby("Symbol", dropna=False):
        # Coerce Ret series to numeric, dropping bad values
        rets = grp["Ret"].map(parse_to_float).dropna().astype(float).values
        var, es = _var_es(np.array(rets, dtype=float), level)
        records.append({"Symbol": sym, "VaR": var, "ES": es})
    return pd.DataFrame(records)


@safe_float_conversion_wrapper
def factor_regression(df: pd.DataFrame, market: str = "SPY") -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    CAPM beta regression vs market.
    Pivot to wide, coerce all cells to float via parse_to_float, then drop NaNs.
    """
    # Pivot the returns
    wide = df.pivot(index="Date", columns="Symbol", values="Ret")
    
    # FIXED: Apply parse_to_float first, then convert to numeric using pd.to_numeric
    # This properly handles None values returned by parse_to_float
    for col in wide.columns:
        wide[col] = wide[col].map(parse_to_float)
    
    # Convert to numeric, coercing any remaining problematic values to NaN
    wide = wide.apply(pd.to_numeric, errors='coerce').dropna(how="any")

    cols = wide.columns.tolist()
    if market not in cols:
        market = cols[0] if cols else market
    if market not in cols or len(cols) < 2:
        return pd.DataFrame(columns=["Symbol", "Beta"]), pd.DataFrame(columns=["Symbol", "ResidualVar"])

    X = wide[[market]].values
    Y = wide.drop(columns=[market]).values
    assets = wide.drop(columns=[market]).columns.tolist()

    # Add safety check for empty data
    if X.size == 0 or Y.size == 0:
        return pd.DataFrame(columns=["Symbol", "Beta"]), pd.DataFrame(columns=["Symbol", "ResidualVar"])

    lr = LinearRegression().fit(X, Y)
    betas = pd.DataFrame({"Symbol": assets, "Beta": lr.coef_.flatten().tolist()})

    residuals = Y - lr.predict(X)
    resid_var = pd.DataFrame({
        "Symbol": assets,
        "ResidualVar": residuals.var(axis=0, ddof=1).tolist()
    })

    return betas, resid_var


def run_factor_model(file_path: str, priors: dict | None = None) -> dict:
    """
    Run the full pipeline:
    1) Read & clean data
    2) Compute risk metrics
    3) Compute factor regression
    4) Package results for Streamlit - ensuring all data is JSON serializable
    """
    try:
        df = _read_and_clean(file_path)

        risk_tbl = compute_risk(df)
        betas, resid = factor_regression(df)

        summary = (
            betas.merge(risk_tbl, on="Symbol")
                 .merge(resid, on="Symbol")
                 .sort_values("Symbol")
                 .reset_index(drop=True)
        )

        # Convert all data to JSON-serializable format
        # Ensure all numeric values are Python floats, not numpy types
        summary_dict = summary.copy()
        for col in summary_dict.select_dtypes(include=['number']).columns:
            summary_dict[col] = summary_dict[col].astype(float).tolist()
        
        # Convert DataFrame to dict format that's JSON serializable
        summary_json = {
            "data": summary_dict.to_dict('records'),  # List of dicts
            "schema": {"fields": [{"name": col, "type": "number" if summary[col].dtype.kind in 'biufc' else "string"} 
                                for col in summary.columns]}
        }

        return {
            "summary": summary_json,
            "var_chart": {
                "x": [str(x) for x in summary["Symbol"].tolist()], 
                "y": [float(x) for x in summary["VaR"].tolist()]
            },
            "beta_chart": {
                "x": [str(x) for x in summary["Symbol"].tolist()], 
                "y": [float(x) for x in summary["Beta"].tolist()]
            },
        }
    except Exception as e:
        # Add better error handling
        print(f"Error in run_factor_model: {str(e)}")
        return {
            "summary": {"data": [], "schema": {"fields": []}},
            "var_chart": {"x": [], "y": []},
            "beta_chart": {"x": [], "y": []},
            "error": str(e)
        }