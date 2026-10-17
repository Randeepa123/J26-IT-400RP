"""
plot_lp_evaluation.py
=====================
Publication-Grade Visualizations for Kukule Ganga LP Optimizer Evaluation
Component: Component 3 - Hydropower Generation & Reservoir Release Optimization Subsystem

Generates:
1. lp_vs_reference_comparison.png: 4-panel comparison of storage, turbine release, generation, and spill
2. lp_chronological_splits.png: Training (Dev) vs Held-Out Test generation & storage trajectories
3. lp_linear_approximation_gap.png: Detailed analysis of linear power approximation vs physical non-linear power

Author: Antigravity Research Pipeline
Date  : October 2026
"""

import os
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# Visual Aesthetics
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.size": 10,
    "axes.titlesize": 12,
    "axes.titleweight": "bold",
    "axes.labelsize": 10,
    "axes.labelweight": "semibold",
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.fontsize": 9,
    "figure.titlesize": 14,
    "figure.titleweight": "bold",
    "figure.autolayout": True,
    "lines.linewidth": 1.2,
    "grid.alpha": 0.4,
    "grid.linestyle": "--"
})

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LP_RESULTS_PATH = os.path.join(SCRIPT_DIR, "lp_results.csv")
REF_RESULTS_PATH = os.path.join(SCRIPT_DIR, "reference_results_full.csv")


def plot_comparison_4panel(df_lp, df_ref, output_path):
    """Plot 4-panel time series comparing LP Optimizer vs Heuristic Reference Policy."""
    dates = pd.to_datetime(df_lp["date"])

    fig, axes = plt.subplots(4, 1, figsize=(15, 12), sharex=True)

    # 1. Active Storage Trajectory
    ax1 = axes[0]
    ax1.plot(dates, df_ref["end_storage_m3"] / 1e6, label="Reference Rule-Curve Policy", color="#7f7f7f", linestyle="--", alpha=0.85)
    ax1.plot(dates, df_lp["end_storage_m3"] / 1e6, label="Genuine LP Optimizer (HiGHS)", color="#1f77b4", linewidth=1.4)
    ax1.axhline(1.67, color="#d62728", linestyle=":", linewidth=1.5, label="Full Supply Level (S_max = 1.67 MCM)")
    ax1.axhline(0.0, color="#8c564b", linestyle=":", linewidth=1.2, label="Minimum Operating Level (S_min = 0.0 MCM)")
    ax1.set_ylabel("Storage (MCM)")
    ax1.set_title("A. Reservoir Active Storage Trajectory & Head Preservation")
    ax1.legend(loc="upper right", framealpha=0.9)
    ax1.grid(True)
    ax1.set_ylim(-0.05, 1.85)

    # 2. Turbine Release Volume
    ax2 = axes[1]
    ax2.plot(dates, df_ref["turbine_release_m3"] / 1e6, label="Reference Turbine Release", color="#aec7e8", alpha=0.7)
    ax2.plot(dates, df_lp["turbine_release_m3"] / 1e6, label="LP Optimal Turbine Release", color="#2ca02c", linewidth=1.1)
    ax2.axhline(4.104, color="#e377c2", linestyle=":", label="Hydraulic Rated Ceiling (47.5 m³/s = 4.104 MCM/day)")
    ax2.axhline(3.935, color="#17becf", linestyle="--", label="70 MW Continuous Electrical Cap (3.935 MCM/day)")
    ax2.set_ylabel("Turbine Release (MCM/day)")
    ax2.set_title("B. Daily Turbine Volumetric Release & Capacity Bounds")
    ax2.legend(loc="upper right", framealpha=0.9)
    ax2.grid(True)
    ax2.set_ylim(0.0, 4.5)

    # 3. Daily Electricity Generation
    ax3 = axes[2]
    ax3.plot(dates, df_ref["generation_mwh"], label="Reference Generation (E_phys)", color="#ffbb78", alpha=0.8)
    ax3.plot(dates, df_lp["generation_mwh"], label="LP Optimal Generation (E_phys)", color="#ff7f0e", linewidth=1.2)
    ax3.axhline(1680.0, color="#d62728", linestyle="--", label="Continuous 70 MW Ceiling (1,680.0 MWh/day)")
    ax3.axhline(840.0, color="#bcbd22", linestyle=":", label="Single-Unit Outage Ceiling (840.0 MWh/day)")
    ax3.set_ylabel("Generation (MWh/day)")
    ax3.set_title("C. Daily Hydropower Generation (Physical Wire-to-Water Evaluated)")
    ax3.legend(loc="upper right", framealpha=0.9)
    ax3.grid(True)
    ax3.set_ylim(0.0, 1850.0)

    # 4. Spillway Overflow
    ax4 = axes[3]
    ax4.plot(dates, df_ref["spill_volume_m3"] / 1e6, label="Reference Spill Overflow", color="#c7c7c7", linestyle="--", alpha=0.8)
    ax4.plot(dates, df_lp["spill_volume_m3"] / 1e6, label="LP Spillway Overflow", color="#9467bd", linewidth=1.1)
    ax4.set_ylabel("Spill Volume (MCM/day)")
    ax4.set_title("D. Weir Spillway Overflow During Monsoon Floods")
    ax4.legend(loc="upper right", framealpha=0.9)
    ax4.grid(True)

    # Format x-axis dates
    ax4.xaxis.set_major_locator(mdates.YearLocator())
    ax4.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax4.xaxis.set_minor_locator(mdates.MonthLocator(interval=3))
    ax4.set_xlabel("Date (Chronological Horizon)")

    fig.suptitle("Kukule Ganga Hydropower Station: LP Optimizer vs Heuristic Reference Policy (5-Year Horizon)", y=0.995)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()
    print(f"[Plotting] Saved: {output_path}")


