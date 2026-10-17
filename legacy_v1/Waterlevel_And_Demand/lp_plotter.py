"""
lp_plotter.py
=============
Dedicated Visualization Engine for Kukule Ganga Future-Period LP Optimization Results
Component: Component 3 - Hydropower Generation & Reservoir Release Optimization Subsystem

Generates 4 research-quality Matplotlib graphs:
1. Graph 1 — Optimized Electricity Generation (generation_comparison.png)
   - Physical vs linear generation, 1,680 MWh/day station ceiling, unit outage limits.
2. Graph 2 — Reservoir Storage (reservoir_storage.png)
   - End-of-day active storage trajectory (MCM), FSL (1.67 MCM), MOL (0.0 MCM).
3. Graph 3 — Inflow, Turbine Release and Spill (inflow_release_spill.png)
   - Flow rates in m³/s for forecast inflow, turbine release, and spill.
4. Graph 4 — Water Allocation (water_allocation.png)
   - Daily water balance distribution: turbine release, spill, storage change, evaporation.

Author: Antigravity Research Pipeline
Date  : October 2026
"""

import os
import sys
import numpy as np
import pandas as pd
import matplotlib
# Default to robust non-interactive backend unless interactive display is explicitly requested
if not os.environ.get("MPLBACKEND"):
    matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

SECONDS_PER_DAY = 86400.0

# Scientific publication styling
PLOT_STYLE = {
    "font.family": "sans-serif",
    "font.size": 10,
    "axes.titlesize": 12,
    "axes.titleweight": "bold",
    "axes.labelsize": 10,
    "axes.labelweight": "semibold",
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.fontsize": 9,
    "figure.titlesize": 13,
    "figure.titleweight": "bold",
    "figure.autolayout": True,
    "lines.linewidth": 1.5,
    "grid.alpha": 0.35,
    "grid.linestyle": "--"
}


def setup_date_axis(ax, dates):
    """Format x-axis cleanly based on the time horizon length."""
    n_days = len(dates)
    if n_days <= 21:
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=1 if n_days <= 10 else 2))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    elif n_days <= 90:
        ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=0))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    elif n_days <= 400:
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    else:
        ax.xaxis.set_major_locator(mdates.YearLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha="right")


def plot_generation_comparison(df_res, output_path, is_forecast=False, show_plot=False):
    """
    Graph 1 — Optimized Electricity Generation.
    Plots daily physical generation, linear model generation, and 1,680 MWh/day limit.
    """
    plt.rcParams.update(PLOT_STYLE)
    fig, ax = plt.subplots(figsize=(11, 5.5))

    dates = pd.to_datetime(df_res["date"])
    e_phys = df_res["generation_mwh"]
    has_lp = "linear_generation_mwh" in df_res.columns
    e_lp = df_res["linear_generation_mwh"] if has_lp else None

    # Line plot with markers
    ax.plot(dates, e_phys, color="#ff7f0e", marker="o", markersize=4, linewidth=1.8,
            label="Optimized Physical Generation ($E_{phys}$, Wire-to-Water)")
    ax.fill_between(dates, 0, e_phys, color="#ff7f0e", alpha=0.18)

    if has_lp:
        ax.plot(dates, e_lp, color="#1f77b4", linestyle="--", marker="s", markersize=3.5,
                linewidth=1.4, alpha=0.9, label=r"Linear Model Estimate ($E_{LP} = k_e \cdot V_{turb}$)")

    # Reference limits
    ax.axhline(1680.0, color="#d62728", linestyle="-.", linewidth=1.5,
               label=r"Station Continuous Limit (70 MW $\times$ 24 h = 1,680 MWh/day)")

    # Unit capacity limit if single-unit outage occurred
    if "operating_units" in df_res.columns and (df_res["operating_units"] == 1).any():
        ax.axhline(840.0, color="#bcbd22", linestyle=":", linewidth=1.3,
                   label=r"Single-Unit Capacity Ceiling (35 MW $\times$ 24 h = 840 MWh/day)")

    tag = " [Synthetic ECMWF-Guided Forecast]" if is_forecast else " [Synthetic Simulation]"
    start_str = df_res["date"].iloc[0]
    end_str = df_res["date"].iloc[-1]
    tot_gwh = e_phys.sum() / 1000.0

    ax.set_title(f"Kukule Ganga Power Station — Optimized Daily Electricity Generation{tag}\n"
                 f"Period: {start_str} to {end_str} ({len(df_res)} days) | Total Generation: {tot_gwh:.3f} GWh")
    ax.set_xlabel("Date")
    ax.set_ylabel("Daily Electricity Generation (MWh/day)")
    ax.set_ylim(0, max(1850.0, e_phys.max() * 1.15 if len(e_phys) > 0 else 1850.0))
    ax.grid(True)
    ax.legend(loc="upper right", framealpha=0.9)
    setup_date_axis(ax, dates)

    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    if show_plot:
        try:
            plt.show()
        except Exception:
            pass
    plt.close(fig)
    return os.path.abspath(output_path)


