---
name: mckinsey-charts
description: Create polished, professional, McKinsey/consulting-style charts and plots with Python (matplotlib and/or plotly) — clean typography, restrained color, insight-driven titles, direct data labels, minimal chart junk. Use this skill whenever the user asks for a "chart," "graph," "plot," "visualization," "dashboard," wants data shown in a report/deck/analysis, or asks for something to look "professional," "modern," "clean," "McKinsey-style," "consulting-style," or "BCG/Bain-style." Also trigger when the user shares data (CSV, dataframe, numbers) and asks to visualize, chart, or plot it, even without explicitly requesting a particular style — default to this polished style rather than default matplotlib/plotly aesthetics unless the user asks for something quick and rough.
---

# McKinsey-Style Charts

Produce charts that look like they came out of a consulting deck: one clear
insight per chart, restrained color, no chart junk, direct labels instead of
legends, titles that state the takeaway rather than the variable name.

## Workflow

1. **Understand the data and find the insight.** Before writing any plotting
   code, look at the data and decide: what is the ONE thing this chart should
   communicate? (e.g., "X overtook Y", "growth accelerated after Q2",
   "three regions account for 80% of the gap"). This determines the chart
   type, what gets the accent color, and the title.

2. **Pick the chart type** based on what the insight is (ranking, trend,
   comparison, part-to-whole, correlation, distribution). See the chart-type
   selection table in `references/style_guide.md` — read it if you're unsure,
   especially for waterfall, slope, or part-to-whole charts.

3. **Pick the library:**
   - Default to **matplotlib** for static PNG/SVG output (reports, decks,
     docs) — this is the common case.
   - Use **plotly** only if the user wants interactivity, hover tooltips, or
     an HTML/web embed.

4. **Apply the theme and helpers.** Copy the relevant script
   (`scripts/mckinsey_mpl.py` or `scripts/mckinsey_plotly.py`) into the
   working directory and import from it rather than rewriting styling from
   scratch:
   ```python
   from mckinsey_mpl import apply_style, PALETTE, SEQUENCE, takeaway_title, add_source, style_bar_labels
   apply_style()
   ```

5. **Build the chart:**
   - Write the insight-style title with `takeaway_title()` / `add_takeaway_title()`.
   - Color the one thing that matters with `PALETTE["accent"]` or
     `PALETTE["blue_dark"]`; everything else gray (`PALETTE["gray_light"]`)
     or `SEQUENCE`.
   - Label directly (`style_bar_labels()`, `direct_label_lines()`) instead of
     leaving a legend, when there are few enough series/bars (~5 or fewer).
   - Sort categorical bar charts (usually descending) rather than leaving
     them in arbitrary/alphabetical order, unless order is meaningful
     (e.g., time, a natural sequence).
   - Add a source line with `add_source()`.

6. **Export at report quality:**
   - matplotlib: `plt.savefig(path, dpi=300, bbox_inches="tight")` — use
     `.svg` if the user needs to edit it in Illustrator/PowerPoint, `.png`
     otherwise.
   - plotly: `fig.write_html(path)` for interactive, or
     `fig.write_image(path, scale=3)` for a static export (requires
     `kaleido`: `pip install kaleido --break-system-packages`).

7. **Sanity check before presenting:** does the title state an insight (not
   just a label)? Is there exactly one accent color doing the work? Did you
   remove gridlines/borders/legend you didn't need? If the chart is going
   into a Word doc, PowerPoint deck, or PDF, hand off to the `docx`, `pptx`,
   or `pdf` skill respectively to assemble the final deliverable — this
   skill only produces the chart image/file itself.

## Quick reference: do / don't

| Do | Don't |
|---|---|
| Title states the insight | Title is just the variable/axis name |
| One accent color on the one thing that matters | Rainbow/default color cycle |
| Direct labels on bars/lines | Legend + axis as the only way to read values |
| Light/no gridlines, no chart border | Heavy gridlines, boxed plot area |
| Sorted bars (when order isn't inherently meaningful) | Alphabetical/arbitrary bar order |
| Source line, bottom-left, small gray text | No sourcing |
| Sans-serif, left-aligned title | Centered title, serif font |

## Going deeper

For full design rationale, the chart-type selection table, number formatting
rules, and guidance on when to dial the styling back, read
`references/style_guide.md`.

For matplotlib-specific helper function signatures, read
`scripts/mckinsey_mpl.py` directly (it's short and documented inline).

For plotly-specific helpers, read `scripts/mckinsey_plotly.py`.

## Dependencies

- matplotlib (usually preinstalled)
- plotly + kaleido, only if interactive/HTML output is needed:
  `pip install plotly kaleido --break-system-packages`
