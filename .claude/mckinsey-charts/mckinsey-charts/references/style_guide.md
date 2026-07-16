# McKinsey-Style Chart Design Guide

This is the design reasoning behind the helper scripts. Read this when you need
to make a judgment call the scripts don't automate for you (chart type choice,
what to emphasize, how to phrase a title).

## 1. The title is the insight, not the variable

Every chart should be readable as a single sentence without looking at the
data. The title states the takeaway; the chart proves it.

- Bad: "Revenue by Region, 2023–2024"
- Good: "EMEA overtook North America as the largest region in Q3"

If you can't write an insight-style title, you probably haven't decided what
the chart is for yet — go back to the data and find the one thing that matters.

Subtitle carries the boring-but-necessary context (units, time period, scope)
so the title doesn't have to.

## 2. One accent color, everything else recedes

Pick the ONE series, bar, or data point the story is about and color it with
the accent (`PALETTE["accent"]` or `blue_dark`). Put everything else in gray
or muted blue. This is the single highest-leverage move for making a chart
look "consulting-grade" instead of "default Excel."

Never use a rainbow/qualitative palette (tab10, Set2, etc.) for a chart with
a point of view. Reserve multi-hue palettes only for genuinely neutral
categorical breakdowns where no single category is the story.

## 3. Minimize non-data ink

- No chart border / box around the plot (`axes.spines` top/right/left off).
- Gridlines only on the value axis, very light gray, never both axes.
- No legend when you can direct-label instead (label lines at their
  endpoint, label bars directly with their value).
- Tick marks only where needed; avoid redundant axis titles when the chart
  title already states the units.

## 4. Direct labeling over legends and axes

- Bar charts: put the value directly above/beside the bar, consider removing
  the value-axis labels entirely once bars are labeled.
- Line charts: label each line at its right endpoint with its name and/or
  final value, drop the legend.
- Only fall back to a legend when there are more series than can be cleanly
  end-labeled (~5+).

## 5. Typography

- Sans-serif only (Arial/Helvetica stack).
- Title: bold, 15–18pt, navy, left-aligned, sits above the plot.
- Subtitle: regular, 10–11pt, gray.
- Axis/tick labels: 9–10pt, gray, never bold.
- Data labels: 10pt, medium weight, dark gray or white-on-color if inside a
  filled bar.

## 6. Chart type selection

| If the story is about...                          | Use                                  |
|-----------------------------------------------------|---------------------------------------|
| Ranking categories                                 | Horizontal bar, sorted descending     |
| Change over time (few periods)                     | Column (vertical bar)                 |
| Trend over time (many periods)                     | Line, end-labeled                     |
| Before/after or two-point comparison across groups | Slope chart (two dots + connecting line) |
| Build-up/bridge from start to end value             | Waterfall                             |
| Part-to-whole, ≤4 categories                        | Stacked bar (single bar) or simple pie only if truly ≤3 slices |
| Part-to-whole, >4 categories                        | Horizontal bar (NOT pie/donut)        |
| Correlation between two variables                  | Scatter, with a trend line if relevant |
| Distribution                                        | Histogram or box plot, minimal styling|
| Geographic comparison                               | Choropleth (only if maps add value)   |

Avoid: 3D charts, pie charts with >3 slices, dual y-axes (prefer two small
charts or an indexed single axis), radar/spider charts (hard to read
accurately), excessive use of donut charts.

## 7. Numbers and formatting

- Round aggressively. $24.3482M → "$24.3M" or even "$24M" if precision isn't
  the point.
- Use "M"/"B"/"K" suffixes instead of full numbers with commas where the
  scale is large.
- Percentages: one decimal max, usually zero ("24%" not "24.3%") unless the
  decimal is the story (e.g., interest rates).
- Negative values in red/accent, positive in blue — don't rely on color
  alone, also use position/sign.

## 8. Sourcing and footnotes

Always include a small gray source line bottom-left: `Source: <dataset>,
<date/period>`. If the chart uses an estimate, projection, or excludes
something material, add a one-line note in the same style.

## 9. Layout and sizing

- Default figure size for a single chart in a report: ~9x5.5in (matplotlib)
  at 300 dpi for print-quality PNG, or 1000x600px for plotly/web.
- Leave generous top margin for title+subtitle (the helper functions already
  reserve this).
- For decks: widescreen 13.33x7.5in slide, chart occupies a defined content
  zone with the title living in the slide's own title placeholder if the
  chart is being placed into a PowerPoint slide (use the pptx skill for
  that — this skill just produces the chart image to drop in).

## 10. When NOT to over-style

If the user wants a quick exploratory plot for their own analysis (not a
report deliverable), don't apply the full treatment unprompted — ask, or
default to a lighter touch (apply_style() for clean typography/gridlines,
skip insight-titles and direct labeling if it'd slow down quick iteration).