def plot_chronological_splits(df_dev_lp, df_test_lp, df_dev_ref, df_test_ref, output_path):
    """Plot cumulative generation and energy metrics across Dev and Held-Out Test splits."""
    fig, axes = plt.subplots(1, 2, figsize=(15, 6))

    # Left: Dev Split Cumulative Energy
    ax1 = axes[0]
    dev_dates = pd.to_datetime(df_dev_lp["date"])
    cum_lp_dev = df_dev_lp["generation_mwh"].cumsum() / 1000.0
    cum_ref_dev = df_dev_ref["generation_mwh"].cumsum() / 1000.0
    ax1.plot(dev_dates, cum_lp_dev, label=f"LP Optimizer ({cum_lp_dev.iloc[-1]:.1f} GWh)", color="#1f77b4", linewidth=1.6)
    ax1.plot(dev_dates, cum_ref_dev, label=f"Reference Policy ({cum_ref_dev.iloc[-1]:.1f} GWh)", color="#ff7f0e", linestyle="--", linewidth=1.5)
    ax1.set_ylabel("Cumulative Generation (GWh)")
    ax1.set_title("Development Split (2021-10-19 to 2025-10-18: 1,461 Days)")
    ax1.legend(loc="upper left")
    ax1.grid(True)
    ax1.xaxis.set_major_locator(mdates.YearLocator())
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))

    # Right: Held-Out Test Split Cumulative Energy
    ax2 = axes[1]
    test_dates = pd.to_datetime(df_test_lp["date"])
    cum_lp_test = df_test_lp["generation_mwh"].cumsum() / 1000.0
    cum_ref_test = df_test_ref["generation_mwh"].cumsum() / 1000.0
    ax2.plot(test_dates, cum_lp_test, label=f"LP Optimizer ({cum_lp_test.iloc[-1]:.1f} GWh)", color="#1f77b4", linewidth=1.6)
    ax2.plot(test_dates, cum_ref_test, label=f"Reference Policy ({cum_ref_test.iloc[-1]:.1f} GWh)", color="#ff7f0e", linestyle="--", linewidth=1.5)
    ax2.set_ylabel("Cumulative Generation (GWh)")
    ax2.set_title("Held-Out Evaluation Split (2025-10-19 to 2026-10-18: 365 Days)")
    ax2.legend(loc="upper left")
    ax2.grid(True)
    ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))

    fig.suptitle("Chronological Out-of-Sample Performance Comparison: Cumulative Hydropower Generation", y=1.02)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()
    print(f"[Plotting] Saved: {output_path}")


