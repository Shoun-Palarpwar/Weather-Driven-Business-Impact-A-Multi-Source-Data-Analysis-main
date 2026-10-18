"""
Multi-Sector Data Generator for Weather-Driven Business Impact Analysis.
Generates two distinct, mismatched raw datasets:
1. Hourly Weather Sensor Telemetry (UTC, ISO timestamps, sensor gaps, metric units)
2. 15-minute Cross-Industry Business & Operational Telemetry:
   - On-Demand Logistics (Food/Grocery delivery, active couriers, surge pricing, cancellations)
   - Urban Mobility (Bike-share/micromobility, public transit, rideshare, traffic congestion)
   - Retail & Clothing Apparel (Brick-and-mortar footfall, rainwear/winter apparel, e-commerce)
   - Hospitality & Dining (Dine-in guests, patio seating, hot comfort vs cold beverage indices)
   - Energy & Grid Demand (Grid peak megawatt load, HVAC demand)
   - Supply Chain & Freight (Transit delay minutes, warehouse dispatch throughput)
Across 4 diverse metro areas: NYC, Chicago (ORD), Seattle (SEA), Phoenix (PHX).
"""

import os
import numpy as np
import pandas as pd

def generate_weather_data(start_date="2023-01-01", end_date="2024-12-31", seed=42):
    """
    Generates realistic hourly weather data in UTC format across 4 cities.
    Includes diurnal cycles, seasonal dynamics, storm fronts, and sensor dropouts.
    """
    np.random.seed(seed)
    
    cities = {
        "NYC": {"station": "USW00094728", "tz": "America/New_York", "base_temp": 13.0, "temp_amp": 12.0, "rain_freq": 0.12},
        "ORD": {"station": "USW00094846", "tz": "America/Chicago", "base_temp": 10.5, "temp_amp": 15.0, "rain_freq": 0.11},
        "SEA": {"station": "USW00024233", "tz": "America/Los_Angeles", "base_temp": 11.5, "temp_amp": 7.5, "rain_freq": 0.22},
        "PHX": {"station": "USW00023183", "tz": "America/Phoenix", "base_temp": 24.0, "temp_amp": 12.0, "rain_freq": 0.04},
    }
    
    date_range = pd.date_range(start=start_date, end=end_date, freq="h", tz="UTC")
    total_hours = len(date_range)
    records = []
    
    for city_code, meta in cities.items():
        day_of_year = date_range.dayofyear.values
        hour_utc = date_range.hour.values
        
        tz_offset_approx = {"NYC": -5, "ORD": -6, "SEA": -8, "PHX": -7}[city_code]
        solar_hour = (hour_utc + tz_offset_approx) % 24
        
        # 1. Temperature modeling
        seasonal_temp = meta["base_temp"] - meta["temp_amp"] * np.cos(2 * np.pi * (day_of_year - 20) / 365.25)
        diurnal_temp = 4.5 * np.sin(2 * np.pi * (solar_hour - 8) / 24)
        
        front_shocks = np.zeros(total_hours)
        shock = 0
        for t in range(total_hours):
            shock = 0.96 * shock + np.random.normal(0, 0.8)
            front_shocks[t] = shock
            
        temp_c = seasonal_temp + diurnal_temp + front_shocks
        
        # 2. Rain / Precipitation modeling
        rain_mm = np.zeros(total_hours)
        storm_active = False
        storm_intensity = 0.0
        
        for t in range(total_hours):
            month = date_range[t].month
            monsoon_boost = 2.5 if (city_code == "PHX" and month in [7, 8]) else 1.0
            p_start = meta["rain_freq"] * 0.08 * monsoon_boost
            
            if not storm_active:
                if np.random.random() < p_start:
                    storm_active = True
                    storm_intensity = np.random.gamma(shape=2.0, scale=2.5)
            else:
                if np.random.random() < 0.25:
                    storm_active = False
                    storm_intensity = 0.0
                else:
                    storm_intensity = max(0.1, storm_intensity + np.random.normal(0, 0.8))
            
            if storm_active:
                rain_mm[t] = round(storm_intensity, 2)
                temp_c[t] -= min(3.0, storm_intensity * 0.4)
                
        # 3. Snowfall
        snow_cm = np.zeros(total_hours)
        snow_mask = (temp_c < 1.0) & (rain_mm > 0)
        snow_cm[snow_mask] = np.round(rain_mm[snow_mask] * np.random.uniform(0.8, 1.4, size=snow_mask.sum()), 2)
        rain_mm[snow_mask] = 0.0
        
        # 4. Wind Speed
        base_wind = 14.0 if city_code == "ORD" else 9.0
        wind_kmh = np.maximum(2.0, base_wind + (rain_mm * 1.8) + (snow_cm * 2.2) + np.random.weibull(1.8, total_hours) * 6.0)
        
        # 5. Humidity
        humidity = np.clip(55 + (rain_mm > 0) * 32 - (temp_c - 15) * 0.7 + np.random.normal(0, 5, total_hours), 15, 100)
        if city_code == "PHX":
            humidity = np.clip(humidity - 35 + (rain_mm > 0) * 40, 8, 85)
            
        # 6. Apparent temperature (Feels like)
        feels_like_c = temp_c.copy()
        cold_mask = temp_c < 10
        feels_like_c[cold_mask] = 13.12 + 0.6215 * temp_c[cold_mask] - 11.37 * (wind_kmh[cold_mask]**0.16) + 0.3965 * temp_c[cold_mask] * (wind_kmh[cold_mask]**0.16)
        hot_mask = temp_c > 27
        feels_like_c[hot_mask] = temp_c[hot_mask] + 0.33 * (humidity[hot_mask]/100 * 6.105 * np.exp(17.27 * temp_c[hot_mask] / (237.7 + temp_c[hot_mask]))) - 4.0
        
        weather_desc = []
        for r, s, t_val, w_val in zip(rain_mm, snow_cm, temp_c, wind_kmh):
            if s > 3.0 or (s > 0 and w_val > 35):
                weather_desc.append("Blizzard/Heavy Snow")
            elif s > 0:
                weather_desc.append("Light Snow")
            elif r > 8.0:
                weather_desc.append("Heavy Rainstorm")
            elif r > 2.0:
                weather_desc.append("Moderate Rain")
            elif r > 0.0:
                weather_desc.append("Light Drizzle")
            elif w_val > 38:
                weather_desc.append("High Wind Advisory")
            elif t_val > 38:
                weather_desc.append("Extreme Heat Wave")
            else:
                weather_desc.append("Clear/Overcast")
                
        city_df = pd.DataFrame({
            "timestamp_utc": date_range.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "station_identifier": meta["station"],
            "metro_area": city_code,
            "air_temp_deg_c": np.round(temp_c, 2),
            "apparent_temp_c": np.round(feels_like_c, 2),
            "precip_accumulation_mm": np.round(rain_mm, 2),
            "snow_depth_delta_cm": np.round(snow_cm, 2),
            "sustained_wind_kmh": np.round(wind_kmh, 1),
            "relative_humidity_pct": np.round(humidity, 1),
            "met_condition": weather_desc
        })
        
        # Introduce realistic sensor gaps
        keep_mask = np.random.random(len(city_df)) > 0.012
        for _ in range(6):
            outage_idx = np.random.randint(0, len(city_df) - 10)
            keep_mask[outage_idx:outage_idx + np.random.randint(3, 8)] = False
        city_df = city_df[keep_mask].copy()
        
        glitch_idx = np.random.choice(city_df.index, size=int(len(city_df)*0.003), replace=False)
        city_df.loc[glitch_idx, "relative_humidity_pct"] = np.nan
        records.append(city_df)
        
    weather_df = pd.concat(records, ignore_index=True)
    weather_df = weather_df.sort_values("timestamp_utc").reset_index(drop=True)
    return weather_df


