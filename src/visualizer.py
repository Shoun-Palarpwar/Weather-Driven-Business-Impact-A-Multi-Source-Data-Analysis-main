"""
Visualizer Suite for Weather-Driven Cross-Sector Impact Analysis.
Generates interactive Plotly and static charts for:
1. Naive Correlation vs Econometric Fixed-Effects Elasticity
2. Multi-Sector Scenario Radar & Bar Comparisons
3. Non-Linear Operational Tipping Points (Supply-Demand Bottlenecks)
4. Multi-Source Ingestion & Timezone Harmonization Diagnostics
5. Multi-Hop Causal Chain Flow Diagram
"""

import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np

# Theme palette (Tailored HSL / Slate & Emerald & Amber & Rose)
PALETTE = {
    "primary": "#3B82F6",    # Electric Blue
    "secondary": "#10B981",  # Emerald Green
    "warning": "#F59E0B",    # Amber
    "danger": "#EF4444",     # Rose Red
    "purple": "#8B5CF6",     # Indigo/Purple
    "dark": "#1E293B",       # Slate Dark
    "light": "#F8FAFC",      # Slate Light
    "grid": "#E2E8F0"
}


def create_scenario_impact_chart(flat_metrics_df):
    """
    Creates an interactive horizontal bar chart showing percentage impact across all sectors.
    """
    df = flat_metrics_df.copy()
    df["color"] = np.where(df["delta_pct"] >= 0, PALETTE["secondary"], PALETTE["danger"])
    
    fig = px.bar(
        df,
        x="delta_pct",
        y="display_name",
        color="sector",
        orientation="h",
        labels={"delta_pct": "% Impact vs Baseline", "display_name": "Operational / Economic Metric"},
        title="Cross-Sector Marginal Impact Breakdown (% Shift from Clear Weather Baseline)",
        template="plotly_white",
        color_discrete_sequence=[PALETTE["primary"], PALETTE["secondary"], PALETTE["warning"], PALETTE["purple"], "#06B6D4", "#EC4899"]
    )
    
    fig.update_layout(
        font=dict(family="Inter, sans-serif", size=12),
        margin=dict(l=20, r=20, t=50, b=30),
        xaxis=dict(zeroline=True, zerolinewidth=2, zerolinecolor="#64748B", gridcolor=PALETTE["grid"]),
        yaxis=dict(autorange="reversed"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig


def create_naive_vs_fixed_effects_plot(comp_df):
    """
    Creates a grouped bar comparison showing Naive Correlation vs True Elasticity.
    """
    fig = go.Figure()
    
    df_sample = comp_df.head(10).copy()
    
    fig.add_trace(go.Bar(
        x=df_sample["Metric"],
        y=df_sample["Naive Corr (Rain)"],
        name="Naive Pearson Corr (Rain)",
        marker_color="#94A3B8"
    ))
    
    # Extract numerical elasticity
    df_sample["clean_rain_pct"] = df_sample["True Rain Elasticity (%/mm)"].str.replace("%", "").astype(float) / 10.0
    
    fig.add_trace(go.Bar(
        x=df_sample["Metric"],
        y=df_sample["clean_rain_pct"],
        name="True Isolated Rain Elasticity (Scaled %/mm)",
        marker_color=PALETTE["primary"]
    ))
    
    fig.update_layout(
        title="Naive Correlation vs Econometric Fixed-Effects Elasticity (Controlling for Day, Hour & Season)",
        barmode="group",
        template="plotly_white",
        font=dict(family="Inter, sans-serif"),
        margin=dict(l=20, r=20, t=50, b=40),
        xaxis=dict(tickangle=-30),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig


def create_operational_tipping_point_chart(df):
    """
    Shows the non-linear inflection curve where delivery duration and cancellations spike as rain exceeds 4mm/hr.
    """
    rain_bins = pd.cut(df["precip_accumulation_mm"], bins=[0, 0.5, 2.0, 5.0, 10.0, 25.0], labels=["0mm (Dry)", "0.1-2mm (Light)", "2-5mm (Moderate)", "5-10mm (Heavy)", ">10mm (Extreme)"])
    agg = df.groupby(rain_bins, observed=True).agg({
        "delivery_order_count": "mean",
        "active_couriers": "mean",
        "delivery_duration_min": "mean",
        "cancellation_rate_pct": "mean",
        "surge_pricing_mult": "mean"
    }).reset_index()
    
    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=("Demand vs Active Courier Supply", "Delivery Delays & Order Cancellations"),
        specs=[[{"secondary_y": True}, {"secondary_y": True}]]
    )
    
    # Subplot 1
    fig.add_trace(go.Bar(x=agg["precip_accumulation_mm"], y=agg["delivery_order_count"], name="Delivery Orders", marker_color=PALETTE["primary"]), row=1, col=1, secondary_y=False)
    fig.add_trace(go.Scatter(x=agg["precip_accumulation_mm"], y=agg["active_couriers"], name="Active Couriers", line=dict(color=PALETTE["danger"], width=3)), row=1, col=1, secondary_y=True)
    
    # Subplot 2
    fig.add_trace(go.Scatter(x=agg["precip_accumulation_mm"], y=agg["delivery_duration_min"], name="Delivery Mins", line=dict(color=PALETTE["warning"], width=3)), row=1, col=2, secondary_y=False)
    fig.add_trace(go.Scatter(x=agg["precip_accumulation_mm"], y=agg["cancellation_rate_pct"], name="Cancel %", line=dict(color=PALETTE["danger"], width=3, dash="dot")), row=1, col=2, secondary_y=True)
    
    fig.update_layout(
        title_text="Operational Non-Linear Tipping Points: Rain Threshold Severity Dynamics",
        template="plotly_white",
        font=dict(family="Inter, sans-serif"),
        showlegend=True,
        margin=dict(l=20, r=20, t=50, b=30),
        legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="center", x=0.5)
    )
    return fig


def create_temperature_u_curve(df):
    """
    Illustrates U-shaped energy grid response and hot vs cold beverage consumption across temperature regimes.
    """
    temp_bins = pd.cut(df["air_temp_deg_c"], bins=[-15, 0, 10, 20, 30, 45], labels=["<0°C (Freeze)", "0-10°C (Cold)", "10-20°C (Mild)", "20-30°C (Warm)", ">30°C (Heatwave)"])
    agg = df.groupby(temp_bins, observed=True).agg({
        "electricity_grid_load_mw": "mean",
        "hot_comfort_food_idx": "mean",
        "cold_beverage_icecream_idx": "mean",
        "patio_occupancy_pct": "mean"
    }).reset_index()
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=agg["air_temp_deg_c"], y=agg["electricity_grid_load_mw"], name="Grid Load (MW)", line=dict(color=PALETTE["warning"], width=3.5)))
    fig.add_trace(go.Scatter(x=agg["air_temp_deg_c"], y=agg["hot_comfort_food_idx"]*20, name="Hot Comfort Food (scaled)", line=dict(color=PALETTE["danger"], width=2.5, dash="dash")))
    fig.add_trace(go.Scatter(x=agg["air_temp_deg_c"], y=agg["cold_beverage_icecream_idx"]*20, name="Cold Beverage/Ice Cream (scaled)", line=dict(color=PALETTE["primary"], width=2.5, dash="dot")))
    
    fig.update_layout(
        title="Thermal Elasticity & U-Shaped Energy / Beverage Response Curves",
        xaxis_title="Ambient Air Temperature Tier",
        yaxis_title="Demand Level / Megawatt Load",
        template="plotly_white",
        font=dict(family="Inter, sans-serif"),
        margin=dict(l=20, r=20, t=50, b=30),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig


def create_timezone_alignment_inspector(weather_raw_sample, pos_raw_sample, aligned_sample):
    """
    Returns visual summary tables for the Data Wrangling diagnostic tab.
    """
    weather_snippet = weather_raw_sample[["timestamp_utc", "metro_area", "air_temp_deg_c", "precip_accumulation_mm", "met_condition"]].head(5)
    pos_snippet = pos_raw_sample[["pos_timestamp_local", "region_code", "delivery_order_count" if "delivery_order_count" in pos_raw_sample.columns else "gross_order_count", "active_couriers" if "active_couriers" in pos_raw_sample.columns else "active_courier_count", "surge_pricing_mult"]].head(5)
    aligned_snippet = aligned_sample[["timestamp_utc", "timestamp_local_str", "metro_area", "air_temp_deg_c", "precip_accumulation_mm", "delivery_order_count", "surge_pricing_mult", "traffic_congestion_pct"]].head(5)
    
    return weather_snippet, pos_snippet, aligned_snippet
