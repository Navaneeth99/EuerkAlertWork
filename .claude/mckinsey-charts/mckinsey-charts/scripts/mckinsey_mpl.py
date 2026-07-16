"""
McKinsey-style matplotlib theme and helper functions.

Usage:
    from mckinsey_mpl import apply_style, PALETTE, takeaway_title, add_source, direct_label_lines, style_bar_labels

    apply_style()
    fig, ax = plt.subplots(figsize=(9, 5.5))
    ...
    takeaway_title(ax, "Revenue grew 24% in Q3, driven by the EMEA launch",
                    subtitle="Quarterly revenue, $M")
    add_source(fig, "Source: Internal sales data, FY24")
    plt.savefig("chart.png", dpi=300, bbox_inches="tight")
"""

import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------
# One strong accent color carries the story; everything else recedes to gray
# or muted navy/blue. Never use more than 2-3 hues in a single chart.

PALETTE = {
    "navy": "#04293A",
    "blue_dark": "#0B5394",
    "blue": "#1E78B4",
    "blue_light": "#7FB2DB",
    "accent": "#E3120B",       # use for the ONE thing you want the eye to land on
    "accent_light": "#F4978E",
    "gray_dark": "#3F3F3F",
    "gray": "#888888",
    "gray_light": "#BFBFBF",
    "gray_bg": "#E8E8E8",
    "positive": "#1E78B4",
    "negative": "#E3120B",
    "bg": "#FFFFFF",
}

# Ordered sequence for multi-series charts: leads with navy/blue, falls back
# to grays so any added series doesn't fight for attention.
SEQUENCE = [
    PALETTE["blue_dark"],
    PALETTE["gray_light"],
    PALETTE["blue_light"],
    PALETTE["gray"],
    PALETTE["navy"],
]

FONT_STACK = ["Arial", "Helvetica", "Liberation Sans", "DejaVu Sans"]


def _first_available_font():
    available = {f.name for f in fm.fontManager.ttflist}
    for name in FONT_STACK:
        if name in available:
            return name
    return "sans-serif"


def apply_style():
    """Apply the McKinsey-style rcParams globally. Call once per script/session."""
    font = _first_available_font()
    plt.rcParams.update({
        "font.family": font,
        "font.size": 11,
        "axes.titlesize": 16,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "axes.titlepad": 28,
        "axes.labelsize": 10,
        "axes.labelcolor": PALETTE["gray_dark"],
        "axes.edgecolor": PALETTE["gray_light"],
        "axes.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.spines.left": False,
        "axes.grid": True,
        "axes.grid.axis": "y",
        "grid.color": PALETTE["gray_bg"],
        "grid.linewidth": 0.8,
        "axes.axisbelow": True,
        "xtick.color": PALETTE["gray_dark"],
        "ytick.color": PALETTE["gray_dark"],
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "ytick.left": False,
        "xtick.bottom": True,
        "xtick.color": PALETTE["gray_light"],
        "figure.facecolor": PALETTE["bg"],
        "axes.facecolor": PALETTE["bg"],
        "savefig.facecolor": PALETTE["bg"],
        "legend.frameon": False,
        "legend.fontsize": 10,
        "text.color": PALETTE["gray_dark"],
    })


def takeaway_title(ax, title, subtitle=None, y_title=1.12, y_subtitle=1.05):
    """
    McKinsey charts are titled with the INSIGHT, not the variable name.
    Bad:  "Revenue by Quarter"
    Good: "Revenue grew 24% in Q3, driven by the EMEA launch"

    title: the insight, bold, left-aligned, above the chart
    subtitle: smaller gray context line (units, scope, time period)
    """
    ax.text(0, y_title, title, transform=ax.transAxes,
            fontsize=15, fontweight="bold", color=PALETTE["navy"],
            ha="left", va="bottom")
    if subtitle:
        ax.text(0, y_subtitle, subtitle, transform=ax.transAxes,
                fontsize=10.5, color=PALETTE["gray"],
                ha="left", va="bottom")


def add_source(fig, text, y=-0.02):
    """Small gray source/footnote line, bottom-left of the figure."""
    fig.text(0.02, y, text, fontsize=8.5, color=PALETTE["gray"], ha="left")


def style_bar_labels(ax, bars, fmt="{:,.0f}", color=None, fontsize=10,
                      inside=False, suffix=""):
    """
    Add direct value labels to bars instead of relying on a y-axis.
    Set inside=True to place labels inside tall bars in white.
    """
    for bar in bars:
        height = bar.get_height() if bar.get_height() != 0 else bar.get_width()
        is_vertical = bar.get_height() != 0
        val = bar.get_height() if is_vertical else bar.get_width()
        label = fmt.format(val) + suffix
        if is_vertical:
            x = bar.get_x() + bar.get_width() / 2
            y = bar.get_height()
            va = "top" if inside else "bottom"
            ty = y - (y * 0.05) if inside else y + (max(abs(y), 1) * 0.02)
            ax.text(x, ty, label, ha="center", va=va,
                    fontsize=fontsize, color=color or PALETTE["gray_dark"],
                    fontweight="medium")
        else:
            y = bar.get_y() + bar.get_height() / 2
            x = bar.get_width()
            ha = "right" if inside else "left"
            tx = x - (x * 0.02) if inside else x + (max(abs(x), 1) * 0.02)
            ax.text(tx, y, label, ha=ha, va="center",
                    fontsize=fontsize, color=color or PALETTE["gray_dark"])


def direct_label_lines(ax, x_end, series, labels, colors=None, fontsize=10.5,
                        offset=0.02):
    """
    Label each line at its right-hand endpoint instead of using a legend.
    series: list of y-values (last value used for placement)
    labels: list of strings, one per series
    """
    colors = colors or SEQUENCE
    for i, (y_vals, label) in enumerate(zip(series, labels)):
        y_end = y_vals[-1] if hasattr(y_vals, "__len__") else y_vals
        ax.annotate(label, xy=(x_end, y_end),
                    xytext=(x_end + offset, y_end),
                    fontsize=fontsize, color=colors[i % len(colors)],
                    fontweight="bold", va="center", ha="left",
                    annotation_clip=False)


def diverging_color(value):
    """Return accent (negative) or blue (positive) — use for single-metric
    bar/waterfall charts where sign carries the story."""
    return PALETTE["negative"] if value < 0 else PALETTE["positive"]
