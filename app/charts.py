from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from benefit_stress_lab import config, formatting
from theme import FONT_FAMILY, Palette

SENSITIVITY_LABELS = {
    "above_threshold_pct": "Above threshold",
    "above_threshold_change_pp": "Change vs current",
    "employer_saving_pct": "Employer saving",
}

SENSITIVITY_METRICS = {
    "above_threshold_pct": ("Share above threshold", formatting.pct, "%"),
    "above_threshold_change_pp": ("Change in share above threshold", formatting.pp, " pp"),
    "employer_saving_pct": ("Employer saving", formatting.pct, "%"),
}


def _channels(colour: str) -> list[int]:
    return [int(colour[i : i + 2], 16) for i in (1, 3, 5)]


def _rgba(colour: str, alpha: float) -> str:
    red, green, blue = _channels(colour)
    return f"rgba({red},{green},{blue},{alpha})"


def _luminance(colour: str) -> float:
    linear = []
    for channel in _channels(colour):
        value = channel / 255
        linear.append(value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4)
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _ink_on(colour: str) -> str:
    return "#FFFFFF" if _luminance(colour) < 0.2 else "#171717"


def _mix(scale: tuple[tuple[float, str], ...], position: float) -> str:
    stops = sorted(scale)
    position = min(max(position, 0.0), 1.0)
    for (start, low), (end, high) in zip(stops, stops[1:], strict=False):
        if position <= end:
            share = 0.0 if end == start else (position - start) / (end - start)
            mixed = [
                round(a + (b - a) * share)
                for a, b in zip(_channels(low), _channels(high), strict=True)
            ]
            return "#{:02X}{:02X}{:02X}".format(*mixed)
    return stops[-1][1]


def _headroom(values) -> list[float]:
    numbers = pd.to_numeric(pd.Series(list(values)), errors="coerce").dropna()
    low = min(0.0, numbers.min()) if len(numbers) else 0.0
    high = max(0.0, numbers.max()) if len(numbers) else 1.0
    span = (high - low) or 1.0
    return [low - 0.2 * span if low < 0 else 0.0, high + 0.2 * span]


def _label_font(pal: Palette, size: int = 12) -> dict:
    return {"color": pal.text_secondary, "size": size, "family": FONT_FAMILY}


def _style(fig: go.Figure, pal: Palette, *, height: int, legend: bool = False) -> go.Figure:
    fig.update_layout(
        template="none",
        height=height,
        margin={"l": 8, "r": 8, "t": 40 if legend else 12, "b": 8},
        font={"family": FONT_FAMILY, "color": pal.text_secondary, "size": 12},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=legend,
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.04,
            "xanchor": "left",
            "x": 0,
            "traceorder": "normal",
            "font": _label_font(pal),
        },
        hoverlabel={
            "bgcolor": pal.card,
            "bordercolor": pal.border,
            "font": {"family": FONT_FAMILY, "color": pal.text, "size": 12},
        },
        barcornerradius=3,
    )
    fig.update_xaxes(
        showgrid=False,
        zeroline=False,
        linecolor=pal.axis,
        ticks="",
        ticklabelstandoff=6,
        tickfont={"color": pal.muted, "size": 12},
        title_font=_label_font(pal),
        title_standoff=12,
        automargin=True,
    )
    fig.update_yaxes(
        gridcolor=pal.grid,
        zeroline=False,
        showline=False,
        ticks="",
        ticklabelstandoff=8,
        tickfont={"color": pal.muted, "size": 12},
        title_font=_label_font(pal),
        title_standoff=12,
        automargin=True,
    )
    return fig


def _panel_titles(fig: go.Figure, pal: Palette) -> None:
    fig.update_annotations(font={"color": pal.text_secondary, "size": 12, "family": FONT_FAMILY})


def plan_colours(plan_names: list[str], pal: Palette) -> dict[str, str]:
    colours = {plan_names[0]: pal.baseline}
    colours.update(zip(plan_names[1:], pal.plans, strict=False))
    return colours


def _label_positions(costs: pd.Series, shares: pd.Series) -> dict[str, str]:
    x_span = (costs.max() - costs.min()) or 1.0
    y_span = (shares.max() - shares.min()) or 1.0
    positions = {}
    for name in costs.index:
        crowded = any(
            other != name
            and abs(costs[other] - costs[name]) / x_span < 0.3
            and 0 <= (shares[other] - shares[name]) / y_span < 0.35
            for other in costs.index
        )
        positions[name] = "bottom center" if crowded else "top center"
    return positions


