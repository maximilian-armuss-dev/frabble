from __future__ import annotations

import html
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping

from src.domain.board import Board
from src.domain.models import Move
from src.evaluation.models import EvaluationCase
from src.formal.language import StrictlyLocalLanguage

from .board_figures import PROJECT_ROOT, plot_board_axis_pairs
from .run_figures import (
    TimedLLMResponse,
    _board_with_move_overlay,
    _check_class,
    _check_symbol,
    _display_value,
    _move_conflict_coords,
    _move_from_object,
    _move_markup,
    _move_tile_colors,
    _rack_markup,
    _redact_board_configuration,
    display_llm_response,
)

def resolve_evaluation_run(
    case_set: str | None,
    run_id: str,
    *,
    project_root: str | Path = PROJECT_ROOT,
) -> Path:
    evaluation_root = Path(project_root) / "outputs" / "evaluation"
    if case_set is not None:
        candidates = [evaluation_root / case_set / "runs" / run_id]
    else:
        candidates = list(evaluation_root.glob(f"*/runs/{run_id}"))
    existing = [path for path in candidates if path.is_dir()]
    if not existing:
        raise FileNotFoundError(f"Evaluation run not found: {run_id}")
    if len(existing) > 1:
        raise ValueError(
            f"Evaluation run ID is ambiguous across case sets: {run_id}"
        )
    return existing[0]


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
    run_path: str | Path | None = None,
    project_root: str | Path = PROJECT_ROOT,
) -> tuple[Path, dict[str, Any]]:
    if run_path is not None:
        if case_set is not None or run_id is not None:
            raise ValueError(
                "Set run_path on its own, without case_set or run_id."
            )
        run_dir = Path(run_path)
        if not run_dir.is_absolute():
            run_dir = Path(project_root) / run_dir
        if not run_dir.is_dir():
            raise FileNotFoundError(f"Evaluation run folder not found: {run_dir}")
        return run_dir, load_evaluation_aggregate(run_dir)
    if (case_set is None) == (run_id is None):
        raise ValueError("Set exactly one of case_set or run_id.")
    if run_id is not None:
        run_dir = resolve_evaluation_run(
            case_set,
            run_id,
            project_root=project_root,
        )
        return run_dir, load_evaluation_aggregate(run_dir)
    assert case_set is not None
    run_dir = latest_completed_evaluation_run(
        case_set,
        project_root=project_root,
    )
    return run_dir, load_evaluation_aggregate(run_dir)


def latest_completed_evaluation_run(
    case_set: str,
    *,
    project_root: str | Path = PROJECT_ROOT,
) -> Path:
    runs_dir = (
        Path(project_root)
        / "outputs"
        / "evaluation"
        / case_set
        / "runs"
    )
    completed = []
    for manifest_path in runs_dir.glob("*/run-manifest.json"):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("status") != "complete":
            continue
        completed.append(
            (
                str(manifest.get("completed_at") or ""),
                manifest_path.parent.name,
                manifest_path.parent,
            )
        )
    if not completed:
        raise FileNotFoundError(
            f"No completed evaluation run found under {runs_dir}"
        )
    return max(completed)[2]


