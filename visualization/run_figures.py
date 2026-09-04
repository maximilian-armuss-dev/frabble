from __future__ import annotations

import json
import html
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Literal, Mapping, Sequence

from src.domain.board import Board
from src.domain.models import Move
from src.formal.grammar.serialization import load_grammar
from src.formal.language import StrictlyLocalLanguage
from src.formal.parsing import SubmittedMove, parse_submitted_move
from src.formal.validation import validate_move_detailed
from src.generator.reconstruction import board_before_transition
from src.generator.config import resolve_scenario_grammar_path
from src.generator.scenario_io import load_scenario_run
from src.llm.client import call_llm_detailed
from src.llm.env import ENV, MODEL_CONFIGS_PATH
from src.llm.evaluation import evaluate_granular
from src.llm.prompting import PROMPTS_DIR, build_prompt
from src.llm.representers import RepresenterConfig

from .board_figures import (
    CONFLICTING_MOVE_TILE,
    MATCHING_MOVE_TILE,
    NEW_MOVE_TILE,
    PROJECT_ROOT,
    plot_board_axis_pairs,
    resolve_scenario_path,
)


MoveSource = Literal["parsed", "ground_truth"]


@dataclass(frozen=True)
class LLMRunContext:
    run_path: Path
    run_log: Mapping[str, object]
    scenario_path: Path
    board: Board
    rack: tuple[str, ...]
    parsed_move: Move | None
    ground_truth_move: Move


@dataclass(frozen=True)
class PreparedLLMTransition:
    scenario_path: Path
    transition_index: int
    model_name: str
    reasoning_effort: str | None
    board: Board
    rack: tuple[str, ...]
    ground_truth_move: Move
    language: StrictlyLocalLanguage
    representers: RepresenterConfig
    system_prompt: str
    user_prompt: str


@dataclass(frozen=True)
class TimedLLMResponse:
    raw_response: str
    elapsed_seconds: float
    usage: Mapping[str, object]
    metadata: Mapping[str, object]


def load_llm_run_context(
    run_path: str | Path,
    *,
    project_root: str | Path | None = None,
) -> LLMRunContext:
    path = resolve_run_path(run_path)
    run_log = json.loads(path.read_text(encoding="utf-8"))
    root = Path(project_root) if project_root is not None else PROJECT_ROOT
    scenario_path = _resolve_path(str(run_log["scenario_file"]), root, path.parent)
    scenario_run = load_scenario_run(scenario_path)
    transition_index = int(run_log["transition_index"])
    board = board_before_transition(scenario_run, transition_index)
    transition = scenario_run.transitions[transition_index]
    return LLMRunContext(
        run_path=path,
        run_log=run_log,
        scenario_path=scenario_path,
        board=board,
        rack=transition.rack,
        parsed_move=_move_from_object(run_log.get("parsed_move")),
        ground_truth_move=_move_from_object(run_log["ground_truth_move"]),
    )


def resolve_run_path(name_or_path: str | Path) -> Path:
    """Resolve a run-log path or bare run name under outputs/llm-runs/."""
    path = Path(name_or_path)
    candidates = [path]
    if path.suffix != ".json":
        candidates.append(path.with_suffix(".json"))
    if not path.is_absolute() and path.parent == Path("."):
        candidates.append(PROJECT_ROOT / "outputs" / "llm-runs" / path)
        if path.suffix != ".json":
            candidates.append(
                PROJECT_ROOT / "outputs" / "llm-runs" / path.with_suffix(".json")
            )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Run log not found: {name_or_path}")


def run_llm_transition(
    *,
    scenario_name: str | Path,
    transition_index: int,
    model_name: str,
    reasoning_effort: str | None,
    output_dir: str | Path | None = None,
    representers: RepresenterConfig | None = None,
) -> LLMRunContext:
    """Run one scenario transition through an LLM and return its inspection context."""
    prepared = prepare_llm_transition(
        scenario_name=scenario_name,
        transition_index=transition_index,
        model_name=model_name,
        reasoning_effort=reasoning_effort,
        representers=representers,
    )
    response = call_prepared_llm_transition(prepared)
    return finalize_llm_transition(prepared, response, output_dir=output_dir)


