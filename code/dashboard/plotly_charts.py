"""Interactive Plotly charts matching McKinseyStyle from the report graph pipeline.

Colors and typography align with the restrained report theme:
navy + muted gray-blue, Calibri, light value-axis gridlines, no chart box.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import plotly.graph_objects as go

# Report chart tokens (navy highlight + muted secondary).
WITH_PR_COLOR = "#051C2C"
WITHOUT_PR_COLOR = "#B8C4CE"
ACCENT_COLOR = "#051C2C"
GRID_COLOR = "#E3E3E3"
TEXT_COLOR = "#051C2C"
MUTED_TEXT = "#757575"
SUBTITLE_TEXT = "#4A4A4A"

# Prefer Calibri (report font); fall back across platforms.
FONT_FAMILY = "Calibri, Arial, Segoe UI, Helvetica, sans-serif"
TITLE_SIZE = 17
LABEL_SIZE = 13
TICK_SIZE = 11
SUBTITLE_SIZE = 11
X_TICK_SIZE = 12
LEGEND_SIZE = 12


@dataclass(frozen=True)
class PlotlyMcKinseyStyle:
    with_pr_color: str = WITH_PR_COLOR
    without_pr_color: str = WITHOUT_PR_COLOR
    accent_color: str = ACCENT_COLOR
    grid_color: str = GRID_COLOR
    text_color: str = TEXT_COLOR
    muted_text: str = MUTED_TEXT
    subtitle_text: str = SUBTITLE_TEXT
    font_family: str = FONT_FAMILY
    title_size: int = TITLE_SIZE
    label_size: int = LABEL_SIZE
    tick_size: int = TICK_SIZE
    subtitle_size: int = SUBTITLE_SIZE
    x_tick_size: int = X_TICK_SIZE
    legend_size: int = LEGEND_SIZE

    @property
    def group_colors(self) -> list[str]:
        return [self.with_pr_color, self.without_pr_color]


STYLE = PlotlyMcKinseyStyle()


def _font(size: int, *, color: str | None = None) -> dict:
    return {
        "family": STYLE.font_family,
        "size": size,
        "color": color or STYLE.text_color,
    }


def _y_axis_at_zero(
    *,
    y_min: float,
    y_max: float,
    style: PlotlyMcKinseyStyle = STYLE,
) -> dict:
    """Y-axis: light gridlines only, no box, baseline at y=0 when data allow."""
    pad = max(abs(y_max) * 0.12, 0.05)
    if y_min >= 0:
        y_range = [0, y_max + pad]
    else:
        y_range = [y_min - pad, y_max + pad]

    return dict(
        title=dict(font=_font(style.label_size)),
        tickfont=_font(style.tick_size, color=style.muted_text),
        gridcolor=style.grid_color,
        gridwidth=0.8,
        showgrid=True,
        range=y_range,
        rangemode="tozero" if y_min >= 0 else "normal",
        zeroline=True,
        zerolinecolor=style.muted_text,
        zerolinewidth=1.0,
        showline=False,
        ticks="",
        mirror=False,
        automargin=True,
        fixedrange=False,
    )


def _base_layout(
    *,
    title: str,
    ylabel: str,
    xlabel: str | None = None,
    style: PlotlyMcKinseyStyle = STYLE,
    height: int = 480,
    y_min: float = 0.0,
    y_max: float = 1.0,
) -> dict:
    yaxis = _y_axis_at_zero(y_min=y_min, y_max=y_max, style=style)
    yaxis["title"] = dict(text=ylabel, font=_font(style.label_size))

    # Multi-line titles need extra top space so the legend stays clear of the subtitle.
    has_subtitle = "<br>" in title
    top_margin = 110 if has_subtitle else 70

    return dict(
        template="simple_white",
        font=_font(style.label_size),
        title=dict(
            text=title,
            x=0.0,
            xanchor="left",
            y=0.98,
            yanchor="top",
            pad=dict(t=0, b=8),
            font=_font(style.title_size, color=style.accent_color),
        ),
        yaxis=yaxis,
        xaxis=dict(
            title=dict(
                text=xlabel or "",
                font=_font(style.label_size),
            ),
            tickfont=_font(style.x_tick_size, color=style.muted_text),
            tickangle=-45,
            showgrid=False,
            zeroline=False,
            showline=False,
            ticks="",
            mirror=False,
            automargin=True,
            **({"anchor": "y", "side": "bottom"} if y_min >= 0 else {}),
        ),
        plot_bgcolor="white",
        paper_bgcolor="white",
        # Top-right legend so it never overlaps the left-aligned title/subtitle.
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1.0,
            bgcolor="rgba(0,0,0,0)",
            borderwidth=0,
            font=_font(style.legend_size),
            traceorder="normal",
            itemsizing="constant",
            itemwidth=30,
        ),
        margin=dict(l=70, r=30, t=top_margin, b=110),
        height=height,
        hovermode="closest",
        bargap=0.25,
        bargroupgap=0.05,
    )


def grouped_bar_with_error_plotly(
    categories: list[str],
    series: list[tuple[str, list[float], list[float], list[int] | None]],
    *,
    title: str,
    ylabel: str = "Mean Value per Paper",
    style: PlotlyMcKinseyStyle = STYLE,
    label_values: bool = False,
    height: int | None = None,
) -> go.Figure:
    """Grouped bars with SE error bars — visual twin of the report chart style."""
    fig = go.Figure()
    colors = style.group_colors

    y_tops: list[float] = []
    for i, item in enumerate(series):
        label, means, errs = item[0], item[1], item[2]
        ns = item[3] if len(item) > 3 else None
        color = colors[i % len(colors)]
        customdata = []
        for j, (m, e) in enumerate(zip(means, errs)):
            n_val = ns[j] if ns is not None else None
            customdata.append([e, n_val if n_val is not None else "—"])
            if pd.notna(m):
                y_tops.append(float(m) + (float(e) if pd.notna(e) else 0.0))

        fig.add_trace(
            go.Bar(
                name=label,
                x=categories,
                y=means,
                base=0,
                marker_color=color,
                marker_line_width=0,
                opacity=1.0,
                error_y=dict(
                    type="data",
                    array=errs,
                    visible=True,
                    thickness=1.0,
                    width=4,
                    color=style.muted_text,
                ),
                customdata=customdata,
                hovertemplate=(
                    f"<b>{label}</b><br>"
                    "%{x}<br>"
                    "Mean: %{y:.3f}<br>"
                    "SE: %{customdata[0]:.3f}<br>"
                    "N: %{customdata[1]}<extra></extra>"
                ),
                text=[
                    f"{m:.2f}" if label_values and pd.notna(m) else ""
                    for m in means
                ],
                textposition="outside",
                textfont=_font(style.tick_size),
                cliponaxis=False,
            )
        )

    fig_height = height or max(480, 60 + 28 * len(categories))
    layout_title = title if "<" in title else f"<b>{title}</b>"
    y_max = max(y_tops) if y_tops else 1.0

    layout = _base_layout(
        title=layout_title,
        ylabel=ylabel,
        style=style,
        height=fig_height,
        y_min=0.0,
        y_max=y_max,
    )
    layout["barmode"] = "group"
    # Force colorway so Streamlit/Plotly templates cannot override series colors.
    layout["colorway"] = style.group_colors
    fig.update_layout(**layout)
    for i, color in enumerate(style.group_colors):
        if i < len(fig.data):
            fig.data[i].marker.color = color
            fig.data[i].marker.line.width = 0
    return fig


def forest_plot_plotly(
    coef_df: pd.DataFrame,
    *,
    title: str = (
        "<b>Effect of Press Release on Altmetric Metrics</b><br>"
        f"<span style='font-size:11px;font-weight:normal;color:{SUBTITLE_TEXT}'>"
        "(OLS, Fixed effects by entity)</span>"
    ),
    style: PlotlyMcKinseyStyle = STYLE,
) -> go.Figure:
    """Coefficient chart matching the report fixed-effects forest plot."""
    fig = go.Figure()
    err_plus = (coef_df["ci_hi"] - coef_df["coef"]).tolist()
    err_minus = (coef_df["coef"] - coef_df["ci_lo"]).tolist()
    y_min = float(coef_df["ci_lo"].min())
    y_max = float(coef_df["ci_hi"].max())
    if y_min > 0:
        y_min = 0.0

    fig.add_trace(
        go.Bar(
            x=coef_df["metric"],
            y=coef_df["coef"],
            base=0,
            width=0.5,
            marker_color=style.with_pr_color,
            marker_line_width=0,
            opacity=1.0,
            error_y=dict(
                type="data",
                array=err_plus,
                arrayminus=err_minus,
                visible=True,
                thickness=1.0,
                width=5,
                color=style.muted_text,
            ),
            customdata=coef_df[["ci_lo", "ci_hi", "se"]].to_numpy(),
            hovertemplate=(
                "<b>%{x}</b><br>"
                "Coef: %{y:.3f}<br>"
                "SE: %{customdata[2]:.3f}<br>"
                "95% CI: [%{customdata[0]:.3f}, %{customdata[1]:.3f}]"
                "<extra></extra>"
            ),
            text=[f"{c:.2f}" for c in coef_df["coef"]],
            textposition="outside",
            textfont=_font(style.tick_size),
            cliponaxis=False,
            showlegend=False,
        )
    )

    layout = _base_layout(
        title=title,
        ylabel="OLS Coefficient for has_pr  (with entity FE)",
        xlabel="Altmetric Metric",
        style=style,
        height=520,
        y_min=y_min,
        y_max=y_max,
    )
    fig.update_layout(**layout)
    if y_min < 0:
        fig.add_hline(
            y=0,
            line_dash="dash",
            line_color=style.muted_text,
            line_width=1.0,
        )
    return fig