def cost_vs_affordability(summary: pd.DataFrame, pal: Palette, symbol: str) -> go.Figure:
    names = list(summary.index)
    colours = plan_colours(names, pal)
    positions = _label_positions(summary["employer_cost_total"], summary["above_threshold_pct"])
    fig = go.Figure()
    for name in names:
        row = summary.loc[name]
        fig.add_trace(
            go.Scatter(
                x=[row["employer_cost_total"]],
                y=[row["above_threshold_pct"]],
                name=name,
                mode="markers+text",
                text=[name],
                textposition=positions[name],
                textfont=_label_font(pal),
                marker={
                    "size": 13,
                    "color": colours[name],
                    "line": {"width": 2, "color": pal.card},
                },
                customdata=[[formatting.money(row["employer_cost_total"], symbol), row["label"]]],
                hovertemplate=(
                    "<b>%{customdata[0]}</b> employer cost<br>"
                    "<b>%{y:.1f}%</b> above threshold<br>"
                    "%{customdata[1]}<extra>%{fullData.name}</extra>"
                ),
                cliponaxis=False,
            )
        )
    costs = summary["employer_cost_total"]
    pad = max((costs.max() - costs.min()) * 0.18, costs.max() * 0.02)
    _style(fig, pal, height=340)
    fig.update_xaxes(
        title_text=f"Employer cost per year ({symbol})",
        tickformat=".3~s",
        nticks=6,
        range=[costs.min() - pad, costs.max() + pad],
    )
    fig.update_yaxes(
        title_text="Employees above threshold",
        ticksuffix="%",
        nticks=5,
        range=[0, max(summary["above_threshold_pct"].max() * 1.3, 5)],
    )
    return fig


def burden_ranges(
    quantiles: pd.DataFrame, threshold_pct: float, colours: dict[str, str], pal: Palette
) -> go.Figure:
    names = list(quantiles.index)[::-1]
    fig = go.Figure()
    for name in names:
        row = quantiles.loc[name]
        colour = colours[name]
        fig.add_trace(
            go.Scatter(
                x=[row["p5"], row["p95"]],
                y=[name, name],
                mode="lines",
                line={"color": _rgba(colour, 0.35), "width": 3},
                hoverinfo="skip",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=[row["p25"], row["p75"]],
                y=[name, name],
                mode="lines",
                line={"color": colour, "width": 14},
                hoverinfo="skip",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=[row["median"]],
                y=[name],
                mode="markers",
                marker={
                    "symbol": "line-ns",
                    "size": 15,
                    "line": {"color": pal.card, "width": 3},
                },
                customdata=[[row["p5"], row["p25"], row["p75"], row["p95"]]],
                hovertemplate=(
                    "<b>%{x:.1f}%</b> median<br>"
                    "Middle half: %{customdata[1]:.1f}% to %{customdata[2]:.1f}%<br>"
                    "5th to 95th percentile: %{customdata[0]:.1f}% to %{customdata[3]:.1f}%"
                    "<extra>%{y}</extra>"
                ),
            )
        )
        fig.add_annotation(
            xref="paper",
            x=1,
            y=name,
            text=f"median {row['median']:.1f}%",
            showarrow=False,
            xanchor="right",
            font=_label_font(pal),
        )
    _style(fig, pal, height=96 + 52 * len(names))
    fig.add_vline(
        x=threshold_pct,
        line={"color": pal.muted, "width": 1, "dash": "dash"},
        annotation_text=f"{threshold_pct:g}% threshold",
        annotation_position="top",
        annotation_font=_label_font(pal, 11),
    )
    fig.update_layout(margin={"t": 28})
    fig.update_xaxes(
        title_text="Burden as a share of salary",
        ticksuffix="%",
        range=[0, quantiles["p95"].max() * 1.5],
    )
    fig.update_yaxes(showgrid=False, type="category")
    return fig


