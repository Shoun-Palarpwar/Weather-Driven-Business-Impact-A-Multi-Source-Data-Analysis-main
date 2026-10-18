"""
Automated unit and integration test suite for Weather-Driven Business Impact Analysis.
"""

import os
import sys
import pytest
import pandas as pd
import numpy as np

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.data_generator import generate_weather_data, generate_cross_sector_business_data
from src.data_pipeline import MultiSourceDataPipeline
from src.econometrics import WeatherEconometricsEngine


def test_data_generation_shapes():
    """Verify data generators create expected schemas and columns."""
    df_weather = generate_weather_data(start_date="2023-01-01", end_date="2023-01-07")
    df_biz = generate_cross_sector_business_data(start_date="2023-01-01", end_date="2023-01-07")
    
    assert len(df_weather) > 0
    assert "timestamp_utc" in df_weather.columns
    assert "air_temp_deg_c" in df_weather.columns
    assert "precip_accumulation_mm" in df_weather.columns
    
    assert len(df_biz) > 0
    assert "pos_timestamp_local" in df_biz.columns
    assert "delivery_order_count" in df_biz.columns
    assert "bikeshare_trips_count" in df_biz.columns
    assert "electricity_grid_load_mw" in df_biz.columns


def test_pipeline_alignment(tmp_path):
    """Test full pipeline end-to-end alignment on temporary directories."""
    raw_dir = tmp_path / "raw"
    proc_dir = tmp_path / "processed"
    raw_dir.mkdir()
    proc_dir.mkdir()
    
    df_w = generate_weather_data(start_date="2023-01-01", end_date="2023-01-05")
    df_b = generate_cross_sector_business_data(start_date="2023-01-01", end_date="2023-01-05")
    
    df_w.to_csv(raw_dir / "weather_sensor_telemetry_raw.csv", index=False)
    df_b.to_csv(raw_dir / "business_cross_sector_raw.csv", index=False)
    
    pipeline = MultiSourceDataPipeline(str(raw_dir), str(proc_dir))
    df_merged = pipeline.run_pipeline()
    
    assert len(df_merged) > 0
    assert "timestamp_utc" in df_merged.columns
    assert "temp_anomaly_deg_c" in df_merged.columns
    assert "rain_intensity_tier" in df_merged.columns
    assert "courier_utilization_ratio" in df_merged.columns
    assert df_merged["air_temp_deg_c"].isna().sum() == 0


def test_econometric_scenario_simulation():
    """Verify econometric engine generates valid predictions and causal cascades."""
    data_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "processed", "weather_business_merged.parquet"))
    if not os.path.exists(data_path):
        pytest.skip("Processed dataset not found yet.")
        
    engine = WeatherEconometricsEngine(data_path)
    engine.fit_sector_models()
    
    sim = engine.simulate_cross_sector_scenario(
        city="NYC",
        day_of_week=4,
        hour_of_day=19,
        rain_mm=10.0,
        temp_anomaly_c=-4.0
    )
    
    assert "by_sector" in sim
    assert "causal_ripples" in sim
    assert len(sim["causal_ripples"]) >= 2
    assert "On-Demand Logistics" in sim["by_sector"]
    assert "Urban Mobility & Transit" in sim["by_sector"]
    assert "Energy & Grid Infrastructure" in sim["by_sector"]


if __name__ == "__main__":
    pytest.main(["-v", __file__])
