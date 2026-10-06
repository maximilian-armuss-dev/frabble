"""Attempt-level overview charts: model facets, case outcomes and reported costs."""

from __future__ import annotations

from collections import Counter, defaultdict
from decimal import Decimal, ROUND_DOWN
from html import escape
from typing import Any, Mapping

import plotly.graph_objects as go
from plotly.colors import sample_colorscale
from plotly.subplots import make_subplots

from .overview_data import OUTCOMES


RATE_COLORS = [[0, "#E36A6A"], [0.5, "#F7F9FB"], [1, "#72C58C"]]
RATE_METRICS = (
    ("valid", "Pass rate", "completed responses"),
    ("truncated", "Truncation rate", "completed responses"),
    ("semantic", "Semantic failure rate", "completed responses"),
    ("transport", "Transport / request error rate", "scheduled attempts"),
)


def _overview(aggregate: Mapping[str, Any]) -> Mapping[str, Any]:
    if "overview" not in aggregate:
        raise ValueError("Load the run with the overview filter to include individual attempts.")
    return aggregate["overview"]


def _slices(aggregate: Mapping[str, Any]):
    buckets = defaultdict(list)
    for row in _overview(aggregate)["attempts"]:
        buckets[(row["language_representation"] or "unspecified",
                 row["reasoning_effort"] or "default")].append(row)
    for (representation, effort), rows in sorted(buckets.items()):
        context = f"{escape(representation)} · reasoning: {escape(effort)}" if len(buckets) > 1 else ""
        yield context, rows


def _model_label(model: str) -> str:
    return escape(model.removeprefix("or_"))


def _title(title: str, subtitle: str) -> str:
    return f"<b>{title}</b>" + (f" · {subtitle}" if subtitle else "")


def _style(figure: go.Figure, title: str, subtitle: str, *, height: int = 480) -> None:
    figure.update_layout(
        title=dict(text=_title(title, subtitle), x=0.02, y=1 - 28 / height, yanchor="top"),
        template="plotly_white", height=height,
        font=dict(family="Arial, sans-serif", size=12, color="#263448"),
        margin=dict(l=75, r=60, t=145, b=100),
        legend=dict(orientation="h", y=1 + 80 / (height - 245), x=0,
                    yanchor="bottom", font=dict(size=11), traceorder="normal"),
        hoverlabel=dict(align="left"),
    )


def _facets(rows: list[dict[str, Any]]):
    models = sorted({r["model"] for r in rows})
    nrows = len(models)
    figure = make_subplots(
        rows=nrows, cols=1, subplot_titles=[_model_label(m) for m in models],
        vertical_spacing=0.30 / nrows if nrows > 1 else 0,
    )
    positions = {model: (index + 1, 1) for index, model in enumerate(models)}
    for annotation in figure.layout.annotations:
        annotation.update(x=0, xanchor="left", font=dict(size=15, color="#263448"))
    return figure, models, positions, nrows


def _dimension_colors(dimensions: list[int]) -> dict[int, str]:
    span = max(dimensions) - min(dimensions)
    levels = [0.40 + 0.5 * (d - min(dimensions)) / span if span else 0.7 for d in dimensions]
    return dict(zip(dimensions, sample_colorscale("Blues", levels), strict=True))


def _money(value: float | None) -> str:
    if value is None:
        return "Not reported"
    cents = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    return f"${cents:,.2f}"


