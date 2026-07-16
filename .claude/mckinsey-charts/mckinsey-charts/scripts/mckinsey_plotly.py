"""
McKinsey-style Plotly theme and helper functions (for interactive HTML output).

Usage:
    import plotly.graph_objects as go
    from mckinsey_plotly import TEMPLATE, PALETTE, add_takeaway_title, add_source

    fig = go.Figure(...)
    fig.update_layout(template=TEMPLATE)
    add_takeaway_title(fig, "Revenue grew 24% in Q3, driven by the EMEA launch",
                        subtitle="Quarterly revenue, $M")
    add_source(fig, "Source: Internal sales data, FY24")
    fig.write_html("chart.html")
    # or fig.write_image("chart.png", scale=3)  # requires kaleido
"""

import plotly.graph_objects as go
import plotly.io as pio

PALETTE = {
    "navy": "#04293A",
    "blue_dark": "#0B5394",
    "blue": "#1E78B4",
    "blue_light": "#7FB2DB",
    "accent": "#E3120B",
    "accent_light": "#F4978E",
    "gray_dark": "#3F3F3F",
    "gray": "#888888",
    "gray_light": "#BFBFBF",
    "gray_bg": "#E8E8E8",
    "bg": "#FFFFFF",
}

SEQUENCE = [PALETTE["blue_dark"], PALETTE["gray_light"], PALETTE["blue_light"],
            PALETTE["gray"], PALETTE["navy"]]

_layout = go.Layout(
    font=dict(family="Arial, Helvetica, sans-serif", size=12, color=PALETTE["gray_dark"]),
    paper_bgcolor=PALETTE["bg"],
    plot_bgcolor=PALETTE["bg"],
    colorway=SEQUENCE,
    margin=dict(t=110, l=60, r=40, b=70),
    xaxis=dict(showgrid=False, showline=True, linecolor=PALETTE["gray_light"],
               ticks="outside", tickcolor=PALETTE["gray_light"], zeroline=False),
    yaxis=dict(showgrid=True, gridcolor=PALETTE["gray_bg"], showline=False,
               zeroline=False),
    legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0,
                font=dict(size=11)),
    hoverlabel=dict(bgcolor="white", font=dict(family="Arial", size=12)),
)

TEMPLATE = pio.templates["plotly_white"]
TEMPLATE.layout = _layout


def add_takeaway_title(fig, title, subtitle=None):
    """
    Title with the INSIGHT (bold, navy), optional gray subtitle with units/scope.
    """
    full = f"<b style='color:{PALETTE['navy']}'>{title}</b>"
    if subtitle:
        full += f"<br><span style='font-size:13px;color:{PALETTE['gray']}'>{subtitle}</span>"
    fig.update_layout(title=dict(text=full, x=0, xanchor="left", y=0.95,
                                  font=dict(size=18)))


def add_source(fig, text):
    fig.add_annotation(text=text, xref="paper", yref="paper", x=0, y=-0.18,
                        showarrow=False, font=dict(size=10, color=PALETTE["gray"]),
                        align="left")


def diverging_color(value):
    return PALETTE["accent"] if value < 0 else PALETTE["blue"]
