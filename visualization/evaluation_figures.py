from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from src.evaluation.result_index import (
    INDEX_FILENAME,
    load_or_build_result_index,
)

from .board_figures import PROJECT_ROOT

TIER_ORDER = ("low", "medium", "high", "stress")
MODEL_ORDER = ("gpt-5-nano", "gpt-5-mini", "gpt-5")


def resolve_evaluation_run(
    case_set: str,
    run_id: str,
    *,
    project_root: str | Path = PROJECT_ROOT,
) -> Path:
    runs_dir = Path(project_root) / "outputs" / "evaluation" / case_set / "runs"
    run_dir = runs_dir / run_id
    if not run_dir.exists():
        raise FileNotFoundError(f"Evaluation run not found: {run_dir}")
    return run_dir


def load_evaluation_aggregate(run_dir: str | Path) -> dict[str, Any]:
    path = Path(run_dir) / "aggregate.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Aggregate root must be an object: {path}")
    return data


def load_evaluation_results(
    case_set: str | None,
    run_id: str | None = None,
    *,
    project_root: str | Path = PROJECT_ROOT,
) -> tuple[Path, dict[str, Any]]:
    resolved_case_set = case_set or latest_completed_case_set(
        project_root=project_root
    )
    if run_id is not None:
        run_dir = resolve_evaluation_run(
            resolved_case_set,
            run_id,
            project_root=project_root,
        )
        return run_dir, load_evaluation_aggregate(run_dir)

    case_root = (
        Path(project_root)
        / "outputs"
        / "evaluation"
        / resolved_case_set
    )
    index = load_or_build_result_index(case_root)
    return case_root / INDEX_FILENAME, dict(index["aggregate"])


def latest_completed_case_set(
    *,
    project_root: str | Path = PROJECT_ROOT,
) -> str:
    evaluation_root = Path(project_root) / "outputs" / "evaluation"
    completed = []
    for manifest_path in evaluation_root.glob("*/runs/*/run-manifest.json"):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("status") != "complete":
            continue
        completed.append(
            (
                str(manifest.get("completed_at") or ""),
                str(manifest.get("case_set") or manifest_path.parents[2].name),
            )
        )
    if not completed:
        raise FileNotFoundError(
            f"No completed evaluation run found under {evaluation_root}"
        )
    return max(completed)[1]


def plot_pass_rate_heatmaps(aggregate: Mapping[str, Any]) -> tuple[object, ...]:
    import plotly.graph_objects as go

    figures = []
    for representation, effort, groups in _group_slices(aggregate):
        models = sorted({str(group["model"]) for group in groups})
        tiers = _ordered_tiers(groups)
        values = [
            [
                _group_value(groups, model, tier, "pass_rate")
                for tier in tiers
            ]
            for model in models
        ]
        labels = [
            ["" if value is None else f"{value:.1%}" for value in row]
            for row in values
        ]
        figure = go.Figure(
            go.Heatmap(
                x=tiers,
                y=models,
                z=values,
                zmin=0,
                zmax=1,
                colorscale="RdYlGn",
                text=labels,
                texttemplate="%{text}",
                colorbar={"title": "pass rate"},
                hovertemplate="model=%{y}<br>tier=%{x}<br>pass=%{z:.1%}<extra></extra>",
            )
        )
        _style_figure(
            figure,
            "Pass rate by model and tier",
            metadata=_plot_metadata(representation, effort, groups),
            x_title="complexity tier",
            y_title="model",
        )
        figures.append(figure)
    return tuple(figures)


def plot_primary_failure_bars(
    aggregate: Mapping[str, Any],
) -> tuple[object, ...]:
    import plotly.graph_objects as go

    figures = []
    for representation, effort, groups in _group_slices(aggregate):
        ordered = sorted(
            groups,
            key=lambda group: (
                str(group["model"]),
                _tier_key(str(group["tier"])),
            ),
        )
        labels = [f"{group['model']} · {group['tier']}" for group in ordered]
        failure_types = sorted(
            {
                failure
                for group in ordered
                for failure in group["primary_failures"]
            }
        )
        palette = _failure_colors(failure_types)
        figure = go.Figure()
        shown_in_legend: set[str] = set()
        for label, group in zip(labels, ordered, strict=True):
            failures = sorted(
                group["primary_failures"].items(),
                key=lambda item: (-int(item[1]), str(item[0])),
            )
            for failure_type, count in failures:
                figure.add_bar(
                    name=failure_type,
                    x=[label],
                    y=[_rate(int(count), int(group["failed"]))],
                    customdata=[int(count)],
                    marker_color=palette[failure_type],
                    legendgroup=failure_type,
                    showlegend=failure_type not in shown_in_legend,
                    hovertemplate=(
                        "%{x}<br>"
                        + failure_type
                        + ": %{customdata} (%{y:.1%} of failures)<extra></extra>"
                    ),
                )
                shown_in_legend.add(failure_type)
        figure.update_layout(barmode="stack")
        _style_figure(
            figure,
            "Primary failure composition",
            metadata=_plot_metadata(representation, effort, groups),
            x_title="model and tier",
            y_title="share of failed attempts",
        )
        figure.update_layout(legend={"traceorder": "reversed"})
        figure.update_xaxes(
            categoryorder="array",
            categoryarray=labels,
        )
        figure.update_yaxes(tickformat=".0%", range=[0, 1])
        figures.append(figure)
    return tuple(figures)