def display_run_summary(aggregate: Mapping[str, Any]):
    from IPython.display import HTML

    data = _overview(aggregate)
    records = data["attempts"]
    selected = data["selection_cost"]
    valid = sum(r["outcome"] == "valid" for r in records)
    completed = sum(r["completed"] for r in records)
    efforts = sorted({str(r.get("reasoning_effort") or "default") for r in records})
    cards = (
        ("Selected attempts", str(len(records)), f"{valid} valid · {completed} completed responses"),
        ("Selection · reported USD", _money(selected["usd"]),
         f"Cost reported for {selected['reported']}/{selected['attempts']} final records"),
        ("Reasoning effort", escape(efforts[0]) if len(efforts) == 1 else "Mixed",
         "Configured for selected attempts" if len(efforts) == 1 else escape(", ".join(efforts))),
    )
    cards_html = "".join(
        "<div style='flex:1;min-width:230px;padding:16px;background:#f3f6fa;"
        "border:1px solid #dbe2eb;border-radius:8px'>"
        f"<div>{label}</div><div style='font-size:25px;font-weight:700'>{value}</div>"
        f"<small>{note}</small></div>" for label, value, note in cards
    )
    cost_rows = "".join(
        f"<tr><th scope='row'>{_model_label(model)}</th>"
        f"<td>{_money(costs['selection']['usd'])}</td>"
        f"<td>{costs['selection']['reported']}/{costs['selection']['attempts']}</td></tr>"
        for model, costs in data["model_costs"].items()
        if costs["selection"]["attempts"]
    )
    return HTML(
        "<style>"
        ".frabble-run-summary{color-scheme:light;background:#fff!important;"
        "color:#263448!important;font-family:Arial,sans-serif;max-width:1200px;"
        "padding:20px;border:1px solid #dbe2eb;border-radius:10px;"
        "box-sizing:border-box;overflow-wrap:anywhere}"
        ".frabble-run-summary *{color:#263448!important}"
        ".frabble-run-summary :is(table,thead,tbody,tr,th,td,code){background:transparent!important}"
        ".frabble-run-summary table{width:100%;border-collapse:collapse!important;"
        "border:1px solid #ccd5e0;margin:16px 0 0;font-size:14px}"
        ".frabble-run-summary caption{text-align:left;font-weight:700;padding:0 0 10px}"
        ".frabble-run-summary :is(th,td){padding:10px 14px;border:1px solid #dbe2eb;"
        "text-align:right;font-variant-numeric:tabular-nums}"
        ".frabble-run-summary th:first-child{text-align:left}"
        ".frabble-run-summary tbody th{font-weight:400}"
        ".frabble-run-summary thead th{background:#edf2f7!important;font-weight:700}"
        ".frabble-run-summary tbody tr:nth-child(even)>*{background:#f7f9fc!important}"
        ".frabble-run-summary tfoot>*{background:#edf2f7!important;font-weight:700;"
        "border-top:2px solid #bcc8d7}"
        "</style><div class='frabble-run-summary'>"
        f"<p><b>Run:</b> <code>{escape(data['run_id'])}</code></p>"
        f"<div style='display:flex;flex-wrap:wrap;gap:12px'>{cards_html}</div>"
        "<div style='overflow-x:auto'><table>"
        "<caption>Reported model costs · selected cases</caption><thead><tr>"
        "<th scope='col'>Model</th><th scope='col'>Cost (USD)</th>"
        "<th scope='col'>Costs reported / attempts</th></tr></thead>"
        f"<tbody>{cost_rows}</tbody><tfoot><tr><th scope='row'>Total</th>"
        f"<td>{_money(selected['usd'])}</td>"
        f"<td>{selected['reported']}/{selected['attempts']}</td>"
        "</tr></tfoot></table></div></div>"
    )


