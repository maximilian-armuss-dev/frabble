from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .board_figures import PROJECT_ROOT


@dataclass(frozen=True)
class EvaluationRunRecord:
    case_set: str
    run_config: str | None
    run_id: str
    status: str
    created_at: str
    completed_at: str | None
    models: tuple[str, ...]
    completed_jobs: int
    error_jobs: int
    path: Path


@dataclass(frozen=True)
class EvaluationAttemptRecord:
    job_id: str
    model: str
    board_size: int | None
    sampling_round: int | None
    status: str
    reasoning_effort: str | None
    path: Path


@dataclass(frozen=True)
class ScenarioRecord:
    source: str
    name: str
    board_size: int | None
    sampling_round: int | None
    seed: int | None
    path: Path
    dimensions: int | None = None


def evaluation_case_sets(*, project_root: str | Path = PROJECT_ROOT) -> tuple[str, ...]:
    root = Path(project_root) / "outputs" / "evaluation"
    if not root.exists():
        return ()
    return tuple(sorted(path.name for path in root.iterdir() if path.is_dir()))


def evaluation_runs(
    case_set: str,
    *,
    status: str | None = None,
    project_root: str | Path = PROJECT_ROOT,
) -> tuple[EvaluationRunRecord, ...]:
    runs_dir = Path(project_root) / "outputs" / "evaluation" / case_set / "runs"
    records = []
    for manifest_path in runs_dir.glob("*/run-manifest.json"):
        manifest = _read_object(manifest_path)
        run_status = str(manifest.get("status") or "unknown")
        if status is not None and run_status != status:
            continue
        records.append(_evaluation_run_record(manifest_path, manifest, case_set))
    return _sort_evaluation_runs(records)


def evaluation_runs_for_config(
    run_config: str,
    *,
    project_root: str | Path = PROJECT_ROOT,
) -> tuple[EvaluationRunRecord, ...]:
    """Find runs produced from one run config across regular and merged outputs."""
    records = []
    for manifest_path in _evaluation_manifest_paths(Path(project_root)):
        manifest = _read_object(manifest_path)
        config = manifest.get("config")
        embedded_name = config.get("config_name") if isinstance(config, dict) else None
        manifest_run_config = manifest.get("run_config") or embedded_name
        if manifest_run_config != run_config:
            continue
        records.append(
            _evaluation_run_record(
                manifest_path,
                manifest,
                default_case_set=manifest_path.parents[2].name,
            )
        )
    return _sort_evaluation_runs(records)


def resolve_evaluation_run_selection(
    case_set: str,
    selector: str | None = "latest",
    *,
    project_root: str | Path = PROJECT_ROOT,
) -> Path:
    if selector not in (None, "latest"):
        path = (
            Path(project_root)
            / "outputs"
            / "evaluation"
            / case_set
            / "runs"
            / selector
        )
        if not path.is_dir():
            raise FileNotFoundError(
                f"Evaluation run {selector!r} not found in case set {case_set!r}."
            )
        return path

    completed = [
        record
        for record in evaluation_runs(case_set, project_root=project_root)
        if record.status == "complete" and (record.path / "aggregate.json").exists()
    ]
    if not completed:
        raise FileNotFoundError(
            f"No completed evaluation run with aggregate found for {case_set!r}."
        )
    return max(
        completed,
        key=lambda record: (record.completed_at or record.created_at, record.run_id),
    ).path


def resolve_evaluation_run_config_selection(
    run_config: str,
    selector: int | str | None = 1,
    *,
    project_root: str | Path = PROJECT_ROOT,
) -> Path:
    """Resolve a completed run by its displayed number or exact run ID."""
    records = _selectable_runs(
        evaluation_runs_for_config(run_config, project_root=project_root)
    )
    if not records:
        raise FileNotFoundError(
            f"No completed evaluation run with aggregate found for {run_config!r}."
        )
    if selector in (None, "latest"):
        return records[0].path
    if isinstance(selector, int):
        if selector < 1 or selector > len(records):
            raise IndexError(
                f"Run number {selector} is outside the displayed range 1..{len(records)}."
            )
        return records[selector - 1].path
    matches = [record for record in records if record.run_id == selector]
    if not matches:
        raise FileNotFoundError(
            f"Evaluation run {selector!r} not found for config {run_config!r}."
        )
    return matches[0].path