def plot_grammar_pass_rates(
    aggregate: Mapping[str, Any],
) -> tuple[object, ...]:
    import plotly.graph_objects as go

    figures = []
    for representation, effort, groups in _group_slices(aggregate):
        for tier in _ordered_tiers(groups):
            tier_groups = [
                group for group in groups if str(group["tier"]) == tier
            ]
            grammar_ids = sorted(
                {
                    _grammar_id(grammar)
                    for group in tier_groups
                    for grammar in group["grammars"]
                }
            )
            if not grammar_ids:
                continue
            grammar_labels = [
                f"Grammar {index}"
                for index in range(1, len(grammar_ids) + 1)
            ]
            ordered_groups = sorted(
                tier_groups,
                key=lambda group: str(group["model"]),
            )
            values = [
                [
                    _grammar_value(group, grammar_id)
                    for grammar_id in grammar_ids
                ]
                for group in ordered_groups
            ]
            text = [
                ["" if value is None else f"{value:.0%}" for value in row]
                for row in values
            ]
            figure = go.Figure(
                go.Heatmap(
                    x=grammar_labels,
                    y=[str(group["model"]) for group in ordered_groups],
                    z=values,
                    zmin=0,
                    zmax=1,
                    colorscale="RdYlGn",
                    text=text,
                    texttemplate="%{text}",
                    customdata=[
                        grammar_ids for _group in ordered_groups
                    ],
                    colorbar={"title": "pass rate"},
                    hovertemplate=(
                        "model=%{y}<br>grammar=%{x}<br>"
                        "sample=%{customdata}<br>"
                        "pass=%{z:.1%}<extra></extra>"
                    ),
                )
            )
            _style_figure(
                figure,
                "Robustness across sampled grammars",
                metadata=_plot_metadata(
                    representation,
                    effort,
                    groups,
                    tier=tier,
                ),
                x_title="sampled grammar",
                y_title="model",
            )
            figures.append(figure)
    return tuple(figures)


def plot_token_usage_bars(
    aggregate: Mapping[str, Any],
) -> tuple[object, ...]:
    import plotly.graph_objects as go

    figures = []
    for representation, effort, groups in _group_slices(aggregate):
        ordered = _ordered_groups(groups)
        labels = [_group_label(group) for group in ordered]
        prompt = [_usage_mean(group, "prompt_tokens") for group in ordered]
        reasoning = [_usage_mean(group, "reasoning_tokens") for group in ordered]
        visible = [
            max(
                _usage_mean(group, "completion_tokens")
                - _usage_mean(group, "reasoning_tokens"),
                0,
            )
            for group in ordered
        ]
        figure = go.Figure()
        for name, values in (
            ("prompt", prompt),
            ("reasoning", reasoning),
            ("visible output", visible),
        ):
            bar_options = {
                "name": name,
                "x": labels,
                "y": values,
                "hovertemplate": (
                    "%{x}<br>" + name + ": %{y:,.0f}<extra></extra>"
                ),
            }
            if name == "visible output":
                bar_options.update(
                    {
                        "text": [
                            f"{sum(parts):,.0f}"
                            for parts in zip(
                                prompt,
                                reasoning,
                                visible,
                                strict=True,
                            )
                        ],
                        "textposition": "outside",
                    }
                )
            figure.add_bar(
                **bar_options,
            )
        figure.update_layout(barmode="stack")
        _style_figure(
            figure,
            "Average token usage per attempt",
            metadata=_plot_metadata(representation, effort, groups),
            x_title="model and tier",
            y_title="average tokens",
        )
        figures.append(figure)
    return tuple(figures)


def plot_latency_tables(
    aggregate: Mapping[str, Any],
) -> tuple[object, ...]:
    import plotly.graph_objects as go

    figures = []
    for representation, effort, groups in _group_slices(aggregate):
        present_tiers = set(_ordered_tiers(groups))
        tiers = list(TIER_ORDER)
        tiers.extend(sorted(present_tiers - set(tiers)))
        present_models = {str(group["model"]) for group in groups}
        models = list(MODEL_ORDER)
        models.extend(sorted(present_models - set(models)))
        runtime_columns = [
            [
                _format_seconds(
                    _group_summary_mean(
                        groups,
                        model,
                        tier,
                        family="timing",
                        metric="llm_elapsed_seconds",
                    )
                )
                for model in models
            ]
            for tier in tiers
        ]
        figure = go.Figure(
            go.Table(
                header={
                    "values": ["Model", *[tier.title() for tier in tiers]],
                    "align": ["left", *(["right"] * len(tiers))],
                    "fill_color": "#e8eef7",
                    "font": {"color": "#172033", "size": 13},
                    "height": 30,
                },
                cells={
                    "values": [
                        [_display_model(model) for model in models],
                        *runtime_columns,
                    ],
                    "align": ["left", *(["right"] * len(tiers))],
                    "fill_color": "#ffffff",
                    "font": {"color": "#172033", "size": 12},
                    "height": 28,
                },
            )
        )
        _style_figure(
            figure,
            "Average LLM runtime per attempt",
            metadata=_plot_metadata(representation, effort, groups),
        )
        figure.update_layout(height=250 + 28 * len(models))
        figures.append(figure)
    return tuple(figures)