def generate_cross_sector_business_data(start_date="2023-01-01", end_date="2024-12-31", seed=101):
    """
    Generates 15-minute point-of-sale and operational telemetry across 6 economic sectors:
    1. On-Demand Delivery & Logistics
    2. Urban Transport & Micromobility
    3. Retail & Clothing Apparel
    4. Food & Dining / Hospitality
    5. Energy Grid & Utilities
    6. Freight Logistics & Supply Chain
    """
    np.random.seed(seed)
    
    city_configs = {
        "NYC": {"tz": "America/New_York", "scale": 1.4, "base_grid_mw": 5800, "city_name": "New York City (Metro)"},
        "ORD": {"tz": "America/Chicago", "scale": 1.0, "base_grid_mw": 4200, "city_name": "Chicago Hub"},
        "SEA": {"tz": "America/Los_Angeles", "scale": 0.8, "base_grid_mw": 2900, "city_name": "Seattle Puget Sound"},
        "PHX": {"tz": "America/Phoenix", "scale": 0.75, "base_grid_mw": 3400, "city_name": "Phoenix Valley"},
    }
    
    us_holidays = {
        "2023-01-01": "New Year's Day", "2023-02-12": "Super Bowl LVII", "2023-07-04": "Independence Day",
        "2023-10-31": "Halloween", "2023-11-23": "Thanksgiving", "2023-12-25": "Christmas Day", "2023-12-31": "New Year's Eve",
        "2024-01-01": "New Year's Day", "2024-02-11": "Super Bowl LVIII", "2024-07-04": "Independence Day",
        "2024-10-31": "Halloween", "2024-11-28": "Thanksgiving", "2024-12-25": "Christmas Day", "2024-12-31": "New Year's Eve"
    }
    
    all_records = []
    
    for city_code, cfg in city_configs.items():
        local_range = pd.date_range(start=f"{start_date} 00:00:00", end=f"{end_date} 23:45:00", freq="15min", tz=cfg["tz"])
        n_periods = len(local_range)
        scale = cfg["scale"]
        
        hour = local_range.hour + local_range.minute / 60.0
        dow = local_range.dayofweek
        month = local_range.month
        date_str = local_range.strftime("%Y-%m-%d")
        
        # Temporal curves
        commute_morning = np.exp(-((hour - 8.2)**2) / 1.8) * 2.2
        lunch_curve = np.exp(-((hour - 12.5)**2) / 2.2) * 1.9
        commute_evening = np.exp(-((hour - 17.8)**2) / 2.0) * 2.6
        dinner_curve = np.exp(-((hour - 19.3)**2) / 3.2) * 3.4
        base_diurnal = 0.12 + commute_morning + lunch_curve + commute_evening + dinner_curve
        
        dow_multipliers = np.array([0.88, 0.90, 0.95, 1.05, 1.38, 1.48, 1.28])
        dow_effect = dow_multipliers[dow]
        
        is_holiday_arr = np.array([1.5 if d in us_holidays else 1.0 for d in date_str])
        
        # Approximate local weather trajectory
        temp_approx = (24.0 if city_code == "PHX" else 13.0) - (12.0 * np.cos(2 * np.pi * local_range.dayofyear / 365.25)) + 4.0 * np.sin(2 * np.pi * (hour - 8) / 24)
        
        rain_prob = 0.08 if city_code != "SEA" else 0.18
        if city_code == "PHX": rain_prob = 0.03
        
        rain_15m = np.zeros(n_periods)
        snow_15m = np.zeros(n_periods)
        in_storm = False
        storm_int = 0.0
        for i in range(n_periods):
            if not in_storm:
                if np.random.random() < (rain_prob * 0.03):
                    in_storm = True
                    storm_int = np.random.gamma(2.0, 1.8)
            else:
                if np.random.random() < 0.12:
                    in_storm = False
                    storm_int = 0.0
                else:
                    storm_int = max(0.05, storm_int + np.random.normal(0, 0.3))
            
            if in_storm:
                if temp_approx[i] < 1.0 and city_code in ["NYC", "ORD"]:
                    snow_15m[i] = storm_int * 0.8
                else:
                    rain_15m[i] = storm_int

        # ==========================================
        # 1. ON-DEMAND LOGISTICS & FOOD DELIVERY
        # ==========================================
        rain_demand_mult = 1.0 + np.minimum(0.48, rain_15m * 0.14)
        snow_demand_mult = 1.0 + np.minimum(0.65, snow_15m * 0.22)
        cold_boost = 1.0 + np.maximum(0, (10 - temp_approx) * 0.015)
        
        exp_delivery_orders = 300 * scale * base_diurnal * dow_effect * rain_demand_mult * snow_demand_mult * cold_boost * is_holiday_arr
        delivery_order_count = np.random.poisson(np.maximum(5, exp_delivery_orders))
        
        # Couriers drop out in bad weather
        courier_retention = np.maximum(0.55, 1.0 - rain_15m * 0.09 - snow_15m * 0.16)
        active_couriers = np.maximum(10, np.random.poisson(140 * scale * (0.35 + 0.65 * base_diurnal) * dow_effect * courier_retention))
        
        demand_supply_ratio = delivery_order_count / np.maximum(1, active_couriers)
        surge_mult = np.round(np.clip(1.0 + 0.45 * np.maximum(0, demand_supply_ratio - 1.8), 1.0, 2.5), 2)
        
        delivery_duration = np.round(np.clip(24.0 + 5.0 * np.maximum(0, demand_supply_ratio - 1.2)**1.5 + (rain_15m * 3.5) + (snow_15m * 6.5) + np.random.normal(0, 2.5, n_periods), 15.0, 75.0), 1)
        cancellation_rate = np.round(np.clip(1.2 + 0.008 * (delivery_duration - 20.0)**2 + (surge_mult - 1.0) * 4.0 + np.random.normal(0, 0.4, n_periods), 0.5, 30.0), 2)
        avg_basket_usd = np.round(np.maximum(18.0, 34.50 + 2.50 * (dow >= 4) + (rain_15m > 0) * 4.20 + (snow_15m > 0) * 6.80 + np.random.normal(0, 1.8, n_periods)), 2)
        delivery_gmv = np.round(delivery_order_count * (1 - cancellation_rate/100.0) * avg_basket_usd * surge_mult, 2)

        # ==========================================
        # 2. URBAN TRANSPORT & MOBILITY
        # ==========================================
        # Bike-share collapses heavily during rain/snow/extreme cold/heat
        bike_weather_penalty = np.exp(-(rain_15m * 1.5 + snow_15m * 3.0 + np.maximum(0, (5 - temp_approx)*0.1) + np.maximum(0, (temp_approx - 36)*0.08)))
        bikeshare_trips = np.maximum(0, np.random.poisson(250 * scale * (commute_morning + commute_evening + 0.4) * (dow < 5) * bike_weather_penalty + 5))
        
        # Public Transit (Bus/Subway): moderate increase in rain (people switch from walking/biking)
        transit_weather_boost = 1.0 + np.minimum(0.25, rain_15m * 0.05 + snow_15m * 0.08)
        public_transit_ridership = np.random.poisson(1800 * scale * (commute_morning * 1.4 + commute_evening * 1.5 + 0.3) * transit_weather_boost)
        
        # Rideshare Trips (Uber/Lyft): sharp surge when rain occurs (modal shift from walking/micromobility)
        rideshare_trips = np.random.poisson(450 * scale * (base_diurnal + 0.2) * dow_effect * (1.0 + np.minimum(0.55, rain_15m * 0.16 + snow_15m * 0.28)))
        
        # Traffic Congestion Index (%)
        traffic_congestion_pct = np.round(np.clip(25.0 + 18.0 * (commute_morning + commute_evening) + 12.0 * np.minimum(2.5, rain_15m) + 20.0 * np.minimum(2.0, snow_15m) + np.random.normal(0, 3.0, n_periods), 5.0, 98.0), 1)

        # ==========================================
        # 3. RETAIL & CLOTHING APPAREL
        # ==========================================
        # Physical mall foot traffic plunges in rain/snow; shifted to e-commerce
        mall_footfall_penalty = np.maximum(0.35, 1.0 - rain_15m * 0.14 - snow_15m * 0.28)
        dow_mall_mult = np.where(dow >= 4, 1.4, 0.9)
        retail_mall_footfall = np.random.poisson(600 * scale * np.maximum(0.1, np.sin(np.pi * (hour - 10)/11.0)) * dow_mall_mult * mall_footfall_penalty)
        
        # Rainwear & Umbrella Apparel Sales Index (100 = baseline)
        rainwear_sales_idx = np.round(np.clip(100.0 + (rain_15m > 0) * 180.0 * np.minimum(2.0, rain_15m) + np.random.normal(0, 8.0, n_periods), 60.0, 600.0), 1)
        
        # Winter Apparel Sales Index (boosted by cold & snow)
        winter_apparel_idx = np.round(np.clip(100.0 + np.maximum(0, (8.0 - temp_approx) * 14.0) + (snow_15m > 0) * 220.0 + np.random.normal(0, 10.0, n_periods), 40.0, 750.0), 1)
        
        # E-Commerce Online Orders
        ecommerce_orders = np.random.poisson(380 * scale * (0.6 + 0.4 * base_diurnal) * (1.0 + (rain_15m > 0) * 0.22 + (snow_15m > 0) * 0.35))

        # ==========================================
        # 4. FOOD & HOSPITALITY (DINE-IN VS DELIVERY)
        # ==========================================
        # Dine-in restaurant guests: drops in heavy rain/cold, shifting demand to delivery
        dinein_penalty = np.maximum(0.40, 1.0 - rain_15m * 0.15 - snow_15m * 0.30)
        restaurant_dinein_guests = np.random.poisson(550 * scale * (lunch_curve + dinner_curve) * dow_effect * dinein_penalty)
        
        # Outdoor Patio Seating Occupancy (%)
        patio_viable = (temp_approx >= 16.0) & (temp_approx <= 32.0) & (rain_15m == 0) & (snow_15m == 0)
        patio_occupancy_pct = np.round(np.clip(np.where(patio_viable, 65.0 + 25.0 * (dow >= 4) + np.random.normal(0, 5.0, n_periods), 0.0), 0.0, 100.0), 1)
        
        # Hot Comfort Food vs Cold Beverage Indices
        hot_comfort_food_idx = np.round(np.clip(100.0 + np.maximum(0, (14.0 - temp_approx) * 6.5) + (rain_15m > 0) * 35.0 + np.random.normal(0, 5.0, n_periods), 50.0, 300.0), 1)
        cold_beverage_icecream_idx = np.round(np.clip(100.0 + np.maximum(0, (temp_approx - 22.0) * 11.0) - (rain_15m > 0) * 40.0 + np.random.normal(0, 6.0, n_periods), 20.0, 450.0), 1)

        # ==========================================
        # 5. ENERGY & UTILITIES GRID
        # ==========================================
        # U-shaped electricity demand curve: high in extreme winter (heating) and extreme summer (air conditioning)
        cdd = np.maximum(0, temp_approx - 18.3)
        hdd = np.maximum(0, 18.3 - temp_approx)
        grid_load_mw = np.round(cfg["base_grid_mw"] * (0.75 + 0.25 * (hour >= 8) * (hour <= 22)) + cdd * 65.0 + hdd * 45.0 + np.random.normal(0, 40.0, n_periods), 1)
        hvac_demand_idx = np.round(np.clip(100.0 + cdd * 12.0 + hdd * 9.0 + np.random.normal(0, 4.0, n_periods), 60.0, 500.0), 1)

        # ==========================================
        # 6. SUPPLY CHAIN & FREIGHT LOGISTICS
        # ==========================================
        # Freight transit delays (minutes): compounded by rain/snow and traffic congestion
        freight_delay_min = np.round(np.clip(8.0 + (traffic_congestion_pct - 25.0) * 0.4 + (rain_15m * 8.0) + (snow_15m * 18.0) + np.random.normal(0, 3.0, n_periods), 0.0, 120.0), 1)
        warehouse_shipments = np.random.poisson(np.maximum(10, 220 * scale * (hour >= 7) * (hour <= 19) * np.maximum(0.6, 1.0 - snow_15m * 0.15)))

        local_ts_formatted = local_range.strftime("%m/%d/%Y %I:%M %p")
        
        city_business_df = pd.DataFrame({
            "pos_timestamp_local": local_ts_formatted,
            "region_code": city_code,
            "region_name": cfg["city_name"],
            # On-Demand
            "delivery_order_count": delivery_order_count,
            "active_couriers": active_couriers,
            "surge_pricing_mult": surge_mult,
            "delivery_duration_min": delivery_duration,
            "cancellation_rate_pct": cancellation_rate,
            "avg_basket_usd": avg_basket_usd,
            "delivery_gmv_usd": delivery_gmv,
            # Transport & Mobility
            "bikeshare_trips_count": bikeshare_trips,
            "public_transit_ridership": public_transit_ridership,
            "rideshare_trip_count": rideshare_trips,
            "traffic_congestion_pct": traffic_congestion_pct,
            # Retail & Apparel
            "retail_mall_footfall": retail_mall_footfall,
            "rainwear_sales_idx": rainwear_sales_idx,
            "winter_apparel_idx": winter_apparel_idx,
            "ecommerce_orders_count": ecommerce_orders,
            # Food & Hospitality
            "restaurant_dinein_guests": restaurant_dinein_guests,
            "patio_occupancy_pct": patio_occupancy_pct,
            "hot_comfort_food_idx": hot_comfort_food_idx,
            "cold_beverage_icecream_idx": cold_beverage_icecream_idx,
            # Energy & Grid
            "electricity_grid_load_mw": grid_load_mw,
            "hvac_demand_idx": hvac_demand_idx,
            # Supply Chain & Freight
            "freight_delay_min": freight_delay_min,
            "warehouse_shipments_count": warehouse_shipments
        })
        
        # Telemetry packet loss (0.5%)
        drop_mask = np.random.random(len(city_business_df)) > 0.005
        city_business_df = city_business_df[drop_mask].copy()
        
        all_records.append(city_business_df)
        
    business_df = pd.concat(all_records, ignore_index=True)
    # Return business dataframe
    return business_df


def generate_and_save_all(output_dir):
    os.makedirs(output_dir, exist_ok=True)
    
    print("Generating Raw Meteorological Telemetry (Source A)...")
    weather_df = generate_weather_data(start_date="2023-01-01", end_date="2024-12-31")
    weather_path = os.path.join(output_dir, "weather_sensor_telemetry_raw.csv")
    weather_df.to_csv(weather_path, index=False)
    print(f" Saved {len(weather_df):,} weather records to {weather_path}")
    
    print("Generating Raw Cross-Sector Business & Operational Stream (Source B)...")
    business_df = generate_cross_sector_business_data(start_date="2023-01-01", end_date="2024-12-31")
    business_path = os.path.join(output_dir, "business_cross_sector_raw.csv")
    business_df.to_csv(business_path, index=False)
    print(f" Saved {len(business_df):,} cross-sector business records to {business_path}")
    
    return weather_path, business_path


if __name__ == "__main__":
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "raw"))
    generate_and_save_all(base_dir)