def evaluation_attempts(
    run_dir: str | Path,
    *,
    model: str | None = None,
    board_size: int | None = None,
    sampling_round: int | None = None,
    status: str | None = None,
) -> tuple[EvaluationAttemptRecord, ...]:
    records = []
    for attempt_path in Path(run_dir).glob("attempts/*.json"):
        attempt = _read_object(attempt_path)
        record = EvaluationAttemptRecord(
            job_id=str(attempt.get("job_id") or attempt_path.stem),
            model=str(attempt.get("model") or "unknown"),
            board_size=_optional_int(attempt.get("board_size")),
            sampling_round=_optional_int(attempt.get("sampling_round")),
            status=str(attempt.get("status") or "unknown"),
            reasoning_effort=_optional_text(attempt.get("reasoning_effort")),
            path=attempt_path,
        )
        if model is not None and record.model != model:
            continue
        if board_size is not None and record.board_size != board_size:
            continue
        if sampling_round is not None and record.sampling_round != sampling_round:
            continue
        if status is not None and record.status != status:
            continue
        records.append(record)
    return tuple(
        sorted(
            records,
            key=lambda record: (
                record.board_size if record.board_size is not None else -1,
                record.sampling_round if record.sampling_round is not None else -1,
                record.model,
                record.job_id,
            ),
        )
    )


def resolve_evaluation_attempt_selection(
    case_set: str,
    *,
    run: str | None = "latest",
    job_id: str | None = None,
    model: str | None = None,
    board_size: int | None = None,
    sampling_round: int | None = None,
    status: str | None = None,
    project_root: str | Path = PROJECT_ROOT,
) -> Path:
    run_dir = resolve_evaluation_run_selection(
        case_set,
        run,
        project_root=project_root,
    )
    return resolve_attempt_selection(
        run_dir,
        job_id=job_id,
        model=model,
        board_size=board_size,
        sampling_round=sampling_round,
        status=status,
    )


def resolve_attempt_selection(
    run_dir: str | Path,
    *,
    job_id: str | None = None,
    model: str | None = None,
    board_size: int | None = None,
    sampling_round: int | None = None,
    status: str | None = None,
) -> Path:
    candidates = evaluation_attempts(
        run_dir,
        model=model,
        board_size=board_size,
        sampling_round=sampling_round,
        status=status,
    )
    if job_id is not None:
        candidates = tuple(record for record in candidates if record.job_id == job_id)
    if len(candidates) == 1:
        return candidates[0].path
    filters = {
        "job_id": job_id,
        "model": model,
        "board_size": board_size,
        "sampling_round": sampling_round,
        "status": status,
    }
    active = ", ".join(f"{key}={value!r}" for key, value in filters.items() if value is not None)
    if not candidates:
        raise FileNotFoundError(f"No attempt matches {active or 'the selected run'}.")
    raise ValueError(
        f"Attempt selection is ambiguous ({len(candidates)} matches for {active or 'the selected run'}). "
        "Add model, board_size, sampling_round, status, or job_id."
    )


def scenario_sources(*, project_root: str | Path = PROJECT_ROOT) -> tuple[str, ...]:
    root = Path(project_root) / "outputs"
    sources = []
    if (root / "scenarios").is_dir():
        sources.append("standalone")
    evaluation_root = root / "evaluation"
    if evaluation_root.exists():
        sources.extend(
            f"evaluation/{path.name}"
            for path in evaluation_root.iterdir()
            if (path / "scenarios").is_dir()
        )
    sources.extend(
        f"generated/{path.name}"
        for path in root.iterdir()
        if path.is_dir()
        and path.name != "evaluation"
        and (path / "scenarios").is_dir()
    )
    return tuple(sorted(sources))