def prepare_llm_transition(
    *,
    scenario_name: str | Path,
    transition_index: int,
    model_name: str,
    reasoning_effort: str | None,
    representers: RepresenterConfig | None = None,
) -> PreparedLLMTransition:
    """Load and render a transition without making an LLM request."""
    scenario_path = resolve_scenario_path(scenario_name)
    scenario_run = load_scenario_run(scenario_path)
    if transition_index < 0 or transition_index >= len(scenario_run.transitions):
        raise IndexError(
            f"transition_index {transition_index} outside 0..{len(scenario_run.transitions) - 1}"
        )

    language, _, _ = load_grammar(_grammar_path(scenario_path))
    board = board_before_transition(scenario_run, transition_index)
    transition = scenario_run.transitions[transition_index]
    active_representers = representers or RepresenterConfig()
    system_prompt, user_prompt = build_prompt(
        board, transition, language, active_representers
    )
    return PreparedLLMTransition(
        scenario_path=scenario_path,
        transition_index=transition_index,
        model_name=model_name,
        reasoning_effort=reasoning_effort,
        board=board,
        rack=transition.rack,
        ground_truth_move=transition.move,
        language=language,
        representers=active_representers,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
    )


def call_prepared_llm_transition(
    prepared: PreparedLLMTransition,
) -> TimedLLMResponse:
    """Call the LLM and measure only the blocking client request."""
    started_at = perf_counter()
    result = call_llm_detailed(
        prepared.system_prompt,
        prepared.user_prompt,
        prepared.model_name,
        reasoning_effort=prepared.reasoning_effort,
    )
    elapsed = perf_counter() - started_at
    model_config = ENV.get_model_config(prepared.model_name)
    metadata = {
        **result.metadata,
        "configured_model": prepared.model_name,
        "backend": result.metadata.get("backend", model_config.backend),
        "reasoning_effort": prepared.reasoning_effort,
    }
    return TimedLLMResponse(
        raw_response=result.content,
        elapsed_seconds=elapsed,
        usage=result.usage,
        metadata=metadata,
    )