def band_impact(
    segments: pd.DataFrame, plan_name: str, colour: str, pal: Palette, symbol: str
) -> go.Figure:
    seg = segments[segments["plan_name"] == plan_name]
    bands = seg["salary_band"].tolist()
    panels = (
        (
            "median_burden_change",
            f"Per year ({symbol})",
            lambda value: formatting.money(value, symbol, signed=True),
        ),
        ("median_burden_pct_change", "As a share of salary", formatting.pp),
    )
    fig = make_subplots(
        rows=1, cols=2, subplot_titles=[title for _, title, _ in panels], horizontal_spacing=0.1
    )
    _panel_titles(fig, pal)
    for col, (column, _, fmt) in enumerate(panels, start=1):
        values = seg[column]
        fig.add_trace(
            go.Bar(
                x=bands,
                y=values,
                marker={"color": colour},
                text=[fmt(value) if pd.notna(value) else "" for value in values],
                textposition="outside",
                constraintext="none",
                textfont=_label_font(pal, 11),
                cliponaxis=False,
                customdata=seg["headcount"],
                hovertemplate="<b>%{text}</b><br>%{x}<br>%{customdata} employees<extra></extra>",
            ),
            row=1,
            col=col,
        )
        for band, value in zip(bands, values, strict=True):
            if pd.isna(value):
                fig.add_annotation(
                    x=band,
                    y=0,
                    text="n too small",
                    showarrow=False,
                    yshift=12,
                    font={"color": pal.muted, "size": 11, "family": FONT_FAMILY},
                    row=1,
                    col=col,
                )
        fig.update_yaxes(range=_headroom(values), row=1, col=col)
    _style(fig, pal, height=290)
    fig.update_layout(bargap=0.62, margin={"t": 30})
    fig.update_yaxes(tickformat=",.0f", nticks=4, row=1, col=1)
    fig.update_yaxes(ticksuffix=" pp", nticks=4, row=1, col=2)
    return fig


def coverage_comparison(
    segments: pd.DataFrame,
    baseline_name: str,
    plan_name: str,
    colours: dict[str, str],
    pal: Palette,
) -> go.Figure:
    fig = go.Figure()
    shares = []
    for name in (baseline_name, plan_name):
        seg = segments[segments["plan_name"] == name]
        share = seg["above_threshold_pct"]
        shares.extend(share)
        fig.add_trace(
            go.Bar(
                x=[config.COVERAGE_TIER_LABELS[tier] for tier in seg["coverage_tier"]],
                y=share,
                name=name,
                marker={"color": colours[name]},
                text=[formatting.pct(value) if pd.notna(value) else "" for value in share],
                textposition="outside",
                constraintext="none",
                textfont=_label_font(pal, 11),
                cliponaxis=False,
                hovertemplate=(
                    "<b>%{text}</b> above threshold<br>%{x}<extra>%{fullData.name}</extra>"
                ),
            )
        )
    _style(fig, pal, height=290, legend=True)
    fig.update_layout(barmode="group", bargap=0.58, bargroupgap=0.1)
    fig.update_yaxes(ticksuffix="%", nticks=4, range=_headroom(shares))
    return fig


def _heatmap(
    z: list[list[float | None]],
    x: list[str],
    y: list[str],
    text: list[list[str]],
    hover: list[list[str]],
    pal: Palette,
    scale: tuple[tuple[float, str], ...],
    limits: tuple[float, float],
    bar_suffix: str,
) -> go.Figure:
    low, high = limits
    fig = go.Figure(
        go.Heatmap(
            z=z,
            x=x,
            y=y,
            customdata=hover,
            colorscale=[list(stop) for stop in scale],
            zmin=low,
            zmax=high,
            xgap=3,
            ygap=3,
            hoverongaps=False,
            hovertemplate="%{customdata}<extra></extra>",
            colorbar={
                "ticksuffix": bar_suffix,
                "thickness": 8,
                "outlinewidth": 0,
                "nticks": 5,
                "tickfont": {"color": pal.muted, "size": 11},
            },
        )
    )
    span = (high - low) or 1.0
    for row_index, row in enumerate(z):
        for col_index, value in enumerate(row):
            if value is None or pd.isna(value):
                ink = pal.muted
            else:
                ink = _ink_on(_mix(scale, (value - low) / span))
            fig.add_annotation(
                x=x[col_index],
                y=y[row_index],
                text=text[row_index][col_index],
                showarrow=False,
                font={"color": ink, "size": 12, "family": FONT_FAMILY},
            )
    return fig