def plot_linear_approximation_gap(df_lp, output_path):
    """Plot linear power approximation accuracy vs exact physical non-linear power."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))

    # Left: Scatter of LP Linear vs Physical Non-Linear Generation
    ax1 = axes[0]
    ax1.scatter(df_lp["generation_mwh"], df_lp["linear_generation_mwh"], alpha=0.35, color="#1f77b4", s=15, edgecolors="none")
    lims = [0, 1750]
    ax1.plot(lims, lims, color="#d62728", linestyle="--", linewidth=1.5, label="1:1 Exact Parity Line")
    ax1.set_xlim(lims)
    ax1.set_ylim(lims)
    ax1.set_xlabel("Physical Non-Linear Generation (MWh/day)")
    ax1.set_ylabel("Linear LP Modeled Generation (MWh/day)")
    ax1.set_title("A. Linear Model vs Physical Non-Linear Energy Parity")
    ax1.legend(loc="upper left")
    ax1.grid(True)

    # Right: Error Distribution Histogram
    ax2 = axes[1]
    errors = df_lp["linear_approximation_error_mwh"]
    # Only for days with generation > 0
    errors_gen = errors[df_lp["generation_mwh"] > 0]
    ax2.hist(errors_gen, bins=40, color="#2ca02c", edgecolor="black", alpha=0.75, density=True)
    mean_err = errors_gen.mean()
    med_err = errors_gen.median()
    ax2.axvline(mean_err, color="#d62728", linestyle="-", linewidth=1.5, label=f"Mean Error: {mean_err:+.2f} MWh/day")
    ax2.axvline(med_err, color="#9467bd", linestyle="--", linewidth=1.5, label=f"Median Error: {med_err:+.2f} MWh/day")
    ax2.set_xlabel("Linear Approximation Error: E_lp - E_phys (MWh/day)")
    ax2.set_ylabel("Probability Density")
    ax2.set_title("B. Linear Model Approximation Error Distribution")
    ax2.legend(loc="upper right")
    ax2.grid(True)

    fig.suptitle("Quantification of Linear Power Approximation Error (k_e = 4.2694e-4 MWh/m³)", y=1.02)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()
    print(f"[Plotting] Saved: {output_path}")


def main():
    print("[Plotting] Loading results datasets...")
    df_lp = pd.read_csv(LP_RESULTS_PATH)
    df_ref = pd.read_csv(REF_RESULTS_PATH)

    df_dev_lp = pd.read_csv(os.path.join(SCRIPT_DIR, "lp_results_dev.csv"))
    df_test_lp = pd.read_csv(os.path.join(SCRIPT_DIR, "lp_results_test.csv"))
    df_dev_ref = pd.read_csv(os.path.join(SCRIPT_DIR, "reference_results_dev.csv"))
    df_test_ref = pd.read_csv(os.path.join(SCRIPT_DIR, "reference_results_test.csv"))

    out_comp = os.path.join(SCRIPT_DIR, "lp_vs_reference_comparison.png")
    out_splits = os.path.join(SCRIPT_DIR, "lp_chronological_splits.png")
    out_gap = os.path.join(SCRIPT_DIR, "lp_linear_approximation_gap.png")

    plot_comparison_4panel(df_lp, df_ref, out_comp)
    plot_chronological_splits(df_dev_lp, df_test_lp, df_dev_ref, df_test_ref, out_splits)
    plot_linear_approximation_gap(df_lp, out_gap)
    print("[Plotting] All figures generated successfully.")


if __name__ == "__main__":
    main()