def plot_reservoir_storage(df_res, output_path, s_max_mcm=1.67, is_forecast=False, show_plot=False):
    """
    Graph 2 — Reservoir Storage.
    Plots daily end-of-day active storage (MCM) with minimum (0.0) and maximum (1.67 MCM) limits.
    """
    plt.rcParams.update(PLOT_STYLE)
    fig, ax = plt.subplots(figsize=(11, 5.5))

    dates = pd.to_datetime(df_res["date"])
    s_end_mcm = df_res["end_storage_m3"] / 1e6
    s_begin_mcm = df_res["beginning_storage_m3"] / 1e6

    # Plot End-of-Day Storage trajectory
    ax.plot(dates, s_end_mcm, color="#1f77b4", marker="o", markersize=4.5, linewidth=2.0,
            label="Optimized End-of-Day Active Storage ($S_t$)")
    ax.fill_between(dates, 0, s_end_mcm, color="#1f77b4", alpha=0.15)

    # Plot beginning storage as step points
    ax.step(dates, s_begin_mcm, where="pre", color="#aec7e8", linestyle=":", linewidth=1.2,
            label="Beginning-of-Day Active Storage ($S_{t-1}$)")

    # Bounds
    ax.axhline(s_max_mcm, color="#d62728", linestyle="--", linewidth=1.5,
               label=f"Full Supply Level (FSL: 206.00 MASL | $S_{{max}} = {s_max_mcm:.2f}$ MCM)")
    ax.axhline(0.0, color="#8c564b", linestyle="-.", linewidth=1.3,
               label="Minimum Operating Level (MOL: 204.25 MASL | $S_{{min}} = 0.00$ MCM)")

    tag = " [Synthetic ECMWF-Guided Forecast]" if is_forecast else " [Synthetic Simulation]"
    start_str = df_res["date"].iloc[0]
    end_str = df_res["date"].iloc[-1]

    ax.set_title(f"Kukule Ganga Regulating Pond — Active Storage Trajectory{tag}\n"
                 f"Period: {start_str} to {end_str} ({len(df_res)} days) | Usable Pondage Range: [0.0, {s_max_mcm:.2f}] MCM")
    ax.set_xlabel("Date")
    ax.set_ylabel("Active Storage Volume (Million m³ / MCM)")
    ax.set_ylim(-0.08, s_max_mcm * 1.18)
    ax.grid(True)
    ax.legend(loc="upper right", framealpha=0.9)
    setup_date_axis(ax, dates)

    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    if show_plot:
        try:
            plt.show()
        except Exception:
            pass
    plt.close(fig)
    return os.path.abspath(output_path)