def plot_rate_heatmaps(aggregate: Mapping[str, Any]) -> tuple[go.Figure, ...]:
    figures = []
    for subtitle, rows in _slices(aggregate):
        figure, models, positions, nrows = _facets(rows)
        sizes = sorted({r["board_size"] for r in rows})
        dims = sorted({r["dimensions"] for r in rows})
        cells = defaultdict(list)
        for row in rows:
            cells[(row["model"], row["dimensions"], row["board_size"])].append(row)
        blocks = []
        for metric_index, (metric, label, denominator_label) in enumerate(RATE_METRICS):
            start = len(figure.data)
            for model in models:
                values, texts, details = [], [], []
                for dimension in dims:
                    value_row, text_row, detail_row = [], [], []
                    for size in sizes:
                        attempts = cells[(model, dimension, size)]
                        counts = Counter(r["outcome"] for r in attempts)
                        denominator = (len(attempts) if metric == "transport"
                                       else sum(r["completed"] for r in attempts))
                        numerator = counts[metric]
                        value_row.append(numerator / denominator if denominator else None)
                        text = f"{numerator}/{denominator}" if denominator else "—"
                        text_row.append(text)
                        composition = "<br>".join(f"{OUTCOMES[k][0]}: {v}" for k, v in counts.items())
                        primary = Counter(r["failure"] for r in attempts if r["failure"])
                        detail_row.append(
                            f"{_model_label(model)} · {dimension}D · board {size}<br>"
                            f"{label}: {numerator}/{denominator} {denominator_label}<br>"
                            f"{composition}<br>Stored primary failures: {escape(str(dict(primary)))}"
                        )
                    values.append(value_row)
                    texts.append(text_row)
                    details.append(detail_row)
                row, col = positions[model]
                figure.add_trace(go.Heatmap(
                    x=[str(s) for s in sizes], y=[f"{d}D" for d in dims], z=values,
                    coloraxis="coloraxis", hovertext=details,
                    hovertemplate="%{hovertext}<extra></extra>", xgap=3, ygap=3,
                    visible=metric_index == 0, showscale=False,
                ), row=row, col=col)
                # Text remains visible on unmeasured cells, which have no heatmap color.
                figure.add_trace(go.Scatter(
                    x=[str(s) for d in dims for s in sizes],
                    y=[f"{d}D" for d in dims for s in sizes],
                    text=[t for line in texts for t in line],
                    hovertext=[t for line in details for t in line],
                    mode="text", textfont=dict(size=14, color="#172033"),
                    hovertemplate="%{hovertext}<extra></extra>",
                    showlegend=False, visible=metric_index == 0,
                ), row=row, col=col)
            blocks.append((start, len(figure.data)))
        _style(figure, "Pass rate", subtitle, height=(max(4, len(dims)) * 40 + 120) * nrows + 190)
        figure.update_layout(
            plot_bgcolor="#edf0f4",
            coloraxis=dict(cmin=0, cmax=1, colorscale=RATE_COLORS,
                           colorbar=dict(title="Rate", tickformat=".0%", len=180,
                                         lenmode="pixels", y=1, yanchor="top", thickness=14)),
        )
        figure.update_xaxes(type="category", categoryorder="array", categoryarray=[str(s) for s in sizes],
                            title_text="Board size", showgrid=False, zeroline=False)
        figure.update_yaxes(type="category", categoryorder="array", categoryarray=[f"{d}D" for d in dims],
                            autorange="reversed", showgrid=False, zeroline=False)
        _metric_menu(figure, blocks, [
            (label, subtitle)
            for metric, label, denominator in RATE_METRICS
        ], axis_updates=[{"coloraxis.reversescale": metric != "valid"} for metric, _, _ in RATE_METRICS])
        figures.append(figure)
    return tuple(figures)


def _metric_menu(figure, blocks, labels, *, axis_updates=None, common=()):
    buttons = []
    for index, ((start, end), (label, subtitle)) in enumerate(zip(blocks, labels, strict=True)):
        layout = {"title.text": _title(label, subtitle)}
        if axis_updates:
            layout.update(axis_updates[index])
        buttons.append(dict(label=label, method="update", args=[
            {"visible": [start <= i < end or i in common for i in range(len(figure.data))]}, layout,
        ]))
    plot_height = figure.layout.height - figure.layout.margin.t - figure.layout.margin.b
    figure.update_layout(updatemenus=[dict(
        buttons=buttons, direction="down", x=0, y=1 + 35 / plot_height, xanchor="left", yanchor="bottom",
        bgcolor="white", bordercolor="#ccd5e0", font=dict(size=12),
    )])


