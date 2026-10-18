"""
Multi-Sector Data Alignment and Wrangling Pipeline.
Handles:
1. Parsing heterogeneous timestamp formats across independent feeds
2. Timezone conversion and Daylight Saving Time (DST) normalization per metro area
3. Hourly temporal resampling and aggregation of 15-minute multi-sector business telemetry
4. Telemetry gap imputation and meteorological cleaning
5. Feature engineering (temperature anomalies, precipitation tiers, lag structures, calendar controls)
6. Cross-sector elasticity indicators & spillover metrics
"""

import os
import json
import numpy as np
import pandas as pd

CITY_TZ_MAPPING = {
    "NYC": "America/New_York",
    "ORD": "America/Chicago",
    "SEA": "America/Los_Angeles",
    "PHX": "America/Phoenix"
}

CITY_NAMES = {
    "NYC": "New York City",
    "ORD": "Chicago",
    "SEA": "Seattle",
    "PHX": "Phoenix"
}

US_HOLIDAYS_DATES = {
    "2023-01-01": "New Year's Day", "2023-01-16": "MLK Day", "2023-02-12": "Super Bowl LVII",
    "2023-05-29": "Memorial Day", "2023-07-04": "Independence Day", "2023-09-04": "Labor Day",
    "2023-10-31": "Halloween", "2023-11-23": "Thanksgiving", "2023-12-25": "Christmas Day", "2023-12-31": "New Year's Eve",
    "2024-01-01": "New Year's Day", "2024-01-15": "MLK Day", "2024-02-11": "Super Bowl LVIII",
    "2024-05-27": "Memorial Day", "2024-07-04": "Independence Day", "2024-09-02": "Labor Day",
    "2024-10-31": "Halloween", "2024-11-28": "Thanksgiving", "2024-12-25": "Christmas Day", "2024-12-31": "New Year's Eve"
}