def plot_inflow_release_spill(df_res, output_path, q_station_rated=47.5, is_forecast=False, show_plot=False):
    """
    Graph 3 — Inflow, Turbine Release and Spill.
    Plots forecast inflow, turbine discharge, and spill in m³/s on consistent units.
    """
    plt.rcParams.update(PLOT_STYLE)
    fig, ax = plt.subplots(figsize=(11, 5.5))

    dates = pd.to_datetime(df_res["date"])

    # Convert all volumes to daily average flow rates [m³/s]
    q_in = df_res["inflow_volume_m3"] / SECONDS_PER_DAY
    q_turb = df_res["turbine_release_m3"] / SECONDS_PER_DAY
    q_spill = df_res["spill_volume_m3"] / SECONDS_PER_DAY

    # Plot flow rate series
    ax.plot(dates, q_in, color="#2ca02c", marker="^", markersize=4.5, linewidth=1.8,
            label="Inflow Rate ($Q_{in}$, Catchment Runoff Forecast)")
    ax.plot(dates, q_turb, color="#1f77b4", marker="s", markersize=4, linewidth=1.8,
            label="Optimized Turbine Discharge ($Q_{turb}$, Through Powerhouse)")
    ax.plot(dates, q_spill, color="#9467bd", marker="v", markersize=4, linewidth=1.6, linestyle="--",
            label="Spillway Overflow Rate ($Q_{spill}$, Over Regulator Weir)")

    # Station rated hydraulic capacity limit
    ax.axhline(q_station_rated, color="#d62728", linestyle=":", linewidth=1.5,
               label=f"Station Rated Discharge Limit ($Q_{{rated}} = {q_station_rated:.1f}$ m³/s)")

    tag = " [Synthetic ECMWF-Guided Forecast]" if is_forecast else " [Synthetic Simulation]"
    start_str = df_res["date"].iloc[0]
    end_str = df_res["date"].iloc[-1]

    ax.set_title(f"Kukule Ganga Hydropower Flow Dispatches — Inflow, Generation & Spill{tag}\n"
                 f"Period: {start_str} to {end_str} ({len(df_res)} days) | Consistent Flow Rate Units (m³/s)")
    ax.set_xlabel("Date")
    ax.set_ylabel("Daily Average Flow Rate (m³/s)")
    max_flow = max(q_in.max(), q_turb.max(), q_spill.max(), q_station_rated)
    ax.set_ylim(0, max_flow * 1.15)
    ax.grid(True)
    ax.legend(loc="upper right", framealpha=0.9)
    setup_date_axis(ax, dates)

    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    if show_plot:
        try:
            plt.show()
        except Exception:
            pass
    plt.close(fig)
    return os.path.abspath(output_path)