def plot_outcome_composition(aggregate: Mapping[str, Any]) -> tuple[go.Figure, ...]:
    figures = []
    for subtitle, rows in _slices(aggregate):
        model_counts = defaultdict(Counter)
        for row in rows:
            model_counts[row["model"]][row["outcome"]] += 1
        failure_order = ("semantic", "format", "truncated", "provider", "transport", "unknown")

        def failure_profile(model):
            # Group by the categories that occur, irrespective of their counts
            # or whether the model also returned any valid moves.
            return tuple(index for index, category in enumerate(failure_order)
                         if model_counts[model][category] > 0)

        models = sorted(model_counts, key=lambda model: (
            model_counts[model]["truncated"] == sum(model_counts[model].values()),
            failure_profile(model),
            -model_counts[model]["valid"] / sum(model_counts[model].values()), model,
        ))
        figure = go.Figure()
        for outcome, (label, color, _, _) in OUTCOMES.items():
            counts = [sum(r["model"] == m and r["outcome"] == outcome for r in rows) for m in models]
            if not any(counts):
                continue
            totals = [sum(r["model"] == m for r in rows) for m in models]
            failures = [sum(r["model"] == m and r["outcome"] != "valid" for r in rows) for m in models]
            figure.add_bar(
                y=[_model_label(m) for m in models], x=[n / d for n, d in zip(counts, totals)],
                orientation="h", name=label, marker=dict(color=color, line=dict(color="white", width=1.5)),
                text=[str(n) if n else "" for n in counts], textposition="inside",
                insidetextanchor="middle", textfont=dict(size=13, color="#172033"),
                customdata=[[n, d, f"{n / f:.0%}" if f and outcome != "valid" else "—"]
                            for n, d, f in zip(counts, totals, failures)],
                hovertemplate=("%{y}<br>" + label + ": %{customdata[0]}/%{customdata[1]} scheduled"
                               "<br>%{x:.1%} of all attempts<br>%{customdata[2]} of unsuccessful attempts<extra></extra>"),
            )
        _style(figure, "Outcome composition", subtitle, height=230 + 46 * len(models))
        figure.update_layout(barmode="stack", bargap=0.28, margin=dict(t=95, l=180),
                             legend=dict(y=-0.20, yanchor="top", traceorder="normal"))
        figure.update_xaxes(range=[0, 1], tickformat=".0%", dtick=0.2,
                            title_text="Share of scheduled attempts", gridcolor="#e8edf3", zeroline=False)
        figure.update_yaxes(autorange="reversed", categoryorder="array",
                            categoryarray=[_model_label(m) for m in models])
        figures.append(figure)
    return tuple(figures)


def _attempt_hover(row: Mapping[str, Any]) -> str:
    checks = ", ".join(row["violations"]) if row["outcome"] == "semantic" else "—"
    return (
        f"{_model_label(row['model'])}<br>Case: {escape(str(row['case_id']))}<br>"
        f"{row['dimensions']}D · board {row['board_size']} · round {row['sampling_round']}<br>"
        f"Outcome: {OUTCOMES[row['outcome']][0]}<br>"
        f"Stored failure: {escape(str(row['failure'] or '—'))}<br>"
        f"Finish reason: {escape(str(row['finish_reason'] or '—'))}<br>"
        f"Violated checks: {escape(checks)}<br>{escape(str(row['message'])[:300])}"
    )


