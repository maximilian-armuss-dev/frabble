"""One prepared evaluation case, previewed and sent from a notebook."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from src.evaluation.artifacts import file_sha256, read_json, write_json_atomic
from src.evaluation.job_execution import AsyncLLMCaller, execute_job
from src.evaluation.jobs import EvaluationJob, safe_id
from src.evaluation.models import EvaluationCase
from src.llm.client import acall_llm_detailed
from src.llm.env import ENV
from src.llm.prompting import build_prompt
from src.llm.representers import RepresenterConfig

from .board_figures import PROJECT_ROOT
from .evaluation_figures import EvaluationAttemptContext, load_evaluation_attempt


@dataclass(frozen=True)
class PreparedCaseRecord:
    case_id: str
    dimensions: int
    visible_sequences: int
    sampling_round: int
    path: Path


@dataclass(frozen=True)
class CaseSetAxes:
    dimensions: tuple[int, ...]
    visible_sequences: tuple[int, ...]
    rounds: tuple[int, ...]


@dataclass(frozen=True)
class PreparedCasePlayground:
    case_path: Path
    case_sha256: str
    case: EvaluationCase
    model_name: str
    reasoning_effort: str
    system_prompt: str
    user_prompt: str


def list_prepared_cases(
    case_set: str,
    *,
    project_root: str | Path = PROJECT_ROOT,
) -> tuple[PreparedCaseRecord, ...]:
    """List frozen cases and their semantic coordinates."""
    if not case_set or Path(case_set).name != case_set:
        raise ValueError("Pass a case-set name without a path.")
    case_dir = Path(project_root) / "outputs" / "evaluation" / case_set / "cases"
    if not case_dir.is_dir():
        raise FileNotFoundError(f"Prepared case set not found: {case_set!r}.")
    rows = []
    for path in case_dir.glob("*.json"):
        data = read_json(path)
        dimensions = data.get("dimensions") or data.get("board", {}).get("dimensions")
        rows.append(
            (
                int(data["board_size"]),
                int(dimensions),
                int(data["sampling_round"]),
                str(data["case_id"]),
                path,
            )
        )
    return tuple(
        PreparedCaseRecord(case_id, dimensions, size, round_index, path)
        for size, dimensions, round_index, case_id, path in sorted(rows)
    )


def case_set_axes(cases: tuple[PreparedCaseRecord, ...]) -> CaseSetAxes:
    return CaseSetAxes(
        dimensions=tuple(sorted({case.dimensions for case in cases})),
        visible_sequences=tuple(sorted({case.visible_sequences for case in cases})),
        rounds=tuple(sorted({case.sampling_round for case in cases})),
    )


def display_case_set_axes(
    cases: tuple[PreparedCaseRecord, ...],
    *,
    case_set: str,
) -> object:
    axes = case_set_axes(cases)
    from IPython.display import Markdown

    return Markdown(
        f"**Case set:** `{case_set}` · **{len(cases)} prepared puzzles**\n\n"
        f"- Dimensions: `{list(axes.dimensions)}`\n"
        f"- Sequences on board: `{list(axes.visible_sequences)}`\n"
        f"- Rounds: `{list(axes.rounds)}`"
    )


def select_prepared_case(
    cases: tuple[PreparedCaseRecord, ...],
    dimensions: int,
    visible_sequences: int,
    round_index: int,
) -> PreparedCaseRecord:
    axes = case_set_axes(cases)
    for label, selected, available in (
        ("DIMENSIONS", dimensions, axes.dimensions),
        ("SEQUENCES_ON_BOARD", visible_sequences, axes.visible_sequences),
        ("ROUND", round_index, axes.rounds),
    ):
        if (
            isinstance(selected, bool)
            or not isinstance(selected, int)
            or selected not in available
        ):
            raise ValueError(f"{label} must be one of {list(available)}; got {selected!r}.")
    matches = [
        case
        for case in cases
        if (case.dimensions, case.visible_sequences, case.sampling_round)
        == (dimensions, visible_sequences, round_index)
    ]
    if len(matches) != 1:
        raise ValueError(
            "No unique prepared puzzle matches that dimension, sequence count, and round."
        )
    return matches[0]


def prepare_selected_case(
    case: PreparedCaseRecord,
    model_name: str,
    reasoning_effort: str,
) -> PreparedCasePlayground:
    return _prepare_case_path(case.path, model_name, reasoning_effort)


def _prepare_case_path(
    case_path: Path,
    model_name: str,
    reasoning_effort: str,
) -> PreparedCasePlayground:
    ENV.get_model_config(model_name)
    case = EvaluationCase.model_validate(read_json(case_path))
    board = case.to_board()
    system_prompt, user_prompt = build_prompt(
        board,
        case.to_transition(),
        case.to_language(),
        RepresenterConfig(),
    )
    return PreparedCasePlayground(
        case_path=case_path,
        case_sha256=file_sha256(case_path),
        case=case,
        model_name=model_name,
        reasoning_effort=reasoning_effort,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
    )


def display_case_preview(prepared: PreparedCasePlayground) -> object:
    """Show the selected case and prompt before the provider request."""
    case = prepared.case
    markup = (
        f"**Case:** `{case.case_id}` · **Board:** {case.to_board().dimensions}D, "
        f"{case.board_size} visible sequences · **Model:** `{prepared.model_name}` · "
        f"**Reasoning:** `{prepared.reasoning_effort}`\n\n"
        f"**System prompt**\n\n```text\n{prepared.system_prompt}\n```\n\n"
        f"**User prompt**\n\n```text\n{prepared.user_prompt}\n```"
    )
    from IPython.display import Markdown

    return Markdown(markup)


def load_saved_case_attempt(
    case: PreparedCaseRecord,
    model_name: str,
) -> EvaluationAttemptContext:
    """Use the newest completed evaluation attempt for this case and model."""
    runs_dir = case.path.parent.parent / "runs"
    manifests = sorted(
        runs_dir.glob("*/run-manifest.json"),
        key=lambda path: (
            str(read_json(path).get("completed_at") or ""),
            path.parent.name,
        ),
        reverse=True,
    )
    pattern = f"{safe_id(case.case_id)}__{safe_id(model_name)}__*.json"
    for manifest_path in manifests:
        if read_json(manifest_path).get("status") != "complete":
            continue
        attempts = []
        for path in (manifest_path.parent / "attempts").glob(pattern):
            attempt = read_json(path)
            if (
                attempt.get("status") == "complete"
                and attempt.get("case_id") == case.case_id
                and attempt.get("model") == model_name
            ):
                attempts.append((str(attempt.get("timestamp") or ""), path))
        if attempts:
            return load_evaluation_attempt(max(attempts)[1])
    raise FileNotFoundError(
        f"No completed evaluation attempt for case {case.case_id!r} "
        f"and model {model_name!r}. Choose another model or MODE='fresh'."
    )


async def run_prepared_case(
    prepared: PreparedCasePlayground,
    *,
    output_dir: str | Path | None = None,
    call_llm: AsyncLLMCaller = acall_llm_detailed,
) -> EvaluationAttemptContext:
    """Call one model, save the evaluated attempt, and load it for inspection."""
    if file_sha256(prepared.case_path) != prepared.case_sha256:
        raise ValueError("The prepared case changed after preview; prepare it again.")
    job = EvaluationJob(
        job_id="__".join(
            (
                safe_id(prepared.case.case_id),
                safe_id(prepared.model_name),
                prepared.reasoning_effort,
            )
        ),
        case_path=prepared.case_path,
        model_name=prepared.model_name,
        language_representation="forbidden-snippets",
        reasoning_effort=prepared.reasoning_effort,
    )
    attempt = await execute_job(job, 0, call_llm=call_llm)
    root = (
        Path(output_dir)
        if output_dir is not None
        else PROJECT_ROOT / "outputs" / "llm-runs"
    )
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    attempt_path = root / f"{job.job_id}_{timestamp}.json"
    write_json_atomic(attempt_path, attempt)
    return load_evaluation_attempt(attempt_path)
