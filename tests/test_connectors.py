"""
Unit tests for Real Revenue Connectors & Empirical Elasticity Estimation.
"""

import os
import sys
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.revenue_connectors import (
    SquareConnector,
    StripeConnector,
    CSVRevenueConnector,
    estimate_empirical_elasticities
)


def test_square_connector_sandbox():
    sq = SquareConnector()
    df = sq.fetch_daily_revenue(start_date="2024-01-01", end_date="2024-01-14", mock_profile="restaurant")
    assert len(df) == 14
    assert "revenue" in df.columns
    assert "date" in df.columns
    assert df["revenue"].mean() > 1000.0


def test_stripe_connector_sandbox():
    stripe = StripeConnector()
    df = stripe.fetch_daily_revenue(start_date="2024-01-01", end_date="2024-01-10", mock_profile="ecommerce")
    assert len(df) == 10
    assert "revenue" in df.columns
    assert "order_count" in df.columns
    assert df["revenue"].mean() > 5000.0


def test_csv_revenue_connector_fuzzy():
    raw_df = pd.DataFrame({
        "Transaction_Date": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"],
        "Gross_Sales_USD": ["$1,250.50", "$2,400.00", "$950.25", "$3,100.75"],
        "Customer_Notes": ["dine-in", "takeout", "dine-in", "event"]
    })
    connector = CSVRevenueConnector()
    df_clean, meta = connector.parse_dataframe(raw_df)
    assert len(df_clean) == 4
    assert "revenue" in df_clean.columns
    assert "date" in df_clean.columns
    assert df_clean["revenue"].sum() > 7000.0


def test_empirical_elasticity_regression():
    sq = SquareConnector()
    df_merchant = sq.fetch_daily_revenue("2023-01-01", "2023-03-31", mock_profile="restaurant")
    
    # Synthetic weather daily
    dates = pd.date_range("2023-01-01", "2023-03-31", freq="D")
    df_weather = pd.DataFrame({
        "date_str": dates.strftime("%Y-%m-%d"),
        "precip_accumulation_mm": np.random.exponential(2.5, len(dates)),
        "air_temp_deg_c": np.random.normal(12.0, 5.0, len(dates)),
        "temp_anomaly_deg_c": np.random.normal(0.0, 3.0, len(dates)),
        "snow_depth_delta_cm": np.zeros(len(dates))
    })
    
    res = estimate_empirical_elasticities(df_merchant, df_weather, "Test Merchant")
    assert res["status"] == "SUCCESS"
    assert "rain_elasticity" in res
    assert "temp_elasticity" in res
    assert "r_squared" in res
    assert res["r_squared"] > 0.10
    assert res["observations_count"] > 30


if __name__ == "__main__":
    pytest.main(["-v", __file__])