def plot_case_outcomes(aggregate: Mapping[str, Any]) -> tuple[go.Figure, ...]:
    figures = []
    categories = list(OUTCOMES)
    colorscale = []
    for index, (_, color, _, _) in enumerate(OUTCOMES.values()):
        colorscale.extend([(index / len(categories), color), ((index + 1) / len(categories), color)])
    for subtitle, rows in _slices(aggregate):
        models = sorted({r["model"] for r in rows})
        cases = sorted({(r["board_size"], r["sampling_round"], r["dimensions"], r["case_id"]) for r in rows})
        # Keep long runs readable without collapsing distinct cases into a mean.
        for offset in range(0, len(cases), 24):
            page = cases[offset:offset + 24]
            cells = {(r["model"], r["case_id"]): r for r in rows}
            if len(cells) != len(rows):
                raise ValueError("Multiple saved attempts for the same model and case in one overview slice.")
            values, texts, hovers = [], [], []
            for model in models:
                line = [cells.get((model, case_id)) for _, _, _, case_id in page]
                values.append([categories.index(r["outcome"]) if r else None for r in line])
                texts.append([OUTCOMES[r["outcome"]][2] if r else "—" for r in line])
                hovers.append([_attempt_hover(r) if r else "No scheduled attempt" for r in line])
            figure = go.Figure(go.Heatmap(
                x=list(range(len(page))), y=[_model_label(m) for m in models], z=values,
                zmin=-0.5, zmax=len(categories) - 0.5, colorscale=colorscale,
                text=texts, texttemplate="%{text}", textfont=dict(color="white"), hovertext=hovers,
                hovertemplate="%{hovertext}<extra></extra>", showscale=False, xgap=3, ygap=3,
            ))
            for key, (label, color, code, _) in OUTCOMES.items():
                if any(r["outcome"] == key for r in rows):
                    figure.add_scatter(x=[None], y=[None], mode="markers", name=f"{code} · {label}",
                                       marker=dict(color=color, symbol="square", size=11), hoverinfo="skip")
            suffix = f" · cases {offset + 1}–{offset + len(page)} of {len(cases)}" if len(cases) > 24 else ""
            _style(figure, "Case outcomes", subtitle + suffix, height=330 + 40 * len(models))
            figure.update_layout(plot_bgcolor="#edf0f4", margin=dict(t=95, l=180))
            figure.update_xaxes(tickmode="array", tickvals=list(range(len(page))),
                                ticktext=[f"{b} · {d}D<br>r{r}" for b, r, d, _ in page],
                                title_text="Board size · dimension / sampling round", showgrid=False)
            figure.update_yaxes(autorange="reversed", showgrid=False)
            for index in range(1, len(page)):
                if page[index][:2] != page[index - 1][:2]:
                    figure.add_vline(x=index - 0.5, line_color="#263448", line_width=1)
            figures.append(figure)
    return tuple(figures)


