from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path

from ..formal.grammar.config import GrammarConfig
from ..formal.grammar.sampler import sample_grammar_from_config
from ..formal.grammar.serialization import save_grammar
from ..generator.config import GeneratorConfig, PROJECT_ROOT
from ..generator.engine import ScenarioGenerator
from ..generator.readable_json import dumps_readable_json
from ..generator.scenario_io import load_scenario_run
from .artifacts import content_sha256, file_sha256, write_json_atomic
from .case_sampling import (
    CaseCoordinates,
    SampledBoardParameters,
    evaluation_case_id,
    grammar_artifact_id,
    resolve_generation_config,
    resolve_grammar_config,
    sample_board_parameters,
)
from .case_snapshot import PreparedGrammar, PreparedScenario, build_evaluation_case
from .config import CaseSetConfig
from .scenario_workers import ScenarioTask, resolve_worker_count, run_scenarios
from .preparation_artifacts import (
    PreparationManifest,
    artifact_entry,
)


@dataclass(frozen=True)
class _CaseWork:
    case_id: str
    coordinates: CaseCoordinates
    parameters: SampledBoardParameters
    grammar: PreparedGrammar
    scenario: PreparedScenario
    scenario_hash: str

    def task(self) -> ScenarioTask:
        return ScenarioTask(self.case_id, self.scenario.config.model_dump(mode="json"))


