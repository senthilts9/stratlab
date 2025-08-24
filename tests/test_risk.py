
import polars as pl
from backend.compute import compute_risk

def test_var():
    df = pl.DataFrame({
        'Date':['2025-01-01','2025-01-02','2025-01-03'],
        'Symbol':['XYZ']*3,
        'Px':[100,101,102]
    }).with_columns(pl.col('Px').pct_change().over('Symbol').alias('Ret')).drop_nulls()
    out = compute_risk(df,0.95)
    assert out['VaR'][0]>0 and out['ES'][0]>0