def scenarios(
    source: str,
    *,
    board_size: int | None = None,
    sampling_round: int | None = None,
    project_root: str | Path = PROJECT_ROOT,
) -> tuple[ScenarioRecord, ...]:
    scenario_dir = _scenario_dir(source, Path(project_root))
    records = []
    for path in scenario_dir.glob("*.json"):
        match = re.search(r"\.b(\d+)\.r(\d+)$", path.stem)
        file_board_size = int(match.group(1)) if match else None
        file_round = int(match.group(2)) if match else None
        if board_size is not None and file_board_size != board_size:
            continue
        if sampling_round is not None and file_round != sampling_round:
            continue
        data = _read_object(path)
        initial_board = data.get("initial_board")
        config = data.get("config")
        dimensions = (
            initial_board.get("dimensions")
            if isinstance(initial_board, dict)
            else None
        )
        if dimensions is None and isinstance(config, dict):
            dimensions = config.get("dimensions")
        records.append(
            ScenarioRecord(
                source=source,
                name=str(data.get("config_name") or path.stem),
                board_size=file_board_size,
                sampling_round=file_round,
                seed=_optional_int(data.get("seed")),
                path=path,
                dimensions=_optional_int(dimensions),
            )
        )
    return tuple(
        sorted(
            records,
            key=lambda record: (
                record.board_size if record.board_size is not None else -1,
                record.sampling_round if record.sampling_round is not None else -1,
                record.name,
            ),
        )
    )


def resolve_scenario_selection(
    source: str,
    *,
    name: str | None = None,
    board_size: int | None = None,
    sampling_round: int | None = None,
    project_root: str | Path = PROJECT_ROOT,
) -> Path:
    candidates = scenarios(
        source,
        board_size=board_size,
        sampling_round=sampling_round,
        project_root=project_root,
    )
    if name is not None:
        normalized = Path(name).stem
        candidates = tuple(
            record
            for record in candidates
            if record.name == name or record.path.stem == normalized
        )
    if len(candidates) == 1:
        return candidates[0].path
    if not candidates:
        raise FileNotFoundError(
            f"No scenario matches source={source!r}, name={name!r}, "
            f"board_size={board_size!r}, sampling_round={sampling_round!r}."
        )
    raise ValueError(
        f"Scenario selection is ambiguous ({len(candidates)} matches). "
        "Add name, board_size, or sampling_round."
    )


def display_evaluation_run_catalog(
    case_set: str,
    *,
    selected: str | None = "latest",
    limit: int = 10,
    project_root: str | Path = PROJECT_ROOT,
) -> object:
    records = evaluation_runs(case_set, project_root=project_root)[:limit]
    selected_path = None
    try:
        selected_path = resolve_evaluation_run_selection(
            case_set,
            selected,
            project_root=project_root,
        )
    except FileNotFoundError:
        pass
    rows = [
        (
            "✓" if record.path == selected_path else "",
            _short_timestamp(record.completed_at or record.created_at),
            record.run_id,
            record.status,
            ", ".join(record.models) or "—",
            str(record.completed_jobs),
            str(record.error_jobs),
        )
        for record in records
    ]
    case_sets = evaluation_case_sets(project_root=project_root)
    selected_text = selected_path.name if selected_path is not None else "unresolved"
    return _display_table(
        f"Evaluation runs · {case_set}",
        ("", "date", "run", "status", "models", "complete", "errors"),
        rows,
        footer=(
            f"{_collapsible_values('Available case sets', case_sets)}"
            f"<br>Selected: {html.escape(selected_text)}"
        ),
    )


def display_evaluation_config_run_catalog(
    run_config: str,
    *,
    selected: int | str | None = 1,
    limit: int = 10,
    project_root: str | Path = PROJECT_ROOT,
) -> object:
    records = _selectable_runs(
        evaluation_runs_for_config(run_config, project_root=project_root)
    )[:limit]
    selected_path = None
    try:
        selected_path = resolve_evaluation_run_config_selection(
            run_config,
            selected,
            project_root=project_root,
        )
    except (FileNotFoundError, IndexError):
        pass
    rows = [
        (
            str(index),
            "✓" if record.path == selected_path else "",
            _short_timestamp(record.completed_at or record.created_at),
            record.run_id,
            record.case_set,
            ", ".join(record.models) or "—",
            str(record.completed_jobs),
            str(record.error_jobs),
        )
        for index, record in enumerate(records, start=1)
    ]
    selected_text = selected_path.name if selected_path is not None else "unresolved"
    return _display_table(
        f"Evaluation runs · config {run_config}",
        ("#", "", "date", "run", "case set", "models", "complete", "errors"),
        rows,
        footer=f"Selected: {html.escape(selected_text)}",
    )


