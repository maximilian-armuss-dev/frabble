from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ..formal.grammar.config import GrammarConfig
from ..formal.grammar.sampler import sample_grammar_from_config
from ..formal.grammar.serialization import save_grammar
from ..generator.config import GeneratorConfig, PROJECT_ROOT
from ..generator.engine import ScenarioGenerator
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
from .config import CaseSetConfig, TierConfig
from .preparation_artifacts import (
    PreparationManifest,
    artifact_entry,
)


@dataclass
class CaseSetPreparer:
    config: CaseSetConfig
    base_grammar: GrammarConfig
    base_generation: GeneratorConfig
    root: Path
    config_hash: str
    manifest: PreparationManifest
    progress_callback: Callable[[int], None] | None = None

    def prepare(self) -> None:
        git_revision = _git_revision()
        for tier_name, tier in self.config.tiers.items():
            for round_index in range(self.config.sampling_rounds):
                for grammar_index in range(self.config.grammar_samples_per_tier):
                    grammar = self._prepare_grammar(
                        tier_name,
                        tier,
                        round_index,
                        grammar_index,
                    )
                    for board_index in range(self.config.boards_per_grammar):
                        coordinates = CaseCoordinates(
                            tier_name=tier_name,
                            round_index=round_index,
                            grammar_index=grammar_index,
                            board_index=board_index,
                        )
                        self._prepare_case(
                            coordinates=coordinates,
                            tier=tier,
                            grammar=grammar,
                            git_revision=git_revision,
                        )
                        if self.progress_callback is not None:
                            self.progress_callback(1)

    def _prepare_grammar(
        self,
        tier_name: str,
        tier: TierConfig,
        round_index: int,
        grammar_index: int,
    ) -> PreparedGrammar:
        grammar_id = grammar_artifact_id(
            self.config.config_name,
            tier_name,
            round_index,
            grammar_index,
        )
        grammar_path = self.root / "grammars" / f"{grammar_id}.json"
        grammar_config = resolve_grammar_config(
            self.base_grammar,
            self.config,
            tier_name,
            tier,
            round_index,
            grammar_index,
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

    def _prepare_case(
        self,
        *,
        coordinates: CaseCoordinates,
        tier: TierConfig,
        grammar: PreparedGrammar,
        git_revision: str | None,
    ) -> None:
        case_id = evaluation_case_id(
            self.config.config_name,
            coordinates,
        )
        try:
            parameters = sample_board_parameters(
                self.config,
                tier,
                coordinates,
            )
            scenario = self._prepare_scenario(
                case_id,
                parameters,
                grammar.path,
            )
            self._prepare_case_artifact(
                case_id=case_id,
                coordinates=coordinates,
                parameters=parameters,
                grammar=grammar,
                scenario=scenario,
                git_revision=git_revision,
            )
            self.manifest.clear_failure(case_id)
        except Exception as exc:
            self.manifest.record_failure(case_id, exc)
            raise

    def _prepare_scenario(
        self,
        scenario_id: str,
        parameters: SampledBoardParameters,
        grammar_path: Path,
    ) -> PreparedScenario:
        scenario_path = self.root / "scenarios" / f"{scenario_id}.json"
        generation_config = resolve_generation_config(
            self.base_generation,
            scenario_id=scenario_id,
            parameters=parameters,
            grammar_path=grammar_path,
            output_path=scenario_path,
        )
        scenario_hash = content_sha256(generation_config.model_dump(mode="json"))
        if not self.manifest.artifact_matches(
            "scenarios",
            scenario_id,
            scenario_hash,
            scenario_path,
        ):
            generator = ScenarioGenerator(generation_config)
            generator.write(generator.generate())
            self.manifest.record_artifact(
                "scenarios",
                scenario_id,
                artifact_entry(
                    config_hash=scenario_hash,
                    path=scenario_path,
                    board_depth=parameters.board_depth,
                ),
            )
        return PreparedScenario(config=generation_config, path=scenario_path)

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
                tier=coordinates.tier_name,
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