def segment_heatmap(segments: pd.DataFrame, plan_name: str, pal: Palette) -> go.Figure:
    seg = segments[segments["plan_name"] == plan_name].set_index(["coverage_tier", "salary_band"])
    bands = list(config.SALARY_BAND_LABELS)
    tiers = list(config.COVERAGE_TIERS)
    tier_labels = [config.COVERAGE_TIER_LABELS[tier] for tier in tiers]
    z, text, hover = [], [], []
    for tier, tier_label in zip(tiers, tier_labels, strict=True):
        z_row, text_row, hover_row = [], [], []
        for band in bands:
            where = f"{tier_label}, {band}"
            if (tier, band) not in seg.index:
                z_row.append(None)
                text_row.append("none")
                hover_row.append(f"{where}<br>No employees")
                continue
            cell = seg.loc[(tier, band)]
            count = f"{int(cell['headcount'])} employees"
            if cell["suppressed"]:
                z_row.append(None)
                text_row.append("n too small")
                hover_row.append(f"{where}<br>{count}: too few to report")
                continue
            change = float(cell["median_burden_pct_change"])
            z_row.append(change)
            text_row.append(formatting.pp(change))
            hover_row.append(
                f"<b>{formatting.pp(change)}</b> median change in burden<br>{where}<br>{count}"
            )
        z.append(z_row)
        text.append(text_row)
        hover.append(hover_row)
    known = [abs(value) for row in z for value in row if value is not None]
    limit = max(known, default=1.0) or 1.0
    fig = _heatmap(
        z, bands, tier_labels, text, hover, pal, pal.diverging_scale, (-limit, limit), " pp"
    )
    _style(fig, pal, height=190)
    fig.update_xaxes(type="category", showline=False)
    fig.update_yaxes(showgrid=False, type="category")
    return fig


def winners_losers(summary: pd.DataFrame, pal: Palette) -> go.Figure:
    alternatives = summary.iloc[1:].iloc[::-1]
    names = list(alternatives.index)
    parts = (
        ("better_off", "Better off", pal.better),
        ("unchanged", "Unchanged", pal.unchanged),
        ("worse_off", "Worse off", pal.worse),
    )
    fig = go.Figure()
    for key, label, colour in parts:
        counts = alternatives[f"{key}_count"]
        shares = alternatives[f"{key}_pct"]
        fig.add_trace(
            go.Bar(
                y=names,
                x=counts,
                name=label,
                orientation="h",
                marker={"color": colour, "line": {"width": 2, "color": pal.card}},
                text=[
                    f"{int(count):,}" if share >= 8 else ""
                    for count, share in zip(counts, shares, strict=True)
                ],
                textposition="inside",
                insidetextanchor="middle",
                textfont={"color": _ink_on(colour), "size": 11, "family": FONT_FAMILY},
                customdata=shares,
                hovertemplate=(
                    "<b>%{x:,}</b> employees "
                    + label.lower()
                    + " (%{customdata:.1f}%)<br>%{y}<extra></extra>"
                ),
            )
        )
    _style(fig, pal, height=110 + 46 * len(names), legend=True)
    fig.update_layout(barmode="stack", bargap=0.5)
    fig.update_xaxes(title_text="Employees", nticks=6)
    fig.update_yaxes(showgrid=False)
    return fig


def sensitivity_heatmap(grid: pd.DataFrame, metric: str, pal: Palette) -> go.Figure:
    title, fmt, suffix = SENSITIVITY_METRICS[metric]
    index, columns = "high_use_shift_pct", "healthcare_cost_change_pct"
    values = grid.pivot(index=index, columns=columns, values=metric)
    labels = grid.pivot(index=index, columns=columns, values="label")
    x = [f"{change:+g}%" if change else "0%" for change in values.columns]
    y = [f"{shift:g}%" for shift in values.index]
    z = values.to_numpy().tolist()
    text = [[fmt(value) for value in row] for row in z]
    hover = [
        [
            f"<b>{text[i][j]}</b> {title.lower()}<br>"
            f"Costs {x[j]}, {y[i]} moved into high use<br>{labels.iat[i, j]}"
            for j in range(len(x))
        ]
        for i in range(len(y))
    ]
    low, high = float(values.min().min()), float(values.max().max())
    if low == high:
        high = low + 1.0
    fig = _heatmap(z, x, y, text, hover, pal, pal.sequential_scale, (low, high), suffix)
    _style(fig, pal, height=340)
    fig.update_xaxes(title_text="Healthcare cost change", type="category", showline=False)
    fig.update_yaxes(title_text="Moved into high use", showgrid=False, type="category")
    return fig