def display_attempt_catalog(
    case_set: str,
    *,
    run: str | None = "latest",
    model: str | None = None,
    board_size: int | None = None,
    sampling_round: int | None = None,
    status: str | None = None,
    limit: int = 20,
    project_root: str | Path = PROJECT_ROOT,
) -> object:
    run_dir = resolve_evaluation_run_selection(case_set, run, project_root=project_root)
    return display_attempt_catalog_for_run(
        run_dir,
        model=model,
        board_size=board_size,
        sampling_round=sampling_round,
        status=status,
        limit=limit,
    )


def display_attempt_catalog_for_run(
    run_dir: str | Path,
    *,
    model: str | None = None,
    board_size: int | None = None,
    sampling_round: int | None = None,
    status: str | None = None,
    limit: int = 20,
) -> object:
    run_dir = Path(run_dir)
    records = evaluation_attempts(
        run_dir,
        model=model,
        board_size=board_size,
        sampling_round=sampling_round,
        status=status,
    )
    rows = [
        (
            record.job_id,
            record.model,
            _display_optional(record.board_size),
            _display_optional(record.sampling_round),
            record.status,
            record.reasoning_effort or "—",
        )
        for record in records[:limit]
    ]
    suffix = "" if len(records) <= limit else f" · showing {limit} of {len(records)}"
    return _display_table(
        f"Attempts · {run_dir.name}{suffix}",
        ("job", "model", "board", "round", "status", "reasoning"),
        rows,
    )


def _evaluation_manifest_paths(project_root: Path) -> tuple[Path, ...]:
    output_root = project_root / "outputs"
    regular = output_root.glob("evaluation/*/runs/*/run-manifest.json")
    exported = output_root.glob("*/runs/*/run-manifest.json")
    return tuple(sorted({*regular, *exported}))


def _evaluation_run_record(
    manifest_path: Path,
    manifest: dict[str, object],
    default_case_set: str,
) -> EvaluationRunRecord:
    config = manifest.get("config")
    config_values = config if isinstance(config, dict) else {}
    models = config_values.get("models", {})
    return EvaluationRunRecord(
        case_set=str(manifest.get("case_set") or default_case_set),
        run_config=_optional_text(
            manifest.get("run_config") or config_values.get("config_name")
        ),
        run_id=str(manifest.get("run_id") or manifest_path.parent.name),
        status=str(manifest.get("status") or "unknown"),
        created_at=str(manifest.get("created_at") or ""),
        completed_at=_optional_text(manifest.get("completed_at")),
        models=tuple(sorted(str(model) for model in models)),
        completed_jobs=int(manifest.get("completed_jobs") or 0),
        error_jobs=int(manifest.get("error_jobs") or 0),
        path=manifest_path.parent,
    )


def _sort_evaluation_runs(
    records: Iterable[EvaluationRunRecord],
) -> tuple[EvaluationRunRecord, ...]:
    return tuple(
        sorted(
            records,
            key=lambda record: (
                record.completed_at or record.created_at,
                record.run_id,
            ),
            reverse=True,
        )
    )


def _selectable_runs(
    records: Iterable[EvaluationRunRecord],
) -> tuple[EvaluationRunRecord, ...]:
    return tuple(
        record
        for record in records
        if record.status == "complete" and (record.path / "aggregate.json").exists()
    )