def plot_pass_rate_heatmaps(aggregate: Mapping[str, Any]) -> tuple[object, ...]:
    import plotly.graph_objects as go

    figures = []
    for representation, effort, groups in _group_slices(aggregate):
        models = sorted({str(group["model"]) for group in groups})
        board_sizes = _ordered_board_sizes(groups)
        values = [
            [
                _group_value(groups, model, board_size, "pass_rate")
                for board_size in board_sizes
            ]
            for model in models
        ]
        rack_usage = [
            [
                _group_summary_stat(
                    groups,
                    model,
                    board_size,
                    family="quality",
                    metric="rack_usage_ratio",
                    statistic="mean",
                )
                for board_size in board_sizes
            ]
            for model in models
        ]
        labels = [
            [
                _pass_rate_label(value, rack_ratio)
                for value, rack_ratio in zip(
                    value_row,
                    rack_row,
                    strict=True,
                )
            ]
            for value_row, rack_row in zip(values, rack_usage, strict=True)
        ]
        figure = go.Figure(
            go.Heatmap(
                x=[str(size) for size in board_sizes],
                y=models,
                z=values,
                zmin=0,
                zmax=1,
                colorscale="RdYlGn",
                text=labels,
                texttemplate="%{text}",
                customdata=rack_usage,
                colorbar={"title": "pass rate"},
                hovertemplate=(
                    "model=%{y}<br>board size=%{x}<br>pass=%{z:.1%}"
                    "<br>mean rack usage=%{customdata:.1%}<extra></extra>"
                ),
            )
        )
        _style_figure(
            figure,
            "Pass rate by model and board size",
            metadata=_plot_metadata(representation, effort, groups),
            x_title="board size",
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
                int(group["board_size"]),
                str(group["model"]),
            ),
        )
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
        for group in ordered:
            failures = sorted(
                group["primary_failures"].items(),
                key=lambda item: (-int(item[1]), str(item[0])),
            )
            for failure_type, count in failures:
                figure.add_bar(
                    name=failure_type,
                    x=[
                        [str(group["board_size"])],
                        [str(group["model"])],
                    ],
                    y=[_rate(int(count), int(group["failed"]))],
                    customdata=[
                        [
                            str(group["board_size"]),
                            str(group["model"]),
                            int(count),
                        ]
                    ],
                    marker_color=palette[failure_type],
                    legendgroup=failure_type,
                    showlegend=failure_type not in shown_in_legend,
                    hovertemplate=(
                        "board size=%{customdata[0]}<br>"
                        "model=%{customdata[1]}<br>"
                        + failure_type
                        + ": %{customdata[2]} "
                        "(%{y:.1%} of failures)<extra></extra>"
                    ),
                )
                shown_in_legend.add(failure_type)
        figure.update_layout(barmode="stack")
        _style_figure(
            figure,
            "Primary failure composition",
            metadata=_plot_metadata(representation, effort, groups),
            x_title="board size and model",
            y_title="share of failed attempts",
        )
        figure.update_layout(legend={"traceorder": "reversed"})
        figure.update_xaxes(type="multicategory")
        figure.update_yaxes(tickformat=".0%", range=[0, 1])
        figures.append(figure)
    return tuple(figures)