def contribution_curve(
    sweep: pd.DataFrame, colour: str, pal: Palette, symbol: str, marked: dict[float, str]
) -> go.Figure:
    hover = [
        [f"{pct:g}%", formatting.money(saving, symbol)]
        for pct, saving in zip(
            sweep["employer_contribution_pct"], sweep["employer_saving"], strict=True
        )
    ]
    fig = go.Figure(
        go.Scatter(
            x=sweep["employer_saving"],
            y=sweep["above_threshold_pct"],
            mode="lines+markers",
            line={"color": colour, "width": 2},
            marker={"size": 8, "color": colour, "line": {"width": 2, "color": pal.card}},
            customdata=hover,
            hovertemplate=(
                "Employer pays <b>%{customdata[0]}</b> of the premium<br>"
                "<b>%{customdata[1]}</b> saving<br>"
                "<b>%{y:.1f}%</b> above threshold<extra></extra>"
            ),
        )
    )
    for _, point in sweep.iterrows():
        label = marked.get(float(point["employer_contribution_pct"]))
        if label is not None:
            fig.add_annotation(
                x=point["employer_saving"],
                y=point["above_threshold_pct"],
                text=label,
                showarrow=False,
                xanchor="right",
                xshift=-6,
                yshift=12,
                font=_label_font(pal, 11),
            )
    _style(fig, pal, height=340)
    fig.update_xaxes(
        title_text=f"Employer saving per year ({symbol})",
        tickformat=".3~s",
        nticks=6,
        zeroline=True,
        zerolinecolor=pal.axis,
    )
    fig.update_yaxes(
        title_text="Employees above threshold", ticksuffix="%", nticks=5, rangemode="tozero"
    )
    return fig


def mitigation_bars(
    table: pd.DataFrame, best_key: str | None, colour: str, pal: Palette, symbol: str
) -> go.Figure:
    shown = table.iloc[::-1]
    fills = [colour if key == best_key else pal.context for key in shown["key"]]
    panels = (
        (
            "employer_saving",
            f"Employer saving per year ({symbol})",
            lambda value: formatting.money(value, symbol),
        ),
        ("above_threshold_pct", "Employees above threshold", formatting.pct),
    )
    fig = make_subplots(
        rows=1,
        cols=2,
        shared_yaxes=True,
        subplot_titles=[title for _, title, _ in panels],
        horizontal_spacing=0.08,
    )
    _panel_titles(fig, pal)
    for col, (column, _, fmt) in enumerate(panels, start=1):
        fig.add_trace(
            go.Bar(
                y=shown["title"],
                x=shown[column],
                orientation="h",
                marker={"color": fills},
                text=[fmt(value) for value in shown[column]],
                textposition="outside",
                constraintext="none",
                textfont=_label_font(pal, 11),
                cliponaxis=False,
                hovertemplate="<b>%{text}</b><br>%{y}<extra></extra>",
            ),
            row=1,
            col=col,
        )
        fig.update_xaxes(range=_headroom(shown[column]), row=1, col=col)
    _style(fig, pal, height=90 + 38 * len(shown))
    fig.update_layout(bargap=0.5, margin={"t": 30})
    fig.update_xaxes(showticklabels=False, showline=False)
    fig.update_yaxes(showgrid=False)
    return fig


def salary_band_counts(counts: pd.Series, pal: Palette) -> go.Figure:
    fig = go.Figure(
        go.Bar(
            x=list(counts.index),
            y=counts.to_numpy(),
            marker={"color": pal.primary},
            text=[f"{int(value):,}" for value in counts],
            textposition="outside",
            constraintext="none",
            textfont=_label_font(pal, 11),
            cliponaxis=False,
            hovertemplate="<b>%{y:,}</b> employees<br>%{x}<extra></extra>",
        )
    )
    _style(fig, pal, height=260)
    fig.update_layout(bargap=0.62)
    fig.update_xaxes(type="category")
    fig.update_yaxes(nticks=4, range=_headroom(counts))
    return fig