def display_scenario_catalog(
    source: str,
    *,
    name: str | None = None,
    board_size: int | None = None,
    sampling_round: int | None = None,
    limit: int = 20,
    project_root: str | Path = PROJECT_ROOT,
) -> object:
    records = scenarios(
        source,
        board_size=board_size,
        sampling_round=sampling_round,
        project_root=project_root,
    )
    selected_path = None
    try:
        selected_path = resolve_scenario_selection(
            source,
            name=name,
            board_size=board_size,
            sampling_round=sampling_round,
            project_root=project_root,
        )
    except (FileNotFoundError, ValueError):
        pass
    rows = [
        (
            "✓" if record.path == selected_path else "",
            record.name,
            _display_optional(record.board_size),
            _display_optional(record.sampling_round),
            _display_optional(record.seed),
        )
        for record in records[:limit]
    ]
    sources = scenario_sources(project_root=project_root)
    suffix = "" if len(records) <= limit else f" · showing {limit} of {len(records)}"
    footer = _collapsible_values("Available sources", sources)
    if selected_path is not None:
        footer += f"<br>Selected: {selected_path.name}"
    return _display_table(
        f"Scenarios · {source}{suffix}",
        ("", "scenario", "board", "round", "seed"),
        rows,
        footer=footer,
    )


def _scenario_dir(source: str, project_root: Path) -> Path:
    output_root = project_root / "outputs"
    if source == "standalone":
        path = output_root / "scenarios"
    elif source.startswith("evaluation/"):
        path = output_root / "evaluation" / source.removeprefix("evaluation/") / "scenarios"
    elif source.startswith("generated/"):
        path = output_root / source.removeprefix("generated/") / "scenarios"
    else:
        raise ValueError(
            "Scenario source must be 'standalone', 'evaluation/<case-set>', "
            "or 'generated/<collection>'."
        )
    if not path.is_dir():
        raise FileNotFoundError(f"Scenario source not found: {source!r} ({path})")
    return path


def _display_table(
    title: str,
    headers: Iterable[str],
    rows: Iterable[Iterable[str]],
    *,
    footer: str | None = None,
) -> object:
    head = "".join(f"<th>{html.escape(value)}</th>" for value in headers)
    body_rows = list(rows)
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(value)}</td>" for value in row) + "</tr>"
        for row in body_rows
    )
    if not body_rows:
        body = f'<tr><td colspan="99"><em>No matching artifacts.</em></td></tr>'
    footer_markup = f'<div class="artifact-footer">{footer}</div>' if footer else ""
    markup = f"""
<style>
.artifact-catalog {{
  --catalog-foreground: var(--vscode-editor-foreground, var(--jp-ui-font-color1, inherit));
  --catalog-background: var(--vscode-editor-background, var(--jp-layout-color0, transparent));
  --catalog-muted: var(--vscode-descriptionForeground, var(--jp-ui-font-color2, currentColor));
  --catalog-border: var(--vscode-panel-border, var(--jp-border-color2, rgba(127,127,127,.35)));
  font:13px system-ui,sans-serif;
  color:var(--catalog-foreground);
  background:var(--catalog-background);
  max-width:100%;
}}
.artifact-catalog h4 {{margin:0 0 8px;font-size:14px;color:inherit;}}
.artifact-catalog table {{border-collapse:collapse;width:100%;color:inherit;background:transparent;}}
.artifact-catalog th,.artifact-catalog td {{padding:5px 8px;border-bottom:1px solid var(--catalog-border);text-align:left;color:inherit;}}
.artifact-catalog th {{font-size:11px;text-transform:uppercase;color:var(--catalog-muted);}}
.artifact-catalog td:nth-child(3) {{font-family:ui-monospace,monospace;font-size:12px;}}
.artifact-footer {{margin-top:8px;color:var(--catalog-muted);font-size:12px;overflow-wrap:anywhere;}}
</style>
<div class="artifact-catalog"><h4>{html.escape(title)}</h4>
<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>{footer_markup}</div>
"""
    try:
        from IPython.display import HTML

        return HTML(markup)
    except ImportError:
        return markup


def _read_object(path: Path) -> dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return data


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    return int(value)


def _optional_text(value: object) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _display_optional(value: object | None) -> str:
    return "—" if value is None else str(value)


def _short_timestamp(value: str) -> str:
    return value.replace("T", " ")[:19] if value else "—"


def _collapsible_values(label: str, values: Iterable[str]) -> str:
    items = tuple(values)
    contents = ", ".join(html.escape(value) for value in items) or "none"
    return (
        '<details style="display:inline-block;">'
        f"<summary>{html.escape(label)} ({len(items)})</summary>"
        f'<div style="margin-top:4px;">{contents}</div></details>'
    )