def plot_water_allocation(df_res, output_path, is_forecast=False, show_plot=False):
    """
    Graph 4 — Daily Water Allocation & Physical Mass Balance Distribution.
    Presents a mathematically exact water balance allocation:
      V_in = V_turb + V_spill + Delta_S + V_loss
    Using a multi-bar component chart comparing outflow & storage change against inflow.
    """
    plt.rcParams.update(PLOT_STYLE)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7.5), sharex=True, gridspec_kw={"height_ratios": [2.2, 1.2]})

    dates = pd.to_datetime(df_res["date"])
    n_days = len(df_res)
    x = np.arange(n_days)

    # Convert all components to Million Cubic Meters (MCM/day)
    v_in = df_res["inflow_volume_m3"].values / 1e6
    v_turb = df_res["turbine_release_m3"].values / 1e6
    v_spill = df_res["spill_volume_m3"].values / 1e6
    s_end = df_res["end_storage_m3"].values / 1e6
    s_begin = df_res["beginning_storage_m3"].values / 1e6
    delta_s = s_end - s_begin
    v_evap = np.full(n_days, 1440.0 / 1e6)  # 0.00144 MCM/day

    # Panel 1: Primary Outflow & Total Inflow Comparison
    width = 0.38
    rects1 = ax1.bar(x - width/2, v_in, width, label="Inflow Volume ($V_{in}$)", color="#2ca02c", alpha=0.85, edgecolor="black", linewidth=0.5)
    
    # Stack turbine release + spillway discharge on the right bar
    rects2 = ax1.bar(x + width/2, v_turb, width, label="Turbine Release ($V_{turb}$)", color="#1f77b4", alpha=0.9, edgecolor="black", linewidth=0.5)
    rects3 = ax1.bar(x + width/2, v_spill, width, bottom=v_turb, label="Spill Overflow ($V_{spill}$)", color="#9467bd", alpha=0.8, edgecolor="black", linewidth=0.5)

    ax1.set_ylabel("Water Volume (Million m³ / MCM)")
    ax1.grid(True)
    ax1.legend(loc="upper right", framealpha=0.9)
    tag = " [Synthetic ECMWF-Guided Forecast]" if is_forecast else " [Synthetic Simulation]"
    start_str = df_res["date"].iloc[0]
    end_str = df_res["date"].iloc[-1]
    ax1.set_title(f"Kukule Ganga Daily Water Balance Allocation{tag}\n"
                  f"Inflow vs Turbined and Spilled Volumes ({start_str} to {end_str})")

    # Panel 2: Net Storage Change and Evaporation Loss
    pos_ds = np.maximum(0.0, delta_s)
    neg_ds = np.minimum(0.0, delta_s)

    ax2.bar(x, pos_ds, 0.45, label=r"Reservoir Filling (+$\Delta S$)", color="#17becf", alpha=0.85, edgecolor="black", linewidth=0.5)
    ax2.bar(x, neg_ds, 0.45, label=r"Reservoir Drawdown ($-\Delta S$)", color="#d62728", alpha=0.85, edgecolor="black", linewidth=0.5)
    ax2.axhline(0.0, color="black", linewidth=0.8)

    ax2.set_ylabel(r"$\Delta S$ (MCM/day)")
    ax2.set_xlabel("Date")
    ax2.grid(True)
    ax2.legend(loc="upper right", framealpha=0.9)

    # Format ticks
    ax2.set_xticks(x)
    if n_days <= 16:
        labels = [d.strftime("%b %d") for d in dates]
        ax2.set_xticklabels(labels, rotation=35, ha="right")
    else:
        step = max(1, n_days // 12)
        tick_indices = list(range(0, n_days, step))
        if (n_days - 1) not in tick_indices:
            tick_indices.append(n_days - 1)
        ax2.set_xticks(tick_indices)
        ax2.set_xticklabels([dates.iloc[i].strftime("%b %d") for i in tick_indices], rotation=35, ha="right")

    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    if show_plot:
        try:
            plt.show()
        except Exception:
            pass
    plt.close(fig)
    return os.path.abspath(output_path)


def generate_all_future_lp_plots(df_res, output_dir, is_forecast=False, show_plots=False):
    """
    Generate and save all 4 required visualization plots into output_dir.

    Returns:
    --------
    dict with absolute file paths to all 4 generated PNG figures.
    """
    os.makedirs(output_dir, exist_ok=True)

    path_gen = os.path.join(output_dir, "generation_comparison.png")
    path_storage = os.path.join(output_dir, "reservoir_storage.png")
    path_flows = os.path.join(output_dir, "inflow_release_spill.png")
    path_alloc = os.path.join(output_dir, "water_allocation.png")

    abs_gen = plot_generation_comparison(df_res, path_gen, is_forecast=is_forecast, show_plot=show_plots)
    abs_storage = plot_reservoir_storage(df_res, path_storage, s_max_mcm=1.67, is_forecast=is_forecast, show_plot=show_plots)
    abs_flows = plot_inflow_release_spill(df_res, path_flows, q_station_rated=47.5, is_forecast=is_forecast, show_plot=show_plots)
    abs_alloc = plot_water_allocation(df_res, path_alloc, is_forecast=is_forecast, show_plot=show_plots)

    return {
        "generation_graph": abs_gen,
        "storage_graph": abs_storage,
        "flow_graph": abs_flows,
        "allocation_graph": abs_alloc
    }