def _group_slices(
    aggregate: Mapping[str, Any],
) -> list[tuple[str, str, list[Mapping[str, Any]]]]:
    buckets: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for group in aggregate["groups"]:
        representation = str(group["language_representation"])
        effort = str(group.get("reasoning_effort") or "default")
        buckets.setdefault((representation, effort), []).append(group)
    return [
        (representation, effort, groups)
        for (representation, effort), groups in sorted(buckets.items())
    ]


def _ordered_tiers(groups: list[Mapping[str, Any]]) -> list[str]:
    return sorted(
        {str(group["tier"]) for group in groups},
        key=_tier_key,
    )


def _ordered_groups(
    groups: list[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    return sorted(
        groups,
        key=lambda group: (
            str(group["model"]),
            _tier_key(str(group["tier"])),
        ),
    )


def _tier_key(tier: str) -> tuple[int, str]:
    try:
        return (TIER_ORDER.index(tier), tier)
    except ValueError:
        return (len(TIER_ORDER), tier)


def _group_value(
    groups: list[Mapping[str, Any]],
    model: str,
    tier: str,
    field: str,
) -> Any:
    for group in groups:
        if group["model"] == model and group["tier"] == tier:
            return group.get(field)
    return None


def _group_summary_mean(
    groups: list[Mapping[str, Any]],
    model: str,
    tier: str,
    *,
    family: str,
    metric: str,
) -> float | None:
    for group in groups:
        if group["model"] == model and group["tier"] == tier:
            value = group.get(family, {}).get(metric, {}).get("mean")
            return float(value) if value is not None else None
    return None


def _grammar_id(grammar: Mapping[str, Any]) -> str:
    return (
        f"r{int(grammar['sampling_round']):02d}."
        f"g{int(grammar['grammar_sample_index']):02d}"
    )


def _grammar_value(
    group: Mapping[str, Any],
    grammar_id: str,
) -> float | None:
    for grammar in group["grammars"]:
        if _grammar_id(grammar) == grammar_id:
            return grammar.get("pass_rate")
    return None


def _group_label(group: Mapping[str, Any]) -> str:
    return f"{group['model']} · {group['tier']}"


def _usage_mean(group: Mapping[str, Any], metric: str) -> float:
    return _summary_mean(group, family="usage", metric=metric)


def _summary_mean(
    group: Mapping[str, Any],
    *,
    family: str,
    metric: str,
) -> float:
    value = group.get(family, {}).get(metric, {}).get("mean")
    return float(value or 0)


def _plot_metadata(
    representation: str,
    effort: str,
    groups: list[Mapping[str, Any]],
    *,
    tier: str | None = None,
) -> Mapping[str, str]:
    tiers = tier or ", ".join(_ordered_tiers(groups))
    return {
        "Tier": tiers,
        "Representation": representation,
        "Reasoning": effort,
    }


def _format_seconds(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f} s"


def _display_model(model: str) -> str:
    labels = {
        "gpt-5-nano": "GPT-5 Nano",
        "gpt-5-mini": "GPT-5 Mini",
        "gpt-5": "GPT-5",
    }
    return labels.get(model, model)


def _failure_colors(failure_types: list[str]) -> dict[str, str]:
    from plotly.colors import qualitative

    colors = qualitative.Safe + qualitative.Plotly
    return {
        failure_type: colors[index % len(colors)]
        for index, failure_type in enumerate(failure_types)
    }


def _rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _style_figure(
    figure: object,
    title: str,
    *,
    metadata: Mapping[str, str],
    x_title: str | None = None,
    y_title: str | None = None,
) -> None:
    subtitle = "<br>".join(
        f"<b>{key}:</b> {value}" for key, value in metadata.items()
    )
    figure.update_layout(
        title={
            "text": (
                f"<b>{title}</b><br>"
                f"<span style='font-size:12px;color:#667085'>{subtitle}</span>"
            ),
            "x": 0.0,
            "xanchor": "left",
            "xref": "paper",
            "y": 0.90,
            "yanchor": "top",
        },
        template="plotly_white",
        margin={"l": 70, "r": 30, "t": 155, "b": 70},
        legend_title_text="",
        xaxis_title=x_title,
        yaxis_title=y_title,
    )
