"""
McKinsey-style report charts for the EurekAlert press-release impact analysis.

Builds the chart types from code/analysis.ipynb (Impact of press release section)
with a shared visual theme and saves PNG files to an output directory.

Usage:
    python code/07_create_graphs.py
    python code/07_create_graphs.py --output-dir ../reports/figures/mckinsey
    python code/07_create_graphs.py --sample-size 500000
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.figure import Figure

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from utils.impact_analysis import (  # noqa: E402
    DEFAULT_ALTMET_CSV,
    DEFAULT_DUCKDB,
    DEFAULT_SOURCE_NOTE,
    METRIC_LABELS,
    METRICS,
    REQUIRED_PIPELINE_OBJECTS,
    assert_pipeline_objects,
    attach_cited_by_count,
    compute_group_stats,
    fit_coefficient_forest,
    load_paper_df,
    short_entity_name,
)

DEFAULT_OUTPUT_DIR = SCRIPT_DIR.parent / "reports" / "figures"

# Re-export for callers that imported these from this module.
__all__ = [
    "DEFAULT_ALTMET_CSV",
    "DEFAULT_DUCKDB",
    "DEFAULT_OUTPUT_DIR",
    "DEFAULT_SOURCE_NOTE",
    "METRIC_LABELS",
    "METRICS",
    "McKinseyStyle",
    "REQUIRED_PIPELINE_OBJECTS",
    "STYLE",
    "assert_pipeline_objects",
    "attach_cited_by_count",
    "compute_group_stats",
    "fit_coefficient_forest",
    "generate_all_graphs",
    "load_paper_df",
    "short_entity_name",
]


@dataclass(frozen=True)
class McKinseyStyle:
    """Shared visual theme for report-ready charts."""

    with_pr_color: str = "#051C2C"
    without_pr_color: str = "#B8C4CE"
    accent_color: str = "#051C2C"
    grid_color: str = "#E3E3E3"
    text_color: str = "#051C2C"
    muted_text: str = "#757575"
    source_text: str = DEFAULT_SOURCE_NOTE
    font_family: str = "Calibri"
    title_size: int = 17
    label_size: int = 10
    tick_size: int = 9
    source_size: int = 8
    bar_width: float = 0.36
    dpi: int = 300

    @property
    def group_colors(self) -> list[str]:
        return [self.with_pr_color, self.without_pr_color]

    def apply(self) -> None:
        plt.rcParams.update(
            {
                "font.family": self.font_family,
                "font.sans-serif": ["Calibri", "Arial", "Segoe UI", "DejaVu Sans"],
                "font.size": self.label_size,
                "axes.titlesize": self.title_size,
                "axes.titlecolor": self.accent_color,
                "axes.labelsize": self.label_size,
                "xtick.labelsize": self.tick_size,
                "ytick.labelsize": self.tick_size,
                "xtick.color": self.text_color,
                "ytick.color": self.text_color,
                "axes.titleweight": "bold",
                "axes.edgecolor": self.grid_color,
                "axes.labelcolor": self.text_color,
                "text.color": self.text_color,
                "figure.facecolor": "white",
                "axes.facecolor": "white",
                "savefig.facecolor": "white",
                "savefig.bbox": "tight",
            }
        )

    def style_axes(self, ax: Axes, *, y_grid: bool = True) -> None:
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color(self.grid_color)
        ax.spines["bottom"].set_color(self.grid_color)
        if y_grid:
            ax.yaxis.grid(True, linestyle="-", color=self.grid_color, alpha=0.7, linewidth=0.8)
            ax.set_axisbelow(True)

    def add_source_note(self, fig: Figure, note: str | None = None) -> None:
        fig.text(
            0.01,
            0.01,
            note or self.source_text,
            ha="left",
            va="bottom",
            fontsize=self.source_size,
            color=self.muted_text,
        )


STYLE = McKinseyStyle()


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug or "chart"


def save_figure(fig: Figure, output_dir: Path, filename: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename
    fig.savefig(path, dpi=STYLE.dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def grouped_bar_with_error(
    ax: Axes,
    categories: list[str],
    series: list[tuple[str, list[float], list[float]]],
    *,
    style: McKinseyStyle = STYLE,
    ylabel: str = "Mean per Paper",
    title: str | None = None,
    subtitle: str | None = None,
    rotate_x: int = 45,
    label_values: bool = False,
) -> None:
    """Draw grouped bars with standard-error whiskers."""
    x = np.arange(len(categories))
    bar_width = style.bar_width

    for i, (label, means, errs) in enumerate(series):
        ax.bar(
            x + i * bar_width,
            means,
            yerr=errs,
            width=bar_width,
            label=label,
            color=style.group_colors[i % len(style.group_colors)],
            edgecolor="none",
            linewidth=0,
            alpha=1.0,
            capsize=4,
            error_kw={"elinewidth": 1.0, "ecolor": style.muted_text},
        )
        if label_values:
            ymax = max((m + (e or 0)) for m, e in zip(means, errs) if pd.notna(m))
            offset = 0.02 * ymax if ymax else 0.1
            for j, (mean, err) in enumerate(zip(means, errs)):
                if pd.isna(mean):
                    continue
                ax.text(
                    x[j] + i * bar_width,
                    mean + (err or 0) + offset,
                    f"{mean:.2f}",
                    ha="center",
                    va="bottom",
                    fontsize=style.tick_size,
                    fontweight="bold",
                )

    ax.set_xticks(x + bar_width / 2)
    ax.set_xticklabels(categories, rotation=rotate_x, ha="right")
    ax.set_ylabel(ylabel)
    ax.set_ylim(bottom=0)
    style.style_axes(ax)

    if title:
        full_title = title if not subtitle else f"{title}\n{subtitle}"
        ax.set_title(full_title, fontsize=style.title_size, fontweight="bold", loc="left")
    ax.legend(frameon=False, fontsize=style.label_size)


def plot_impact_overview(
    paper_df: pd.DataFrame,
    output_dir: Path,
    *,
    style: McKinseyStyle = STYLE,
) -> Path:
    """Grouped bar chart: mean metric values for With PR vs Without PR."""
    means: list[list[float]] = []
    errs: list[list[float]] = []
    for has_pr in (True, False):
        group = paper_df[paper_df["has_pr"] == has_pr]
        means.append([group[m].mean() for m in METRICS])
        errs.append([group[m].sem() for m in METRICS])

    fig, ax = plt.subplots(figsize=(12, 5.5))
    grouped_bar_with_error(
        ax,
        METRIC_LABELS,
        [
            ("With PR", means[0], errs[0]),
            ("Without PR", means[1], errs[1]),
        ],
        style=style,
        ylabel="Mean Value per Paper",
        title="Impact of press release",
        label_values=True,
    )
    style.add_source_note(fig)
    fig.subplots_adjust(bottom=0.22)
    return save_figure(fig, output_dir, "01_impact_overview.png")


def plot_metrics_by_entity(
    paper_df: pd.DataFrame,
    output_dir: Path,
    *,
    category: str,
    style: McKinseyStyle = STYLE,
) -> list[Path]:
    """One chart per metric, grouped by institution or journal."""
    entity_df = paper_df[paper_df["category"] == category].copy()
    entity_label = "Institution" if category == "institution" else "Journal"
    prefix = "02_institution" if category == "institution" else "03_journal"
    saved: list[Path] = []

    for metric, metric_label in zip(METRICS, METRIC_LABELS):
        names, m_pr, e_pr, m_no, e_no, _, _ = compute_group_stats(
            entity_df, "entity_name", metric
        )
        fig, ax = plt.subplots(figsize=(14, 5.5))
        grouped_bar_with_error(
            ax,
            names,
            [
                ("With PR", m_pr, e_pr),
                ("Without PR", m_no, e_no),
            ],
            style=style,
            title=f"{metric_label} by {entity_label}",
            subtitle="(sorted by paper count, most on left)",
        )
        style.add_source_note(fig)
        fig.subplots_adjust(bottom=0.28)
        filename = f"{prefix}_{slugify(metric_label)}.png"
        saved.append(save_figure(fig, output_dir, filename))

    return saved


def plot_distribution_comparison(
    paper_df: pd.DataFrame,
    output_dir: Path,
    *,
    column: str,
    xlabel: str,
    title: str,
    filename: str,
    percentile_cap: float = 99.9,
    bins: int = 50,
    style: McKinseyStyle = STYLE,
) -> Path:
    """Overlapping histogram-style bar chart (% of group) for With vs Without PR."""
    with_pr = paper_df.loc[paper_df["has_pr"], column]
    without_pr = paper_df.loc[~paper_df["has_pr"], column]
    xmax = np.percentile(paper_df[column], percentile_cap)

    counts_with, bin_edges = np.histogram(with_pr[with_pr < xmax], bins=bins)
    counts_without, _ = np.histogram(without_pr[without_pr < xmax], bins=bin_edges)

    pct_with = counts_with / counts_with.sum() * 100 if counts_with.sum() else counts_with
    pct_without = (
        counts_without / counts_without.sum() * 100 if counts_without.sum() else counts_without
    )
    width = np.diff(bin_edges)

    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.bar(
        bin_edges[:-1],
        pct_with,
        width=width,
        color=style.with_pr_color,
        alpha=0.85,
        align="edge",
        edgecolor="black",
        linewidth=0.4,
        label="With PR",
    )
    ax.bar(
        bin_edges[:-1],
        pct_without,
        width=width,
        color=style.without_pr_color,
        alpha=0.85,
        align="edge",
        edgecolor="black",
        linewidth=0.4,
        label="Without PR",
    )
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Percentage of Papers (%)")
    ax.set_title(title, loc="left", fontsize=style.title_size, fontweight="bold")
    style.style_axes(ax)
    ax.legend(frameon=False)
    style.add_source_note(fig)
    return save_figure(fig, output_dir, filename)


def plot_coefficient_forest(
    paper_df: pd.DataFrame,
    output_dir: Path,
    *,
    style: McKinseyStyle = STYLE,
) -> Path | None:
    """OLS coefficient chart with 95% CI (requires pyfixest)."""
    try:
        coef_df = fit_coefficient_forest(paper_df)
    except ImportError:
        print("Skipping coefficient plot: pyfixest is not installed.")
        return None

    x = np.arange(len(coef_df))
    yerr = np.array(
        [coef_df["coef"] - coef_df["ci_lo"], coef_df["ci_hi"] - coef_df["coef"]]
    )

    fig, ax = plt.subplots(figsize=(9, 6))
    ax.bar(
        x,
        coef_df["coef"],
        yerr=yerr,
        width=0.5,
        color=style.with_pr_color,
        edgecolor="black",
        linewidth=0.6,
        alpha=0.9,
        capsize=5,
        error_kw={"elinewidth": 1.0, "ecolor": "black"},
    )
    ymax = coef_df["ci_hi"].max()
    offset = 0.02 * abs(ymax) if ymax else 0.1
    for i, row in coef_df.iterrows():
        ax.text(
            i,
            row["ci_hi"] + offset,
            f"{row['coef']:.2f}",
            va="bottom",
            ha="center",
            fontsize=style.tick_size,
            fontweight="bold",
        )

    ax.set_xticks(x)
    ax.set_xticklabels(coef_df["metric"], rotation=45, ha="right")
    ax.axhline(0, color=style.muted_text, linewidth=1, linestyle="--")
    ax.set_ylabel("OLS Coefficient for has_pr  (with entity FE)")
    ax.set_xlabel("Altmetric Metric")
    ax.set_title(
        "Effect of Press Release on Altmetric Metrics\n"
        "(OLS, Fixed effects by entity)",
        loc="left",
        fontsize=style.title_size,
        fontweight="bold",
    )
    style.style_axes(ax)
    style.add_source_note(fig, "Source: OpenAlex, Altmetric, press release data. Bars: 95% CI.")
    fig.subplots_adjust(bottom=0.22)
    return save_figure(fig, output_dir, "04_coefficient_forest.png")


def generate_all_graphs(
    paper_df: pd.DataFrame,
    output_dir: Path,
    *,
    style: McKinseyStyle = STYLE,
    include_coefficient_plot: bool = True,
) -> list[Path]:
    """Generate the full set of McKinsey-style charts and return saved paths."""
    style.apply()
    saved: list[Path] = []

    print(f"Saving charts to {output_dir.resolve()}")
    saved.append(plot_impact_overview(paper_df, output_dir, style=style))
    saved.extend(plot_metrics_by_entity(paper_df, output_dir, category="institution", style=style))
    saved.extend(plot_metrics_by_entity(paper_df, output_dir, category="journal", style=style))
    saved.append(
        plot_distribution_comparison(
            paper_df,
            output_dir,
            column="attention_score",
            xlabel="Total Attention Score",
            title="Attention Score Distribution (% of group) With and Without Press Release",
            filename="05_attention_score_distribution.png",
            style=style,
        )
    )
    saved.append(
        plot_distribution_comparison(
            paper_df,
            output_dir,
            column="total_mentions",
            xlabel="Total Altmetric Mentions",
            title="Total Mentions Distribution (% of group) With and Without Press Release",
            filename="06_total_mentions_distribution.png",
            style=style,
        )
    )

    if include_coefficient_plot:
        coef_path = plot_coefficient_forest(paper_df, output_dir, style=style)
        if coef_path is not None:
            saved.append(coef_path)

    print(f"Saved {len(saved)} chart(s).")
    return saved


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create McKinsey-style report charts for press-release impact analysis."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory for saved PNG files (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--duckdb",
        type=Path,
        default=DEFAULT_DUCKDB,
        help="Path to eurekalert.duckdb",
    )
    parser.add_argument(
        "--altmet-csv",
        type=Path,
        default=DEFAULT_ALTMET_CSV,
        help="Path to Altmetric deliverable CSV",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=0,
        help="Max rows per has_pr group (use 0 for no sampling)",
    )
    parser.add_argument(
        "--no-coefficient-plot",
        action="store_true",
        help="Skip the OLS coefficient forest plot",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    sample_size = None if args.sample_size == 0 else args.sample_size

    print("Loading analysis data …")
    paper_df = load_paper_df(
        duckdb_path=args.duckdb,
        altmet_csv=args.altmet_csv,
        sample_size=sample_size,
    )
    print(f"Loaded {len(paper_df):,} papers ({paper_df['has_pr'].sum():,} with PR).")

    generate_all_graphs(
        paper_df,
        args.output_dir,
        include_coefficient_plot=not args.no_coefficient_plot,
    )


if __name__ == "__main__":
    main()