@dataclass
class CaseSetPreparer:
    config: CaseSetConfig
    base_grammar: GrammarConfig
    base_generation: GeneratorConfig
    root: Path
    config_hash: str
    manifest: PreparationManifest
    workers: int | None = None
    generation_progress_factory: (
        Callable[
            [str, int],
            AbstractContextManager[Callable[[int], None]],
        ]
        | None
    ) = None

    def prepare(self) -> None:
        git_revision = _git_revision()
        grammars: dict[str, PreparedGrammar] = {}
        pending: dict[str, _CaseWork] = {}
        seen: set[str] = set()
        for board_size in self.config.board_sizes:
            for round_index in range(self.config.sampling_rounds):
                for dimensions in self.config.dimensions or [None]:
                    coordinates = CaseCoordinates(board_size, round_index, dimensions)
                    grammar_id = grammar_artifact_id(
                        self.config.config_name, board_size, round_index
                    )
                    if grammar_id not in grammars:
                        grammars[grammar_id] = self._prepare_grammar(coordinates)
                    case_id = evaluation_case_id(self.config.config_name, coordinates)
                    if case_id in seen:
                        raise ValueError(f"Duplicate scenario ID: {case_id}")
                    seen.add(case_id)
                    try:
                        work = self._resolve_case(coordinates, grammars[grammar_id])
                        if self.manifest.artifact_matches(
                            "scenarios", case_id, work.scenario_hash, work.scenario.path
                        ):
                            self._finish_case(work, git_revision)
                        else:
                            pending[case_id] = work
                    except Exception as exc:
                        self.manifest.record_failure(case_id, exc)
                        raise

        worker_count = resolve_worker_count(self.workers, len(pending))
        if worker_count == 0:
            return

        def completed(task: ScenarioTask, checksum: str) -> None:
            work = pending[task.scenario_id]
            path = work.scenario.path
            if file_sha256(path) != checksum:
                raise ValueError(f"{task.scenario_id}: scenario checksum changed")
            run = load_scenario_run(path)
            if (
                # The existing serializer truncates floats to four decimals.
                run.config != json.loads(dumps_readable_json(task.config))
                or run.config_name != task.scenario_id
                or run.seed != task.config["seed"]
                or len(run.transitions) != task.config["target_transition_count"]
            ):
                raise ValueError(f"{task.scenario_id}: unexpected scenario content")
            self.manifest.record_artifact(
                "scenarios", task.scenario_id,
                artifact_entry(
                    config_hash=work.scenario_hash, path=path,
                    board_depth=work.parameters.board_depth,
                    dimensions=work.parameters.dimensions,
                ),
            )
            self._finish_case(work, git_revision)

        def failed(task: ScenarioTask, exc: Exception) -> None:
            self.manifest.record_failure(task.scenario_id, exc)

        if worker_count == 1:
            for work in pending.values():
                task = work.task()
                try:
                    generator = ScenarioGenerator(work.scenario.config)
                    if self.generation_progress_factory is None:
                        run = generator.generate()
                    else:
                        with self.generation_progress_factory(
                            work.case_id, work.scenario.config.target_transition_count
                        ) as update:
                            run = generator.generate(progress_callback=update)
                    path = generator.write(run)
                    completed(task, file_sha256(path))
                except Exception as exc:
                    failed(task, exc)
                    raise
                except KeyboardInterrupt:
                    failed(task, RuntimeError("Preparation interrupted by user"))
                    raise
        else:
            run_scenarios(
                (work.task() for work in pending.values()),
                workers=worker_count, completed=completed, failed=failed,
                progress_factory=self.generation_progress_factory,
            )

    def _resolve_case(
        self, coordinates: CaseCoordinates, grammar: PreparedGrammar
    ) -> _CaseWork:
        case_id = evaluation_case_id(self.config.config_name, coordinates)
        parameters = sample_board_parameters(self.config, coordinates, self.base_generation)
        path = self.root / "scenarios" / f"{case_id}.json"
        config = resolve_generation_config(
            self.base_generation, scenario_id=case_id, parameters=parameters,
            grammar_path=grammar.path, output_path=path,
        )
        return _CaseWork(
            case_id, coordinates, parameters, grammar,
            PreparedScenario(config=config, path=path),
            content_sha256(config.model_dump(mode="json")),
        )

    def _finish_case(self, work: _CaseWork, git_revision: str | None) -> None:
        self._prepare_case_artifact(
            case_id=work.case_id, coordinates=work.coordinates,
            parameters=work.parameters, grammar=work.grammar,
            scenario=work.scenario, git_revision=git_revision,
        )
        self.manifest.clear_failure(work.case_id)

    def _prepare_grammar(
        self,
        coordinates: CaseCoordinates,
    ) -> PreparedGrammar:
        grammar_id = grammar_artifact_id(
            self.config.config_name,
            coordinates.board_size,
            coordinates.round_index,
        )
        grammar_path = self.root / "grammars" / f"{grammar_id}.json"
        grammar_config = resolve_grammar_config(
            self.base_grammar,
            self.config,
            coordinates.board_size,
            coordinates.round_index,
            grammar_id,
        )
        grammar_hash = content_sha256(grammar_config.model_dump(mode="json"))

        if not self.manifest.artifact_matches(
            "grammars",
            grammar_id,
            grammar_hash,
            grammar_path,
        ):
            try:
                grammar, actual_seed = sample_grammar_from_config(
                    grammar_config,
                    language_id=grammar_id,
                )
                grammar_path.parent.mkdir(parents=True, exist_ok=True)
                save_grammar(
                    grammar,
                    grammar_config,
                    grammar_path,
                    grammar_id,
                )
                self.manifest.record_artifact(
                    "grammars",
                    grammar_id,
                    artifact_entry(
                        config_hash=grammar_hash,
                        path=grammar_path,
                        requested_seed=grammar_config.seed,
                        actual_seed=actual_seed,
                    ),
                )
            except Exception as exc:
                self.manifest.record_failure(grammar_id, exc)
                raise

        self.manifest.clear_failure(grammar_id)
        return PreparedGrammar(
            config=grammar_config,
            path=grammar_path,
            actual_seed=int(
                self.manifest.data["grammars"][grammar_id]["actual_seed"]
            ),
        )

    def _prepare_case_artifact(
        self,
        *,
        case_id: str,
        coordinates: CaseCoordinates,
        parameters: SampledBoardParameters,
        grammar: PreparedGrammar,
        scenario: PreparedScenario,
        git_revision: str | None,
    ) -> None:
        grammar_sha256 = file_sha256(grammar.path)
        scenario_sha256 = file_sha256(scenario.path)
        case_hash = content_sha256(
            {
                "case_set_config_hash": self.config_hash,
                "grammar_sha256": grammar_sha256,
                "scenario_sha256": scenario_sha256,
                "board_depth": parameters.board_depth,
            }
        )
        case_path = self.root / "cases" / f"{case_id}.json"
        if self.manifest.artifact_matches(
            "cases",
            case_id,
            case_hash,
            case_path,
        ):
            return

        evaluation_case = build_evaluation_case(
            case_id=case_id,
            case_set=self.config.config_name,
            coordinates=coordinates,
            parameters=parameters,
            grammar=grammar,
            grammar_sha256=grammar_sha256,
            scenario=scenario,
            scenario_sha256=scenario_sha256,
            case_set_config_hash=self.config_hash,
            git_revision=git_revision,
        )
        write_json_atomic(case_path, evaluation_case.model_dump(mode="json"))
        self.manifest.record_artifact(
            "cases",
            case_id,
            artifact_entry(
                config_hash=case_hash,
                path=case_path,
                board_size=coordinates.board_size,
                dimensions=parameters.dimensions,
            ),
        )


def _git_revision() -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None