def plot_grammar_pass_rates(
    aggregate: Mapping[str, Any],
) -> tuple[object, ...]:
    import plotly.graph_objects as go

    figures = []
    for representation, effort, groups in _group_slices(aggregate):
        for board_size in _ordered_board_sizes(groups):
            board_size_groups = [
                group for group in groups if int(group["board_size"]) == board_size
            ]
            grammar_ids = sorted(
                {
                    _grammar_id(grammar)
                    for group in board_size_groups
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
                board_size_groups,
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
                    board_size=board_size,
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
        board_sizes = [str(group["board_size"]) for group in ordered]
        models = [str(group["model"]) for group in ordered]
        categories = [board_sizes, models]
        hover_data = [
            [str(group["board_size"]), str(group["model"])]
            for group in ordered
        ]
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
                "x": categories,
                "y": values,
                "customdata": hover_data,
                "hovertemplate": (
                    "board size=%{customdata[0]}<br>"
                    "model=%{customdata[1]}<br>"
                    + name
                    + ": %{y:,.0f}<extra></extra>"
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
            x_title="board size and model",
            y_title="average tokens",
        )
        figure.update_xaxes(type="multicategory")
        figures.append(figure)
    return tuple(figures)


QUALITY_METRICS: tuple[tuple[str, str, str], ...] = (
    ("main_word_length", "Average main word length", "main word length"),
    ("overlap_count", "Average overlap count", "overlap count"),
    ("letter_score_total", "Average letter score", "letter score"),
)


def plot_quality_score_bars(aggregate: Mapping[str, Any]) -> tuple[object, ...]:
    """Compare average word length, overlap count, and letter score (passing attempts)."""
    import plotly.graph_objects as go

    figures = []
    for representation, effort, groups in _group_slices(aggregate):
        ordered = _ordered_groups(groups)
        categories = [
            [str(group["board_size"]) for group in ordered],
            [str(group["model"]) for group in ordered],
        ]
        hover_data = [
            [str(group["board_size"]), str(group["model"])] for group in ordered
        ]
        for metric, title, hover_label in QUALITY_METRICS:
            values = [_quality_mean(group, metric) for group in ordered]
            figure = go.Figure(
                go.Bar(
                    x=categories,
                    y=values,
                    customdata=hover_data,
                    marker_color="#2563eb",
                    text=[
                        "" if value is None else f"{value:.1f}"
                        for value in values
                    ],
                    textposition="outside",
                    hovertemplate=(
                        "board size=%{customdata[0]}<br>"
                        "model=%{customdata[1]}<br>"
                        f"{hover_label}: %{{y:.2f}}<extra></extra>"
                    ),
                )
            )
            _style_figure(
                figure,
                title,
                metadata=_plot_metadata(representation, effort, groups),
                x_title="board size and model",
                y_title=title.removeprefix("Average ").title(),
            )
            figure.update_xaxes(type="multicategory")
            figures.append(figure)
    return tuple(figures)


def _quality_mean(group: Mapping[str, Any], metric: str) -> float | None:
    value = group.get("quality", {}).get(metric, {}).get("mean")
    return float(value) if value is not None else None


def plot_latency_tables(
    aggregate: Mapping[str, Any],
) -> tuple[object, ...]:
    import plotly.graph_objects as go

    figures = []
    for representation, effort, groups in _group_slices(aggregate):
        board_sizes = _ordered_board_sizes(groups)
        models = sorted({str(group["model"]) for group in groups})
        runtime_columns = [
            [
                _format_seconds(
                    _group_summary_mean(
                        groups,
                        model,
                        board_size,
                        family="timing",
                        metric="request_elapsed_seconds",
                    )
                )
                for model in models
            ]
            for board_size in board_sizes
        ]
        figure = go.Figure(
            go.Table(
                header={
                    "values": ["Model", *[str(size) for size in board_sizes]],
                    "align": ["left", *(["right"] * len(board_sizes))],
                    "fill_color": "#e8eef7",
                    "font": {"color": "#172033", "size": 13},
                    "height": 30,
                },
                cells={
                    "values": [
                        models,
                        *runtime_columns,
                    ],
                    "align": ["left", *(["right"] * len(board_sizes))],
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


def _ordered_board_sizes(groups: list[Mapping[str, Any]]) -> list[int]:
    return sorted(
        {int(group["board_size"]) for group in groups},
    )


def _ordered_groups(
    groups: list[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    return sorted(
        groups,
        key=lambda group: (
            int(group["board_size"]),
            str(group["model"]),
        ),
    )


def _group_value(
    groups: list[Mapping[str, Any]],
    model: str,
    board_size: int,
    field: str,
) -> Any:
    for group in groups:
        if group["model"] == model and int(group["board_size"]) == board_size:
            return group.get(field)
    return None


def _group_summary_mean(
    groups: list[Mapping[str, Any]],
    model: str,
    board_size: int,
    *,
    family: str,
    metric: str,
) -> float | None:
    return _group_summary_stat(
        groups,
        model,
        board_size,
        family=family,
        metric=metric,
        statistic="mean",
    )


def _group_summary_stat(
    groups: list[Mapping[str, Any]],
    model: str,
    board_size: int,
    *,
    family: str,
    metric: str,
    statistic: str,
) -> float | None:
    for group in groups:
        if group["model"] == model and int(group["board_size"]) == board_size:
            value = group.get(family, {}).get(metric, {}).get(statistic)
            return float(value) if value is not None else None
    return None


def _pass_rate_label(
    pass_rate: float | None,
    rack_usage_ratio: float | None,
) -> str:
    if pass_rate is None:
        return ""
    if rack_usage_ratio is None:
        return f"{pass_rate:.1%}"
    return f"{pass_rate:.1%}<br>{rack_usage_ratio:.1%} rack"


def _grammar_id(grammar: Mapping[str, Any]) -> str:
    return f"r{int(grammar['sampling_round']):02d}"


def _grammar_value(
    group: Mapping[str, Any],
    grammar_id: str,
) -> float | None:
    for grammar in group["grammars"]:
        if _grammar_id(grammar) == grammar_id:
            return grammar.get("pass_rate")
    return None


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
    board_size: int | None = None,
) -> Mapping[str, str]:
    board_sizes = (
        str(board_size)
        if board_size is not None
        else ", ".join(str(size) for size in _ordered_board_sizes(groups))
    )
    return {
        "Board size": board_sizes,
        "Representation": representation,
        "Reasoning": effort,
    }


def _format_seconds(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f} s"


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


# ---------------------------------------------------------------------------
# Individual attempt inspection
# ---------------------------------------------------------------------------

MoveSource = Literal["parsed", "ground_truth"]
_MAX_PLOTTABLE_DIMENSIONS = 4
_EVALUATION_DIR = PROJECT_ROOT / "outputs" / "evaluation"


@dataclass(frozen=True)
class EvaluationAttemptContext:
    attempt_path: Path
    attempt: dict[str, Any]
    board: Board
    rack: tuple[str, ...]
    parsed_move: Move | None
    ground_truth_move: Move
    language: StrictlyLocalLanguage


def resolve_attempt_path(
    job_id_or_path: str | Path,
    *,
    case_set: str | None = None,
) -> Path:
    """Resolve an attempt JSON path from a job_id, bare filename, or full path."""
    path = Path(job_id_or_path)
    for candidate in [path, path.with_suffix(".json")]:
        if candidate.exists():
            return candidate

    name = path.name if path.suffix == ".json" else path.name + ".json"
    search_roots = (
        [_EVALUATION_DIR / case_set]
        if case_set
        else [p for p in _EVALUATION_DIR.iterdir() if p.is_dir()]
    )
    for root in search_roots:
        for found in root.glob(f"runs/*/attempts/{name}"):
            return found

    raise FileNotFoundError(
        f"Attempt not found: {job_id_or_path!r}. "
        "Pass a full path, a job_id, or set case_set to narrow the search."
    )


def load_evaluation_attempt(
    job_id_or_path: str | Path,
    *,
    case_set: str | None = None,
) -> EvaluationAttemptContext:
    """Load an evaluation attempt JSON and reconstruct its board/language context."""
    attempt_path = resolve_attempt_path(job_id_or_path, case_set=case_set)
    attempt = json.loads(attempt_path.read_text(encoding="utf-8"))
    case_path = _resolve_case_file(str(attempt["case_file"]), attempt_path)
    evaluation_case = EvaluationCase.model_validate(
        json.loads(case_path.read_text(encoding="utf-8"))
    )
    board = evaluation_case.to_board()
    language = evaluation_case.to_language()
    return EvaluationAttemptContext(
        attempt_path=attempt_path,
        attempt=attempt,
        board=board,
        rack=evaluation_case.rack,
        parsed_move=_move_from_object(attempt.get("parsed_move")),
        ground_truth_move=_move_from_object(attempt["ground_truth_move"]),
        language=language,
    )


def display_attempt_prompt(context: EvaluationAttemptContext) -> object:
    """Render the stored system/user prompts and raw model response."""
    system_prompt = str(context.attempt.get("system_prompt", ""))
    user_prompt = str(context.attempt.get("user_prompt", ""))
    raw_response = str(context.attempt.get("raw_response", ""))
    user_prompt_display = _redact_board_configuration(
        user_prompt, board_cell_count=len(context.board.cells)
    )
    markup = f"""
### Attempt
`{context.attempt_path.name}`

### System prompt
```text
{system_prompt}
```

### User prompt (board configuration redacted)
```text
{user_prompt_display}
```

### Raw model response
```text
{raw_response}
```
"""
    try:
        from IPython.display import Markdown

        return Markdown(markup)
    except ImportError:
        return markup


def display_attempt_response(context: EvaluationAttemptContext) -> object:
    """Render the token/timing card, reusing the run_figures display."""
    attempt = context.attempt
    usage = dict(attempt.get("usage", {}))
    metadata = {
        **dict(attempt.get("provider_metadata", {})),
        "configured_model": attempt.get("model"),
        "reasoning_effort": attempt.get("reasoning_effort"),
        "backend": "litellm",
    }
    elapsed = attempt.get("llm_elapsed_seconds")
    response = TimedLLMResponse(
        raw_response=str(attempt.get("raw_response", "")),
        elapsed_seconds=float(elapsed) if elapsed is not None else 0.0,
        usage=usage,
        metadata=metadata,
    )
    return display_llm_response(response)


def display_attempt_summary(context: EvaluationAttemptContext) -> object:
    """Render a compact pass/fail card for an already-completed evaluation attempt."""
    attempt = context.attempt
    evaluation = dict(attempt.get("evaluation", {}))
    status_ok = bool(evaluation.get("overall"))
    status = "PASS" if status_ok else "FAIL"
    status_color = "#0f7b45" if status_ok else "#b42318"
    message = evaluation.get("message") or ""

    checks = [
        ("parse", evaluation.get("parse_ok")),
        ("sequence", evaluation.get("sequence_valid")),
        ("spatial", evaluation.get("spatial_valid")),
        ("overlap", evaluation.get("overlap_valid")),
        ("no word extension", evaluation.get("no_word_extension")),
        ("cross words", evaluation.get("cross_words_valid")),
        ("rack", evaluation.get("rack_valid")),
    ]
    check_rows = "\n".join(
        f"""
        <tr>
          <td style="text-align:left;padding:3px 12px 3px 0;">{html.escape(label)}</td>
          <td class="{_check_class(value)}"
              style="text-align:right;padding:3px 0 3px 12px;">{_check_symbol(value)}</td>
        </tr>
        """
        for label, value in checks
    )
    scores = [
        ("word length", evaluation.get("main_word_length")),
        ("overlap count", evaluation.get("overlap_count")),
        ("letter score", evaluation.get("letter_score_total")),
    ]
    score_rows = "\n".join(
        f"""
        <tr>
          <td style="text-align:left;padding:3px 12px 3px 0;">{html.escape(label)}</td>
          <td style="text-align:right;padding:3px 0 3px 12px;
                     font-weight:700;color:#111827;">{html.escape(_display_value(value))}</td>
        </tr>
        """
        for label, value in scores
    )
    move_markup = _move_markup(attempt.get("parsed_move"))
    needed: Counter[str] = Counter()
    if context.parsed_move is not None:
        needed = Counter(
            symbol
            for coord, symbol in zip(
                context.parsed_move.coords(),
                context.parsed_move.sequence,
                strict=True,
            )
            if context.board.get(coord) is None
        )
    rack_markup = _rack_markup(
        {"rack": context.rack, "rack_symbols_needed": dict(needed)}
    )

    board_size = attempt.get("board_size", "")
    model = attempt.get("model", "")
    lang_repr = attempt.get("language_representation", "")
    effort = attempt.get("reasoning_effort", "")
    rack_used = evaluation.get("rack_symbols_used", "n/a")
    rack_ratio = evaluation.get("rack_usage_ratio")
    rack_ratio_str = f"{rack_ratio:.0%}" if isinstance(rack_ratio, float) else "n/a"
    case_id = attempt.get("case_id", "")

    markup = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
                color:#1f2937;max-width:920px;border:1px solid #d0d7de;
                border-radius:8px;overflow:hidden;background:white;">
      <div style="display:flex;align-items:center;gap:12px;padding:12px 14px;
                  border-bottom:1px solid #d0d7de;background:#f6f8fa;">
        <span style="background:{status_color};color:white;font-weight:700;
                     border-radius:999px;padding:3px 10px;font-size:12px;">{status}</span>
        <span style="font-size:13px;color:#6b7280;">
          board size:&nbsp;<b>{html.escape(str(board_size))}</b>&ensp;·&ensp;
          model:&nbsp;<b>{html.escape(model)}</b>&ensp;·&ensp;
          repr:&nbsp;<b>{html.escape(lang_repr)}</b>&ensp;·&ensp;
          effort:&nbsp;<b>{html.escape(effort)}</b>
        </span>
      </div>
      <div style="display:grid;grid-template-columns:minmax(0,1fr) minmax(280px,0.8fr);
                  border-bottom:1px solid #e5e7eb;">
        <div style="padding:12px 14px;min-width:0;">
          <div style="font-size:12px;text-transform:uppercase;color:#6b7280;
                      font-weight:700;margin-bottom:8px;">model response</div>
          {move_markup}
          <div style="font-size:12px;text-transform:uppercase;color:#6b7280;
                      font-weight:700;margin:14px 0 8px;">
            rack &mdash; used {rack_used}/{len(context.rack)} ({rack_ratio_str})
          </div>
          {rack_markup}
          <div style="font-size:12px;text-transform:uppercase;color:#6b7280;
                      font-weight:700;margin:14px 0 6px;">message</div>
          <div style="color:#111827;white-space:pre-wrap;line-height:1.45;">
            <code>{html.escape(str(message))}</code>
          </div>
        </div>
        <div style="padding:12px 14px;border-left:1px solid #e5e7eb;background:#f9fafb;">
          <div style="font-size:12px;text-transform:uppercase;color:#6b7280;
                      font-weight:700;margin-bottom:6px;">failure classes</div>
          <table style="border-collapse:collapse;width:100%;font-size:14px;">
            <tbody>{check_rows}</tbody>
          </table>
          <div style="font-size:12px;text-transform:uppercase;color:#6b7280;
                      font-weight:700;margin:14px 0 6px;">scores</div>
          <table style="border-collapse:collapse;width:100%;font-size:14px;">
            <tbody>{score_rows}</tbody>
          </table>
        </div>
      </div>
      <div style="padding:10px 14px;background:#f9fafb;color:#6b7280;
                  font-size:12px;border-top:1px solid #e5e7eb;">
        {html.escape(case_id)}
      </div>
    </div>
    <style>
      .llm-check-ok {{ color:#0f7b45; font-weight:700; }}
      .llm-check-bad {{ color:#b42318; font-weight:700; }}
      .llm-check-na {{ color:#6b7280; font-weight:700; }}
    </style>
    """
    try:
        from IPython.display import HTML

        return HTML(markup)
    except ImportError:
        return {"evaluation": evaluation}


def plot_attempt_move(
    context: EvaluationAttemptContext,
    *,
    move_source: MoveSource = "parsed",
) -> tuple[object, ...]:
    """Plot the submitted or ground-truth move. Prints a note and returns () for >4D."""
    dims = context.board.dimensions
    if dims > _MAX_PLOTTABLE_DIMENSIONS:
        print(
            f"Cannot plot: dimensionality {dims} exceeds the {_MAX_PLOTTABLE_DIMENSIONS}D "
            "visualization limit."
        )
        return ()

    move = context.parsed_move if move_source == "parsed" else context.ground_truth_move
    reference = context.ground_truth_move

    if move is None:
        return plot_board_axis_pairs(
            context.board,
            move_axis=reference.axis,
            plane_coord=reference.start,
            title="No parsed LLM move",
        )

    board_with_overlay = _board_with_move_overlay(context.board, move)
    conflict_coords = _move_conflict_coords(context.board, move)
    title = f"{move_source.replace('_', ' ').title()} move"
    if conflict_coords:
        title += f" ({len(conflict_coords)} symbol conflict)"
    return plot_board_axis_pairs(
        board_with_overlay,
        move_axis=move.axis,
        plane_coord=move.start,
        tile_colors=_move_tile_colors(context.board, move),
        title=title,
    )


def _resolve_case_file(stored_path: str, attempt_path: Path) -> Path:
    path = Path(stored_path)
    if path.exists():
        return path
    for part_index, part in enumerate(path.parts):
        if part == "outputs":
            candidate = PROJECT_ROOT / Path(*path.parts[part_index:])
            if candidate.exists():
                return candidate
            break
    run_dir = attempt_path.parent.parent
    case_set_dir = run_dir.parent.parent
    candidate = case_set_dir / "cases" / path.name
    if candidate.exists():
        return candidate
    raise FileNotFoundError(
        f"Could not locate case file {stored_path!r}. "
        "The case set must be present locally."
    )
