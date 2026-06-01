from __future__ import annotations

import json
import html
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Literal, Mapping, Sequence

from src.domain.board import Board
from src.domain.models import Move
from src.formal.grammar.serialization import load_grammar
from src.formal.parsing import SubmittedMove, parse_submitted_move
from src.formal.validation import validate_move_detailed
from src.generator.reconstruction import board_before_transition
from src.generator.scenario_io import load_scenario_run
from src.llm.client import call_llm
from src.llm.env import ENV
from src.llm.evaluation import evaluate_granular
from src.llm.prompting import build_prompt
from src.llm.representers import RepresenterConfig

from .board_figures import PROJECT_ROOT, plot_board_projected, resolve_scenario_path


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
    output_dir: str | Path | None = None,
    representers: RepresenterConfig | None = None,
) -> LLMRunContext:
    """Run one scenario transition through an LLM and return its inspection context."""
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

    model_config = ENV.get_model_config(model_name)
    started_at = perf_counter()
    raw_response = call_llm(system_prompt, user_prompt, model_name)
    elapsed = perf_counter() - started_at

    submitted: SubmittedMove | None = None
    parse_error: str | None = None
    try:
        submitted = parse_submitted_move(raw_response)
    except Exception as exc:
        parse_error = str(exc)

    evaluation = evaluate_granular(
        board, language, transition.rack, submitted, parse_error
    )
    timestamp = datetime.now()
    model_tag = model_name.replace("/", "-").replace(":", "-")
    run_dir = (
        Path(output_dir)
        if output_dir is not None
        else PROJECT_ROOT / "outputs" / "llm-runs"
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    output_path = run_dir / (
        f"{scenario_path.stem}_t{transition_index}_{model_tag}_"
        f"{timestamp.strftime('%Y%m%dT%H%M%S')}.json"
    )
    run_log = {
        "scenario_file": str(scenario_path),
        "transition_index": transition_index,
        "model": model_name,
        "model_config": {
            "model": model_config.model,
            "reasoning_depth": model_config.reasoning_effort,
            "reasoning_effort": model_config.reasoning_effort,
            "timeout_seconds": model_config.timeout_seconds,
        },
        "timestamp": timestamp.isoformat(),
        "llm_elapsed_seconds": elapsed,
        "representers": {
            "language": active_representers.language.name,
            "board": active_representers.board.name,
            "rack": active_representers.rack.name,
        },
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "raw_response": raw_response,
        "parsed_move": submitted.model_dump() if submitted is not None else None,
        "evaluation": evaluation.to_json(),
        "ground_truth_move": transition.move.to_json(),
    }
    output_path.write_text(json.dumps(run_log, indent=2, ensure_ascii=False), encoding="utf-8")
    return load_llm_run_context(output_path)


def llm_run_summary(context: LLMRunContext) -> dict[str, object]:
    evaluation = dict(context.run_log.get("evaluation", {}))
    model_config = dict(context.run_log.get("model_config", {}))
    parsed_move = context.parsed_move
    validation = None
    if parsed_move is not None:
        grammar_path = _grammar_path(context.scenario_path)
        language, _, _ = load_grammar(grammar_path)
        validation = validate_move_detailed(
            context.board, language, context.rack, parsed_move
        ).result
    return {
        "run_file": str(context.run_path),
        "scenario_file": str(context.scenario_path),
        "transition_index": context.run_log["transition_index"],
        "model": context.run_log["model"],
        "reasoning_depth": model_config.get("reasoning_depth")
        or model_config.get("reasoning_effort"),
        "llm_elapsed_seconds": context.run_log.get("llm_elapsed_seconds"),
        "overall": evaluation.get("overall"),
        "failure_type": evaluation.get("failure_type"),
        "message": evaluation.get("message"),
        "sequence_valid": evaluation.get("sequence_valid"),
        "spatial_valid": evaluation.get("spatial_valid"),
        "overlap_valid": evaluation.get("overlap_valid"),
        "no_word_extension": evaluation.get("no_word_extension"),
        "cross_words_valid": evaluation.get("cross_words_valid"),
        "rack_symbols_used": evaluation.get("rack_symbols_used"),
        "rack_size": len(context.rack),
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
    failure_type = summary["failure_type"] or "none"
    message = summary["message"] or ""
    checks = [
        ("sequence", summary["sequence_valid"]),
        ("spatial", summary["spatial_valid"]),
        ("overlap", summary["overlap_valid"]),
        ("no word extension", summary["no_word_extension"]),
        ("cross words", summary["cross_words_valid"]),
    ]
    elapsed = summary["llm_elapsed_seconds"]
    elapsed_text = "n/a" if elapsed is None else f"{float(elapsed):.1f}s"
    rack_text = f"{summary['rack_symbols_used']}/{summary['rack_size']}"
    check_rows = "\n".join(
        f"""
        <tr>
          <td>{html.escape(label)}</td>
          <td class="{_check_class(value)}">{_check_symbol(value)}</td>
        </tr>
        """
        for label, value in checks
    )
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
        <strong>{html.escape(str(failure_type))}</strong>
        <span style="color:#6b7280;">transition {summary['transition_index']}</span>
      </div>
      <div style="display:grid;grid-template-columns:repeat(4,minmax(0,1fr));
                  gap:10px;padding:12px 14px;border-bottom:1px solid #e5e7eb;">
        {_metric_card("model", summary["model"])}
        {_metric_card("reasoning", summary["reasoning_depth"])}
        {_metric_card("LLM time", elapsed_text)}
        {_metric_card("rack used", rack_text)}
      </div>
      <div style="padding:12px 14px;border-bottom:1px solid #e5e7eb;">
        <div style="font-size:12px;text-transform:uppercase;color:#6b7280;
                    font-weight:700;margin-bottom:4px;">message</div>
        <code style="white-space:pre-wrap;color:#111827;">{html.escape(str(message))}</code>
      </div>
      <div>
        <table style="border-collapse:collapse;width:100%;font-size:14px;">
          <tbody>{check_rows}</tbody>
        </table>
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


def plot_llm_run_move(
    context: LLMRunContext,
    *,
    move_source: MoveSource = "parsed",
    visible_axes: Sequence[int] | None = None,
    slice_coords: Mapping[int, int] | None = None,
) -> object:
    move = _select_move(context, move_source)
    if move is None:
        return plot_board_projected(
            context.board,
            title="No parsed LLM move",
            visible_axes=visible_axes,
            slice_coords=slice_coords,
        )
    board = _board_with_move_overlay(context.board, move)
    return plot_board_projected(
        board,
        highlight_coords=_new_move_coords(context.board, move),
        title=f"{move_source.replace('_', ' ').title()} move",
        visible_axes=visible_axes,
        slice_coords=slice_coords,
    )


def _select_move(context: LLMRunContext, move_source: MoveSource) -> Move | None:
    if move_source == "parsed":
        return context.parsed_move
    if move_source == "ground_truth":
        return context.ground_truth_move
    raise ValueError(f"Unknown move source: {move_source}")


def _board_with_move_overlay(board: Board, move: Move) -> Board:
    cells = dict(board.cells)
    for coord, symbol in zip(move.coords(), move.sequence, strict=True):
        if coord not in cells:
            cells[coord] = symbol
    return Board(dimensions=board.dimensions, cells=cells, segments=board.segments)


def _new_move_coords(board: Board, move: Move) -> tuple[tuple[int, ...], ...]:
    return tuple(coord for coord in move.coords() if board.get(coord) is None)


def _metric_card(label: str, value: object) -> str:
    return f"""
    <div>
      <div style="font-size:12px;text-transform:uppercase;color:#6b7280;
                  font-weight:700;">{html.escape(label)}</div>
      <div style="font-size:15px;font-weight:600;white-space:nowrap;
                  overflow:hidden;text-overflow:ellipsis;">{html.escape(str(value))}</div>
    </div>
    """


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
    grammar_path = Path(str(scenario_run.config.get("grammar_path", "")))
    if grammar_path.is_absolute() and grammar_path.exists():
        return grammar_path
    root_path = PROJECT_ROOT / grammar_path
    if root_path.exists():
        return root_path
    relative_to_scenario = scenario_path.parent / grammar_path
    if relative_to_scenario.exists():
        return relative_to_scenario
    raise FileNotFoundError(f"Grammar file not found: {grammar_path}")


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