class MultiSourceDataPipeline:
    def __init__(self, raw_dir, processed_dir):
        self.raw_dir = raw_dir
        self.processed_dir = processed_dir
        self.audit_log = {}
        
    def load_raw_sources(self):
        """Loads the raw unaligned CSV datasets."""
        weather_file = os.path.join(self.raw_dir, "weather_sensor_telemetry_raw.csv")
        business_file = os.path.join(self.raw_dir, "business_cross_sector_raw.csv")
        
        if not os.path.exists(business_file):
            business_file = os.path.join(self.raw_dir, "business_pos_logistics_raw.csv")
            
        print(f"Loading weather telemetry from {weather_file}...")
        df_weather_raw = pd.read_csv(weather_file)
        
        print(f"Loading cross-sector business stream from {business_file}...")
        df_business_raw = pd.read_csv(business_file)
        
        self.audit_log["raw_weather_rows"] = len(df_weather_raw)
        self.audit_log["raw_business_rows"] = len(df_business_raw)
        self.audit_log["raw_weather_cols"] = list(df_weather_raw.columns)
        self.audit_log["raw_business_cols"] = list(df_business_raw.columns)
        
        return df_weather_raw, df_business_raw
        
    def process_weather_data(self, df_weather_raw):
        """
        Cleans weather telemetry, parses UTC timestamps, localizes to each city's IANA timezone,
        creates complete regular hourly grids, and imputes missing sensor telemetry.
        """
        print("Standardizing meteorological telemetry...")
        df_weather = df_weather_raw.copy()
        
        df_weather["timestamp_utc"] = pd.to_datetime(df_weather["timestamp_utc"], utc=True)
        processed_city_weather = []
        imputation_stats = {}
        
        for city, tz_name in CITY_TZ_MAPPING.items():
            city_w = df_weather[df_weather["metro_area"] == city].copy()
            city_w = city_w.sort_values("timestamp_utc").drop_duplicates(subset=["timestamp_utc"])
            
            # Localize to City timezone
            city_w["timestamp_local"] = city_w["timestamp_utc"].dt.tz_convert(tz_name)
            
            min_ts = city_w["timestamp_local"].min().floor("h")
            max_ts = city_w["timestamp_local"].max().ceil("h")
            full_hourly_index = pd.date_range(start=min_ts, end=max_ts, freq="h", tz=tz_name, name="timestamp_local")
            
            city_w = city_w.set_index("timestamp_local")
            missing_hours_count = len(full_hourly_index) - len(city_w)
            
            city_w_grid = city_w.reindex(full_hourly_index)
            city_w_grid["metro_area"] = city
            city_w_grid["station_identifier"] = city_w["station_identifier"].dropna().iloc[0] if len(city_w) > 0 else ""
            
            null_temps = city_w_grid["air_temp_deg_c"].isna().sum()
            null_precip = city_w_grid["precip_accumulation_mm"].isna().sum()
            
            # Imputation
            city_w_grid["air_temp_deg_c"] = city_w_grid["air_temp_deg_c"].interpolate(method="time").bfill().ffill()
            city_w_grid["apparent_temp_c"] = city_w_grid["apparent_temp_c"].interpolate(method="time").bfill().ffill()
            city_w_grid["sustained_wind_kmh"] = city_w_grid["sustained_wind_kmh"].interpolate(method="time").bfill().ffill()
            city_w_grid["relative_humidity_pct"] = city_w_grid["relative_humidity_pct"].interpolate(method="time").bfill().ffill()
            
            city_w_grid["precip_accumulation_mm"] = city_w_grid["precip_accumulation_mm"].fillna(0.0)
            city_w_grid["snow_depth_delta_cm"] = city_w_grid["snow_depth_delta_cm"].fillna(0.0)
            city_w_grid["met_condition"] = city_w_grid["met_condition"].ffill().bfill()
            
            # Recompute uniform UTC timestamp column
            city_w_grid["timestamp_utc"] = city_w_grid.index.tz_convert("UTC")
            city_w_grid["timestamp_local_str"] = city_w_grid.index.strftime("%Y-%m-%d %H:%M:%S")
            city_w_grid = city_w_grid.reset_index(drop=True)
            
            imputation_stats[city] = {
                "missing_hours_interpolated": int(missing_hours_count),
                "null_temps_imputed": int(null_temps),
                "null_precip_imputed": int(null_precip)
            }
            processed_city_weather.append(city_w_grid)
            
        df_clean_weather = pd.concat(processed_city_weather, ignore_index=True)
        self.audit_log["weather_imputation_stats"] = imputation_stats
        print(f" Meteorological grid reconstructed: {len(df_clean_weather):,} complete hourly rows.")
        return df_clean_weather

    def process_business_data(self, df_biz_raw):
        """
        Parses US-formatted localized POS/business timestamps, normalizes timezones per region,
        and aggregates 15-minute operational intervals across 6 sectors into synchronized hourly metrics.
        """
        print("Standardizing multi-sector business stream & aggregating to hourly bins...")
        df_biz = df_biz_raw.copy()
        
        # Parse US format: 'MM/DD/YYYY hh:mm AM/PM' -> naive datetime
        df_biz["naive_dt"] = pd.to_datetime(df_biz["pos_timestamp_local"], format="%m/%d/%Y %I:%M %p")
        
        processed_city_biz = []
        
        for city, tz_name in CITY_TZ_MAPPING.items():
            city_b = df_biz[df_biz["region_code"] == city].copy()
            city_b = city_b.sort_values("naive_dt").reset_index(drop=True)
            
            # Localize naive datetime to city's specific IANA timezone safely
            try:
                city_b["timestamp_local"] = city_b["naive_dt"].dt.tz_localize(
                    tz_name, ambiguous="infer", nonexistent="shift_forward"
                )
            except Exception:
                city_b["timestamp_local"] = city_b["naive_dt"].dt.tz_localize(
                    tz_name, ambiguous="NaT", nonexistent="shift_forward"
                ).ffill()
                
            city_b = city_b.dropna(subset=["timestamp_local"])
            
            # Floor to hourly interval for temporal aggregation
            city_b["hourly_bin"] = city_b["timestamp_local"].dt.floor("h")
            
            has_multisector = "bikeshare_trips_count" in city_b.columns
            
            agg_dict = {
                "delivery_order_count": ("delivery_order_count" if "delivery_order_count" in city_b.columns else "gross_order_count", "sum"),
                "delivery_gmv_usd": ("delivery_gmv_usd" if "delivery_gmv_usd" in city_b.columns else "estimated_gmv_usd", "sum"),
                "active_couriers": ("active_couriers" if "active_couriers" in city_b.columns else "active_courier_count", "mean"),
                "surge_pricing_mult": ("surge_pricing_mult", "mean"),
                "delivery_duration_min": ("delivery_duration_min" if "delivery_duration_min" in city_b.columns else "mean_delivery_duration_min", "mean"),
                "cancellation_rate_pct": ("cancellation_rate_pct" if "cancellation_rate_pct" in city_b.columns else "order_cancellation_pct", "mean"),
                "avg_basket_usd": ("avg_basket_usd" if "avg_basket_usd" in city_b.columns else "avg_basket_value_usd", "mean"),
            }
            
            if has_multisector:
                agg_dict.update({
                    "bikeshare_trips_count": ("bikeshare_trips_count", "sum"),
                    "public_transit_ridership": ("public_transit_ridership", "sum"),
                    "rideshare_trip_count": ("rideshare_trip_count", "sum"),
                    "traffic_congestion_pct": ("traffic_congestion_pct", "mean"),
                    "retail_mall_footfall": ("retail_mall_footfall", "sum"),
                    "rainwear_sales_idx": ("rainwear_sales_idx", "mean"),
                    "winter_apparel_idx": ("winter_apparel_idx", "mean"),
                    "ecommerce_orders_count": ("ecommerce_orders_count", "sum"),
                    "restaurant_dinein_guests": ("restaurant_dinein_guests", "sum"),
                    "patio_occupancy_pct": ("patio_occupancy_pct", "mean"),
                    "hot_comfort_food_idx": ("hot_comfort_food_idx", "mean"),
                    "cold_beverage_icecream_idx": ("cold_beverage_icecream_idx", "mean"),
                    "electricity_grid_load_mw": ("electricity_grid_load_mw", "mean"),
                    "hvac_demand_idx": ("hvac_demand_idx", "mean"),
                    "freight_delay_min": ("freight_delay_min", "mean"),
                    "warehouse_shipments_count": ("warehouse_shipments_count", "sum")
                })
                
            hourly_agg = city_b.groupby("hourly_bin").agg(**agg_dict).reset_index()
            
            # Format numeric metrics
            for col in hourly_agg.columns:
                if col != "hourly_bin":
                    if any(kw in col for kw in ["count", "ridership", "footfall", "guests", "shipments"]):
                        hourly_agg[col] = hourly_agg[col].round(0).astype(int)
                    else:
                        hourly_agg[col] = hourly_agg[col].round(2)
                        
            # Store timestamp in UTC and local string for uniform merging
            hourly_agg["timestamp_utc"] = hourly_agg["hourly_bin"].dt.tz_convert("UTC")
            hourly_agg["timestamp_local_str"] = hourly_agg["hourly_bin"].dt.strftime("%Y-%m-%d %H:%M:%S")
            
            # Extract local calendar components while in timezone object
            hourly_agg["hour_of_day"] = hourly_agg["hourly_bin"].dt.hour
            hourly_agg["day_of_week"] = hourly_agg["hourly_bin"].dt.dayofweek
            hourly_agg["day_name"] = hourly_agg["hourly_bin"].dt.day_name()
            hourly_agg["month"] = hourly_agg["hourly_bin"].dt.month
            hourly_agg["month_name"] = hourly_agg["hourly_bin"].dt.month_name()
            hourly_agg["year"] = hourly_agg["hourly_bin"].dt.year
            hourly_agg["date_str"] = hourly_agg["hourly_bin"].dt.strftime("%Y-%m-%d")
            
            hourly_agg["metro_area"] = city
            hourly_agg["region_name"] = CITY_NAMES[city]
            hourly_agg = hourly_agg.drop(columns=["hourly_bin"])
            
            processed_city_biz.append(hourly_agg)
            
        df_clean_biz = pd.concat(processed_city_biz, ignore_index=True)
        print(f" Aggregated business streams into {len(df_clean_biz):,} synchronized hourly records.")
        return df_clean_biz

    def merge_and_engineer_features(self, df_clean_weather, df_clean_biz):
        """
        Merges weather and business streams on (metro_area, timestamp_utc),
        and constructs rich econometric and domain-specific analytical features across all sectors.
        """
        print("Performing spatial-temporal alignment merge...")
        
        # Merge on UTC timestamp and metro_area (bulletproof unambiguous join)
        merged = pd.merge(
            df_clean_biz,
            df_clean_weather.drop(columns=["timestamp_local_str"], errors="ignore"),
            on=["metro_area", "timestamp_utc"],
            how="inner"
        )
        
        print(f" Merged dataset aligned: {len(merged):,} synchronized hourly observations.")
        
        # --- FEATURE ENGINEERING ---
        # 1. Calendar & Temporal Features
        merged["is_weekend"] = merged["day_of_week"].isin([5, 6]).astype(int)
        merged["is_holiday"] = merged["date_str"].isin(US_HOLIDAYS_DATES).astype(int)
        merged["holiday_name"] = merged["date_str"].map(US_HOLIDAYS_DATES).fillna("None")
        
        def get_meal_period(hr):
            if 6 <= hr < 11:
                return "Breakfast (06-11)"
            elif 11 <= hr < 15:
                return "Lunch (11-15)"
            elif 15 <= hr < 17:
                return "Afternoon Lull (15-17)"
            elif 17 <= hr < 22:
                return "Dinner Peak (17-22)"
            else:
                return "Late Night (22-06)"
                
        merged["meal_period"] = merged["hour_of_day"].apply(get_meal_period)
        
        # 2. Meteorological Tiering & Non-Linear Buckets
        merged["is_raining"] = (merged["precip_accumulation_mm"] > 0.05).astype(int)
        merged["is_snowing"] = (merged["snow_depth_delta_cm"] > 0.1).astype(int)
        merged["has_precipitation"] = ((merged["is_raining"] == 1) | (merged["is_snowing"] == 1)).astype(int)
        
        def categorize_rain(mm):
            if mm <= 0.05:
                return "0. None (0 mm)"
            elif mm <= 2.0:
                return "1. Light (0.1 - 2 mm/h)"
            elif mm <= 6.0:
                return "2. Moderate (2 - 6 mm/h)"
            else:
                return "3. Heavy / Storm (>6 mm/h)"
                
        merged["rain_intensity_tier"] = merged["precip_accumulation_mm"].apply(categorize_rain)
        
        def categorize_temp(tc):
            if tc < 0:
                return "Freezing (< 0°C)"
            elif tc < 10:
                return "Cold (0 - 10°C)"
            elif tc < 20:
                return "Mild (10 - 20°C)"
            elif tc < 30:
                return "Warm (20 - 30°C)"
            else:
                return "Extreme Heat (> 30°C)"
                
        merged["temp_tier"] = merged["air_temp_deg_c"].apply(categorize_temp)
        
        # 3. Lag and Dynamics Structures (per city time series)
        merged = merged.sort_values(["metro_area", "timestamp_utc"]).reset_index(drop=True)
        city_groups = merged.groupby("metro_area")
        merged["precip_lag_1h"] = city_groups["precip_accumulation_mm"].shift(1).fillna(0.0)
        merged["precip_lag_2h"] = city_groups["precip_accumulation_mm"].shift(2).fillna(0.0)
        merged["precip_onset_delta"] = merged["precip_accumulation_mm"] - merged["precip_lag_1h"]
        
        # 4. Seasonal Baseline Temperature & Temperature Anomalies (Temperature Shocks)
        baseline_temp_map = merged.groupby(["metro_area", "month", "hour_of_day"])["air_temp_deg_c"].transform("mean")
        merged["expected_seasonal_temp_c"] = np.round(baseline_temp_map, 2)
        merged["temp_anomaly_deg_c"] = np.round(merged["air_temp_deg_c"] - merged["expected_seasonal_temp_c"], 2)
        
        # 5. Energy Metrics: Cooling & Heating Degree Days (hourly equivalent)
        merged["cooling_degree_hours"] = np.maximum(0, merged["air_temp_deg_c"] - 18.33)
        merged["heating_degree_hours"] = np.maximum(0, 18.33 - merged["air_temp_deg_c"])
        
        # 6. Cross-Sector Spillover & Elasticity Ratios
        if "delivery_order_count" in merged.columns and "active_couriers" in merged.columns:
            merged["courier_utilization_ratio"] = np.round(
                merged["delivery_order_count"] / np.maximum(1, merged["active_couriers"]), 2
            )
            
        if "restaurant_dinein_guests" in merged.columns and "delivery_order_count" in merged.columns:
            merged["delivery_to_dinein_ratio"] = np.round(
                merged["delivery_order_count"] / np.maximum(1, merged["restaurant_dinein_guests"]), 2
            )
            
        if "rideshare_trip_count" in merged.columns and "bikeshare_trips_count" in merged.columns:
            merged["rideshare_to_bike_ratio"] = np.round(
                merged["rideshare_trip_count"] / np.maximum(1, merged["bikeshare_trips_count"]), 2
            )
            
        return merged

    def run_pipeline(self):
        """Executes the full pipeline and saves parquet and audit telemetry."""
        os.makedirs(self.processed_dir, exist_ok=True)
        
        df_weather_raw, df_biz_raw = self.load_raw_sources()
        df_clean_weather = self.process_weather_data(df_weather_raw)
        df_clean_biz = self.process_business_data(df_biz_raw)
        
        df_merged = self.merge_and_engineer_features(df_clean_weather, df_clean_biz)
        
        parquet_path = os.path.join(self.processed_dir, "weather_business_merged.parquet")
        csv_sample_path = os.path.join(self.processed_dir, "weather_business_merged_sample.csv")
        audit_path = os.path.join(self.processed_dir, "pipeline_audit_telemetry.json")
        
        print(f"Saving merged multi-sector dataset to {parquet_path}...")
        df_merged.to_parquet(parquet_path, index=False)
        df_merged.head(1000).to_csv(csv_sample_path, index=False)
        
        self.audit_log["total_processed_rows"] = len(df_merged)
        self.audit_log["cities"] = list(df_merged["metro_area"].unique())
        self.audit_log["date_range_start"] = str(df_merged["timestamp_utc"].min())
        self.audit_log["date_range_end"] = str(df_merged["timestamp_utc"].max())
        self.audit_log["columns"] = list(df_merged.columns)
        self.audit_log["sectors_covered"] = [
            "On-Demand Logistics & Food Delivery",
            "Urban Transport & Micromobility",
            "Retail & Clothing Apparel",
            "Food & Hospitality (Dine-in vs Delivery)",
            "Energy Grid & Utilities Demand",
            "Supply Chain & Freight Logistics"
        ]
        
        with open(audit_path, "w") as f:
            json.dump(self.audit_log, f, indent=2)
            
        print(f" Pipeline executed successfully! Output saved to {parquet_path}")
        return df_merged


if __name__ == "__main__":
    base_raw = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "raw"))
    base_proc = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "processed"))
    pipeline = MultiSourceDataPipeline(base_raw, base_proc)
    pipeline.run_pipeline()