def finalize_llm_transition(
    prepared: PreparedLLMTransition,
    response: TimedLLMResponse,
    *,
    output_dir: str | Path | None = None,
) -> LLMRunContext:
    """Parse, evaluate, and persist a completed LLM response."""
    submitted: SubmittedMove | None = None
    parse_error: str | None = None
    try:
        submitted = parse_submitted_move(response.raw_response)
    except Exception as exc:
        parse_error = str(exc)

    evaluation = evaluate_granular(
        prepared.board,
        prepared.language,
        prepared.rack,
        submitted,
        parse_error,
    )
    timestamp = datetime.now()
    model_tag = prepared.model_name.replace("/", "-").replace(":", "-")
    run_dir = (
        Path(output_dir)
        if output_dir is not None
        else PROJECT_ROOT / "outputs" / "llm-runs"
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    output_path = run_dir / (
        f"{prepared.scenario_path.stem}_t{prepared.transition_index}_{model_tag}_"
        f"{timestamp.strftime('%Y%m%dT%H%M%S')}.json"
    )
    model_config = ENV.get_model_config(prepared.model_name)
    run_log = {
        "scenario_file": str(prepared.scenario_path),
        "transition_index": prepared.transition_index,
        "model": prepared.model_name,
        "model_config": {
            "model": model_config.request_model,
            "configured_model": model_config.model,
            "reasoning_effort": prepared.reasoning_effort,
            "max_completion_tokens": model_config.max_completion_tokens,
            "structured_output": True,
            "timeout_seconds": model_config.timeout_seconds,
        },
        "timestamp": timestamp.isoformat(),
        "llm_elapsed_seconds": response.elapsed_seconds,
        "llm_usage": dict(response.usage),
        "llm_response_metadata": dict(response.metadata),
        "representers": {
            "language": prepared.representers.language.name,
            "board": prepared.representers.board.name,
            "rack": prepared.representers.rack.name,
        },
        "system_prompt": prepared.system_prompt,
        "user_prompt": prepared.user_prompt,
        "raw_response": response.raw_response,
        "parsed_move": submitted.model_dump() if submitted is not None else None,
        "evaluation": evaluation.to_json(),
        "ground_truth_move": prepared.ground_truth_move.to_json(),
    }
    output_path.write_text(
        json.dumps(run_log, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return load_llm_run_context(output_path)


def llm_call_diagnostics(response: TimedLLMResponse) -> dict[str, object]:
    completion_details = dict(
        response.usage.get("completion_tokens_details") or {}
    )
    provider_ms = response.metadata.get("provider_processing_ms")
    provider_seconds = None
    if provider_ms is not None:
        try:
            provider_seconds = float(provider_ms) / 1000
        except (TypeError, ValueError):
            provider_seconds = None
    return {
        "wall_seconds": response.elapsed_seconds,
        "backend": response.metadata.get("backend"),
        "provider_processing_seconds": provider_seconds,
        "prompt_tokens": response.usage.get("prompt_tokens"),
        "completion_tokens": response.usage.get("completion_tokens"),
        "reasoning_tokens": completion_details.get("reasoning_tokens"),
        "visible_output_tokens": completion_details.get("text_tokens"),
        "model": response.metadata.get("model"),
        "configured_model": response.metadata.get("configured_model"),
        "reasoning_effort": response.metadata.get("reasoning_effort"),
        "finish_reason": response.metadata.get("finish_reason"),
        "request_id": response.metadata.get("request_id"),
        "incomplete": response.metadata.get("incomplete", False),
        "structured_output_error": response.metadata.get("structured_output_error"),
    }


def display_llm_response(response: TimedLLMResponse) -> object:
    """Render LLM configuration and request metrics in a notebook."""
    diagnostics = llm_call_diagnostics(response)
    model = diagnostics.get("configured_model") or diagnostics.get("model")
    elapsed = diagnostics.get("wall_seconds")
    elapsed_text = "n/a" if elapsed is None else f"{float(elapsed):.1f}s"
    rows = (
        ("model", model),
        ("backend", diagnostics.get("backend")),
        ("reasoning", diagnostics.get("reasoning_effort")),
        ("LLM time", elapsed_text),
        ("prompt tokens", diagnostics.get("prompt_tokens")),
        ("reasoning tokens", diagnostics.get("reasoning_tokens")),
        ("completion tokens", diagnostics.get("completion_tokens")),
    )
    metric_rows = "\n".join(
        f"""
        <li style="display:grid;grid-template-columns:150px minmax(0,1fr);
                   gap:16px;padding:8px 0;
                   {'border-top:1px solid #e5e7eb;' if index else ''}">
          <span style="font-size:12px;text-transform:uppercase;color:#6b7280;
                       font-weight:700;">{html.escape(label)}</span>
          <span style="font-weight:600;color:#111827;">
            {html.escape(_display_value(value))}
          </span>
        </li>
        """
        for index, (label, value) in enumerate(rows)
    )
    if (
        diagnostics.get("finish_reason") == "length"
        and diagnostics.get("reasoning_tokens")
        == diagnostics.get("completion_tokens")
    ):
        note = (
            '<div style="padding:10px 14px;background:#fff7ed;color:#9a3412;'
            'border-top:1px solid #fed7aa;font-size:13px;">'
            "No visible model output: the completion budget was consumed by "
            "reasoning tokens.</div>"
        )
    else:
        note = ""
    markup = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
                color:#1f2937;max-width:920px;border:1px solid #d0d7de;
                border-radius:8px;overflow:hidden;background:white;
                padding:6px 14px;">
      <ul style="list-style:none;margin:0;padding:0;">{metric_rows}</ul>
      {note}
    </div>
    """
    try:
        from IPython.display import HTML

        return HTML(markup)
    except ImportError:
        return {
            "diagnostics": diagnostics,
        }


def display_llm_prompt(prepared: PreparedLLMTransition) -> object:
    """Render prompt sources and fully expanded prompts in a notebook."""
    system_path = PROMPTS_DIR / "system.txt"
    user_path = PROMPTS_DIR / "user.txt"
    system_link = _notebook_relative_link(system_path)
    user_link = _notebook_relative_link(user_path)
    config_link = _notebook_relative_link(MODEL_CONFIGS_PATH)
    scenario_link = _notebook_relative_link(prepared.scenario_path)
    displayed_user_prompt = _redact_board_sequences(
        prepared.user_prompt,
        board_cell_count=len(prepared.board.cells),
        board_sequence_count=len(prepared.board.segments),
    )
    markup = f"""
### Prompt sources

- System template: [`prompts/system.txt`]({system_link})
- User template: [`prompts/user.txt`]({user_link})
- Model config: [`config/model_configs.yaml`]({config_link})
- Scenario: [`{prepared.scenario_path.name}`]({scenario_link})
- Backend: `litellm`

### System prompt

```text
{prepared.system_prompt}
```

### User prompt

```text
{displayed_user_prompt}
```
"""
    try:
        from IPython.display import Markdown

        return Markdown(markup)
    except ImportError:
        return markup


def _notebook_relative_link(path: Path) -> str:
    try:
        relative = path.resolve().relative_to(PROJECT_ROOT.resolve())
    except ValueError:
        return path.as_uri()
    return f"../{relative.as_posix()}"


def _redact_board_sequences(
    prompt: str,
    *,
    board_cell_count: int,
    board_sequence_count: int | None,
) -> str:
    end_marker = "\n\nRack:\n"
    start_marker = next(
        (
            marker
            for marker in ("Existing sequences:\n", "Board configuration:\n")
            if marker in prompt
        ),
        "",
    )
    start = prompt.find(start_marker) if start_marker else -1
    end = prompt.find(end_marker, start + len(start_marker)) if start >= 0 else -1
    if start < 0 or end < 0:
        return prompt
    sequence_summary = (
        f"{board_sequence_count} sequences, "
        if board_sequence_count is not None
        else ""
    )
    replacement = (
        f"{start_marker}[omitted from notebook display: "
        f"{sequence_summary}{board_cell_count} occupied cells]"
    )
    return prompt[:start] + replacement + prompt[end:]


def _redact_board_configuration(prompt: str, *, board_cell_count: int) -> str:
    """Compatibility wrapper for notebooks that imported the old helper."""
    return _redact_board_sequences(
        prompt,
        board_cell_count=board_cell_count,
        board_sequence_count=None,
    )


def llm_run_summary(context: LLMRunContext) -> dict[str, object]:
    evaluation = dict(context.run_log.get("evaluation", {}))
    model_config = dict(context.run_log.get("model_config", {}))
    parsed_move = context.parsed_move
    validation = None
    rack_valid = evaluation.get("rack_valid")
    missing_rack_symbols = dict(evaluation.get("missing_rack_symbols") or {})
    needed = Counter()
    if parsed_move is not None:
        grammar_path = _grammar_path(context.scenario_path)
        language, _, _ = load_grammar(grammar_path)
        validation = validate_move_detailed(
            context.board, language, context.rack, parsed_move
        )
        needed = Counter(
            symbol
            for coord, symbol in zip(
                parsed_move.coords(),
                parsed_move.sequence,
                strict=True,
            )
            if context.board.get(coord) is None
        )
        missing = needed - Counter(context.rack)
        rack_valid = not missing
        missing_rack_symbols = dict(missing)
    spatial_valid = evaluation.get("spatial_valid")
    cross_words_valid = evaluation.get("cross_words_valid")
    if spatial_valid is False:
        cross_words_valid = None
    return {
        "run_file": str(context.run_path),
        "scenario_file": str(context.scenario_path),
        "transition_index": context.run_log["transition_index"],
        "model": context.run_log["model"],
        "backend": model_config.get("backend")
        or dict(context.run_log.get("llm_response_metadata", {})).get("backend"),
        "reasoning_depth": model_config.get("reasoning_depth")
        or model_config.get("reasoning_effort"),
        "llm_elapsed_seconds": context.run_log.get("llm_elapsed_seconds"),
        "overall": evaluation.get("overall"),
        "failure_type": evaluation.get("failure_type"),
        "message": evaluation.get("message"),
        "sequence_valid": evaluation.get("sequence_valid"),
        "spatial_valid": spatial_valid,
        "overlap_valid": evaluation.get("overlap_valid"),
        "no_word_extension": evaluation.get("no_word_extension"),
        "cross_words_valid": cross_words_valid,
        "rack_valid": rack_valid,
        "rack": context.rack,
        "rack_symbols_needed": dict(needed),
        "missing_rack_symbols": missing_rack_symbols,
        "rack_symbols_used": evaluation.get("rack_symbols_used"),
        "rack_size": len(context.rack),
        "main_word_length": evaluation.get("main_word_length"),
        "overlap_count": evaluation.get("overlap_count"),
        "letter_score_total": evaluation.get("letter_score_total"),
        "parsed_move": parsed_move.to_json() if parsed_move is not None else None,
        "ground_truth_move": context.ground_truth_move.to_json(),
        "revalidated_failure_type": None
        if validation is None
        else validation.failure_type,
    }


def display_llm_run_summary(context: LLMRunContext) -> object:
    """Render a compact notebook-friendly summary for an LLM run."""
    summary = llm_run_summary(context)
    status_ok = bool(summary["overall"])
    status = "PASS" if status_ok else "FAIL"
    status_color = "#0f7b45" if status_ok else "#b42318"
    message = summary["message"] or ""
    checks = [
        ("sequence", summary["sequence_valid"]),
        ("spatial", summary["spatial_valid"]),
        ("overlap", summary["overlap_valid"]),
        ("no word extension", summary["no_word_extension"]),
        ("cross words", summary["cross_words_valid"]),
        ("rack", summary["rack_valid"]),
    ]
    check_rows = "\n".join(
        f"""
        <tr>
          <td style="text-align:left;padding:3px 12px 3px 0;">
            {html.escape(label)}
          </td>
          <td class="{_check_class(value)}"
              style="text-align:right;padding:3px 0 3px 12px;">
            {_check_symbol(value)}
          </td>
        </tr>
        """
        for label, value in checks
    )
    scores = [
        ("word length", summary["main_word_length"]),
        ("overlap count", summary["overlap_count"]),
        ("letter score", summary["letter_score_total"]),
    ]
    score_rows = "\n".join(
        f"""
        <tr>
          <td style="text-align:left;padding:3px 12px 3px 0;">
            {html.escape(label)}
          </td>
          <td style="text-align:right;padding:3px 0 3px 12px;
                     font-weight:700;color:#111827;">
            {html.escape(_display_value(value))}
          </td>
        </tr>
        """
        for label, value in scores
    )
    token_rows = _token_rows(context.run_log.get("llm_usage"))
    token_table = ""
    if token_rows:
        token_table = f"""
          <div style="font-size:12px;text-transform:uppercase;color:#6b7280;
                      font-weight:700;margin:14px 0 6px;">tokens</div>
          <table style="border-collapse:collapse;width:100%;font-size:14px;">
            <tbody>{token_rows}</tbody>
          </table>
        """
    move_markup = _move_markup(summary.get("parsed_move"))
    rack_markup = _rack_markup(summary)
    markup = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
                color:#1f2937;max-width:920px;border:1px solid #d0d7de;
                border-radius:8px;overflow:hidden;background:white;">
      <div style="display:flex;align-items:center;gap:12px;padding:12px 14px;
                  border-bottom:1px solid #d0d7de;background:#f6f8fa;">
        <span style="background:{status_color};color:white;font-weight:700;
                     border-radius:999px;padding:3px 10px;font-size:12px;">
          {status}
        </span>
      </div>
      <div style="display:grid;grid-template-columns:minmax(0,1fr) minmax(280px,0.8fr);
                  border-bottom:1px solid #e5e7eb;">
        <div style="padding:12px 14px;min-width:0;">
          <div style="font-size:12px;text-transform:uppercase;color:#6b7280;
                      font-weight:700;margin-bottom:8px;">model response</div>
          {move_markup}
          <div style="font-size:12px;text-transform:uppercase;color:#6b7280;
                      font-weight:700;margin:14px 0 8px;">rack</div>
          {rack_markup}
          <div style="font-size:12px;text-transform:uppercase;color:#6b7280;
                      font-weight:700;margin:14px 0 6px;">message</div>
          <div style="color:#111827;white-space:pre-wrap;line-height:1.45;">
            <code>{html.escape(str(message))}</code>
          </div>
        </div>
        <div style="padding:12px 14px;border-left:1px solid #e5e7eb;
                    background:#f9fafb;">
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
          {token_table}
        </div>
      </div>
      <div style="padding:10px 14px;background:#f9fafb;color:#6b7280;
                  font-size:12px;border-top:1px solid #e5e7eb;">
        {html.escape(Path(str(summary["run_file"])).name)}
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
        return summary


def _token_rows(usage_value: object) -> str:
    if not isinstance(usage_value, Mapping):
        return ""
    completion_details = usage_value.get("completion_tokens_details")
    if not isinstance(completion_details, Mapping):
        completion_details = {}
    reasoning_tokens = completion_details.get("reasoning_tokens")
    completion_tokens = usage_value.get("completion_tokens")
    visible_tokens = completion_details.get("text_tokens")
    if visible_tokens is None:
        visible_tokens = _token_difference(completion_tokens, reasoning_tokens)
    rows = (
        ("prompt", usage_value.get("prompt_tokens")),
        ("reasoning", reasoning_tokens),
        ("visible output", visible_tokens),
        ("completion", completion_tokens),
        ("total", usage_value.get("total_tokens")),
    )
    return "\n".join(
        f"""
        <tr>
          <td style="text-align:left;padding:3px 12px 3px 0;">
            {html.escape(label)}
          </td>
          <td style="text-align:right;padding:3px 0 3px 12px;
                     font-weight:700;color:#111827;">
            {html.escape(_display_value(value))}
          </td>
        </tr>
        """
        for label, value in rows
        if value is not None
    )


def _token_difference(total: object, part: object) -> int | None:
    try:
        return max(int(total) - int(part), 0)
    except (TypeError, ValueError):
        return None


def plot_llm_run_move(
    context: LLMRunContext,
    *,
    move_source: MoveSource = "parsed",
) -> tuple[object, ...]:
    move = _select_move(context, move_source)
    if move is None:
        reference_move = context.ground_truth_move
        return plot_board_axis_pairs(
            context.board,
            move_axis=reference_move.axis,
            plane_coord=reference_move.start,
            title="No parsed LLM move",
        )
    board = _board_with_move_overlay(context.board, move)
    conflict_coords = _move_conflict_coords(context.board, move)
    title = f"{move_source.replace('_', ' ').title()} move"
    if conflict_coords:
        title += f" ({len(conflict_coords)} symbol conflict)"
    return plot_board_axis_pairs(
        board,
        move_axis=move.axis,
        plane_coord=move.start,
        tile_colors=_move_tile_colors(context.board, move),
        title=title,
    )


def _select_move(context: LLMRunContext, move_source: MoveSource) -> Move | None:
    if move_source == "parsed":
        return context.parsed_move
    if move_source == "ground_truth":
        return context.ground_truth_move
    raise ValueError(f"Unknown move source: {move_source}")


def _board_with_move_overlay(board: Board, move: Move) -> Board:
    cells = dict(board.cells)
    has_conflict = False
    for coord, symbol in zip(move.coords(), move.sequence, strict=True):
        current = cells.get(coord)
        if current is None:
            cells[coord] = symbol
        elif current != symbol:
            cells[coord] = f"{current}/{symbol}"
            has_conflict = True
    return Board(
        dimensions=board.dimensions,
        cells=cells,
        segments=() if has_conflict else board.segments,
    )


def _move_tile_colors(board: Board, move: Move) -> dict[tuple[int, ...], str]:
    colors = {}
    for coord, symbol in zip(move.coords(), move.sequence, strict=True):
        current = board.get(coord)
        if current is None:
            colors[coord] = NEW_MOVE_TILE
        elif current == symbol:
            colors[coord] = MATCHING_MOVE_TILE
        else:
            colors[coord] = CONFLICTING_MOVE_TILE
    return colors


def _move_conflict_coords(
    board: Board,
    move: Move,
) -> tuple[tuple[int, ...], ...]:
    return tuple(
        coord
        for coord, symbol in zip(move.coords(), move.sequence, strict=True)
        if board.get(coord) is not None and board.get(coord) != symbol
    )


def _move_markup(move_data: object) -> str:
    if not isinstance(move_data, Mapping):
        return '<em style="color:#6b7280;">No parsed move available.</em>'
    fields = (
        ("start", json.dumps(move_data.get("start"))),
        ("axis", str(move_data.get("axis"))),
        ("sequence", json.dumps(move_data.get("sequence"))),
    )
    items = "\n".join(
        f"""
        <li style="display:grid;grid-template-columns:90px minmax(0,1fr);
                   gap:12px;padding:8px 0;border-top:1px solid #e5e7eb;">
          <span style="font-size:12px;text-transform:uppercase;color:#6b7280;
                       font-weight:700;">{html.escape(label)}</span>
          <code style="color:#111827;font-weight:600;overflow-wrap:anywhere;
                       background:#f3f4f6;border-radius:4px;padding:4px 8px;
                       display:inline-block;">
            {html.escape(value)}
          </code>
        </li>
        """
        for label, value in fields
    )
    return f'<ul style="list-style:none;margin:0;padding:0;">{items}</ul>'


def _rack_markup(summary: Mapping[str, object]) -> str:
    rack = tuple(str(symbol) for symbol in summary.get("rack") or ())
    remaining = Counter(
        {
            str(symbol): int(count)
            for symbol, count in dict(
                summary.get("rack_symbols_needed") or {}
            ).items()
        }
    )
    chips = []
    for symbol in rack:
        used = remaining[symbol] > 0
        if used:
            remaining[symbol] -= 1
        background = "#dcfce7" if used else "#f3f4f6"
        border = "#86efac" if used else "#d1d5db"
        color = "#166534" if used else "#4b5563"
        chips.append(
            f"""
            <span style="display:inline-flex;align-items:center;justify-content:center;
                         min-width:22px;height:22px;padding:0 5px;border-radius:5px;
                         border:1px solid {border};background:{background};
                         color:{color};font-size:12px;
                         font-weight:700;">{html.escape(symbol)}</span>
            """
        )
    if not chips:
        return '<em style="color:#6b7280;">Rack unavailable.</em>'
    return (
        '<div style="display:flex;flex-wrap:wrap;gap:5px;">'
        + "".join(chips)
        + "</div>"
    )


def _display_value(value: object) -> str:
    return "n/a" if value is None else str(value)


def _check_symbol(value: object) -> str:
    if value is True:
        return "OK"
    if value is False:
        return "FAIL"
    return "n/a"


def _check_class(value: object) -> str:
    if value is True:
        return "llm-check-ok"
    if value is False:
        return "llm-check-bad"
    return "llm-check-na"


def _move_from_object(data: object) -> Move | None:
    if data is None:
        return None
    if not isinstance(data, dict):
        raise ValueError("move must be an object.")
    return Move(
        start=tuple(int(value) for value in data["start"]),
        axis=int(data["axis"]),
        sequence=tuple(str(symbol) for symbol in data["sequence"]),
    )


def _grammar_path(scenario_path: Path) -> Path:
    scenario_run = load_scenario_run(scenario_path)
    return resolve_scenario_grammar_path(
        scenario_run.config,
        scenario_path=scenario_path,
    )


def _resolve_path(raw_path: str, project_root: Path, fallback_dir: Path) -> Path:
    path = Path(raw_path)
    if path.is_absolute() and path.exists():
        return path
    root_path = project_root / path
    if root_path.exists():
        return root_path
    if (
        (not path.is_absolute() and path.parent == Path("outputs"))
        or (path.is_absolute() and path.parent.name == "outputs")
    ):
        scenario_path = project_root / "outputs" / "scenarios" / path.name
        if scenario_path.exists():
            return scenario_path
    fallback_path = fallback_dir / path
    if fallback_path.exists():
        return fallback_path
    if path.exists():
        return path
    raise FileNotFoundError(f"Could not resolve path: {raw_path}")