def _point_figures(aggregate, metrics, *, valid_only=False, budgets=False):
    figures = []
    for subtitle, rows in _slices(aggregate):
        figure, models, positions, nrows = _facets(rows)
        sizes = sorted({r["board_size"] for r in rows})
        dims = sorted({r["dimensions"] for r in rows})
        colors = _dimension_colors(dims)
        size_gap = min((b - a for a, b in zip(sizes, sizes[1:])), default=max(sizes[0] * 0.2, 1))
        padding = max((sizes[-1] - sizes[0]) * 0.05, size_gap * 0.2, 1)
        x_range = [sizes[0] - padding, sizes[-1] + padding]
        blocks, layouts = [], []
        eligible = [r for r in rows if not valid_only or r["outcome"] == "valid"]
        base_annotations = list(figure.layout.annotations)
        for metric_index, (key, label, unit) in enumerate(metrics):
            start = len(figure.data)
            available = [r for r in eligible if r[key] is not None]
            maximum = max([r[key] for r in available] + [1])
            if budgets and key == "completion_tokens":
                maximum = max([r["token_limit"] for r in rows if r["token_limit"] is not None] + [maximum])
            ymax = 1.05 if key == "score_ratio" and maximum <= 1 else maximum * 1.12
            annotations = list(base_annotations)
            for model in models:
                row, col = positions[model]
                observations = [r for r in available if r["model"] == model]
                for dimension in dims:
                    for category in OUTCOMES:
                        points = sorted([r for r in observations if r["dimensions"] == dimension
                                         and r["outcome"] == category],
                                        key=lambda r: (r["board_size"], r["sampling_round"], r["case_id"]))
                        if not points:
                            continue
                        dimension_offset = ((dims.index(dimension) - (len(dims) - 1) / 2)
                                            / max(len(dims), 1) * size_gap * 0.08)
                        size_groups = defaultdict(list)
                        for point in points:
                            size_groups[point["board_size"]].append(point)
                        x, y, hover = [], [], []
                        for size, same_size in size_groups.items():
                            for i, point in enumerate(same_size):
                                jitter = ((i / (len(same_size) - 1) - 0.5) * size_gap * 0.02) if len(same_size) > 1 else 0
                                x.append(size + dimension_offset + jitter)
                                y.append(point[key])
                                value = f"{point[key]:.1%}" if key == "score_ratio" else f"{point[key]:,.2f}"
                                hover.append(_attempt_hover(point) + f"<br>{label}: {value}"
                                             f"<br>Valid score: {point['score']} · optimum: {point['optimal_score']}"
                                             f"<br>Configured completion budget: {point['token_limit']}")
                        figure.add_trace(go.Scatter(
                            x=x, y=y, mode="markers", hovertext=hover,
                            hovertemplate="%{hovertext}<extra></extra>", showlegend=False,
                            marker=dict(color=colors[dimension], symbol=OUTCOMES[category][3],
                                        size=11, line=dict(width=0.6, color="white")),
                            visible=metric_index == 0,
                        ), row=row, col=col)
                if budgets and key == "completion_tokens":
                    for limit in sorted({r["token_limit"] for r in rows if r["model"] == model and r["token_limit"] is not None}):
                        figure.add_trace(go.Scatter(
                            x=x_range, y=[limit, limit], mode="lines",
                            line=dict(color="#7e8999", dash="dash", width=1), showlegend=False,
                            hovertemplate=f"Configured budget: {limit:,.0f}<extra></extra>", visible=metric_index == 0,
                        ), row=row, col=col)
                if key == "score_ratio":
                    figure.add_trace(go.Scatter(
                        x=x_range, y=[1, 1], mode="lines",
                        line=dict(color="#7e8999", dash="dash", width=1), showlegend=False,
                        hovertemplate="Certified optimum<extra></extra>", visible=metric_index == 0,
                    ), row=row, col=col)
                if not observations:
                    axis_index = row
                    suffix = str(axis_index) if axis_index > 1 else ""
                    annotations.append(dict(
                        x=0.5, y=0.45, xref=f"x{suffix} domain", yref=f"y{suffix} domain",
                        text="No eligible observations", showarrow=False, font=dict(size=11, color="#778397"),
                    ))
            blocks.append((start, len(figure.data)))
            update = {"annotations": annotations}
            for model in models:
                row, col = positions[model]
                axis_index = row
                axis = "yaxis" + (str(axis_index) if axis_index > 1 else "")
                update.update({f"{axis}.range": [0, ymax], f"{axis}.tickformat": ".0%" if key == "score_ratio" else ",~g",
                               f"{axis}.title.text": unit if col == 1 else ""})
            layouts.append(update)
        common = []
        for dimension in dims:
            common.append(len(figure.data))
            figure.add_scatter(x=[None], y=[None], mode="markers", name=f"{dimension}D",
                               marker=dict(color=colors[dimension], symbol="circle", size=10),
                               hoverinfo="skip")
        if not valid_only:
            for category, (label, _, _, symbol) in OUTCOMES.items():
                if any(r["outcome"] == category and any(r[key] is not None for key, _, _ in metrics) for r in eligible):
                    common.append(len(figure.data))
                    figure.add_scatter(x=[None], y=[None], mode="markers", name=label,
                                       marker=dict(color="#617087", symbol=symbol, size=9), hoverinfo="skip")
        labels = [(label, subtitle) for _, label, _ in metrics]
        _style(figure, labels[0][0], labels[0][1], height=280 * nrows + 210)
        figure.update_xaxes(type="linear", tickmode="array", tickvals=sizes, ticktext=[str(s) for s in sizes],
                            range=x_range, title_text="Board size", zeroline=False, gridcolor="#e8edf3")
        figure.update_layout(**layouts[0])
        if len(metrics) > 1:
            _metric_menu(figure, blocks, labels, axis_updates=layouts, common=common)
        figures.append(figure)
    return tuple(figures)


def plot_move_quality(aggregate):
    return _point_figures(aggregate, (
        ("score_ratio", "Score / certified optimum", "Share of optimum"),
        ("score", "Word score", "Points"),
    ), valid_only=True)


def plot_token_usage(aggregate):
    return _point_figures(aggregate, (
        ("completion_tokens", "Completion tokens", "Tokens"),
        ("prompt_tokens", "Input tokens", "Tokens"),
        ("reasoning_tokens", "Reasoning tokens", "Tokens"),
    ), budgets=True)


def plot_runtime(aggregate):
    return _point_figures(aggregate, (
        ("runtime_minutes", "Request runtime including retries and retry waits", "Minutes"),
    ))
