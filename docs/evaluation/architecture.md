# Internal Architecture

The evaluation pipeline is separated by domain responsibility. Public entry points remain small and delegate sampling, provider access, and artifact management to dedicated modules.

## Entry Points

`src/evaluation/cli.py` contains only three CLI adapters:

- `cmd_prepare`
- `cmd_evaluate`
- `cmd_decompose`

The adapters parse `--config`, load the appropriate Pydantic model, and invoke the corresponding use case. Domain logic and file access do not live in the CLI.

```text
prepare.py        -> prepare_case_set(...)
runner.py         -> evaluate_run(...)
decomposition.py  -> decompose_run(...)
```

## Shared Config Loading

`src/configuration.py` provides shared infrastructure for filename-based YAML configs through `NamedYamlConfigSource`:

1. Config IDs must not contain a path or suffix.
2. `<config-id>.yaml` is located in the domain-specific config directory.
3. The YAML root must be a mapping.
4. `config_name` must not appear in the YAML.
5. The filename stem is inserted as `config_name` before Pydantic validation.

Domain modules retain their own schemas and semantic rules:

- `formal/grammar/config.py`: grammar sampling.
- `generator/config.py`: scenario generation and grammar resolution.
- `evaluation/config.py`: case sets, tiers, and evaluation runs.

The shared source knows no grammar, generator, or evaluation parameters.

## Prepare

### `prepare.py`

The use-case composition root:

- Determines the output directory.
- Computes the case-set config hash.
- Loads the base grammar and generator.
- Initializes the manifest.
- Starts `CaseSetPreparer`.

### `case_preparation.py`

Orchestrates case-set materialization:

- Iterates tiers, sampling rounds, and sample indices.
- Samples or loads grammars.
- Starts the scenario generator.
- Writes cases.
- Reports progress and failures to the manifest.

`PreparedGrammar`, `PreparedScenario`, and `CaseCoordinates` transport related data explicitly instead of using long loose argument lists or tuples.

### `case_sampling.py`

Contains deterministic, side-effect-free sampling and config resolution:

- Board-seed derivation.
- Board-parameter sampling.
- Resolution of concrete grammar and generator configs.
- Stable grammar and case IDs.

This module writes no files and starts no generator.

### `case_snapshot.py`

Reconstructs the immutable `EvaluationCase` from a prepared grammar and scenario. This is the boundary between generator artifacts and the shared evaluation/decomposition interface.

### `preparation_artifacts.py`

Owns the prepare-manifest lifecycle:

- Loading or creating the manifest.
- Hash and checksum validation for existing artifacts.
- Atomic manifest updates.
- Failure recording.
- Schema output.
- Completion status.

## Evaluate

### `runner.py`

Orchestrates a run:

- Validates the prepare manifest.
- Selects or creates a resumable run.
- Builds and shuffles pending jobs.
- Creates semaphore, cooldown state, and tasks.
- Persists attempts.
- Finalizes the manifest and summary.

Provider and retry details do not belong to this module.

### `jobs.py`

Expands a run config into `EvaluationJob` objects and owns:

- Tier, model, and representation selection.
- Case-path resolution.
- Stable job IDs.

### `job_execution.py`

Owns execution of one job:

- Prompt construction.
- Asynchronous LLM call.
- Parsing and granular evaluation.
- Global semaphore usage.
- Model-specific cooldowns.
- Retry classification and backoff.
- Attempt-result construction.

The LLM caller is injected as a callback, allowing this layer to be tested without a real provider.

### `run_artifacts.py`

Owns run persistence and lookup:

- Resuming a matching incomplete run.
- Finding the newest completed run.
- Detecting final attempts.
- Loading and aggregating attempts.
- Writing run manifests and summaries.

Decomposition uses the same run lookup rather than implementing another manifest search.

## Shared Models and Utilities

- `models.py`: versioned Pydantic models and the `DecompositionAdapter` protocol.
- `artifacts.py`: canonical JSON, SHA-256, atomic JSON writes, and UTC timestamps.
- `sampling.py`: stable seed derivation and bounded normal sampling.

These modules contain no CLI orchestration.

## Dependency Direction

```text
CLI
  -> use-case orchestration
      -> domain services and pure mappers
      -> artifact persistence
      -> existing grammar, generator, and LLM boundaries
```

Pure sampling and mapping functions do not access manifests or providers. Artifact modules do not build prompts or sample parameters. Sampling, retry policy, snapshot construction, and persistence can therefore be tested and changed independently.

## Tests

`tests/test_evaluation.py` covers the main module boundaries:

- Filename-based config names.
- Deterministic bounded sampling.
- Prepare snapshots and manifests.
- Global concurrency without a real provider.
- Evaluation/decomposition handoff.
- Rate-limit reset header handling.

Provider calls are replaced through the injected asynchronous LLM caller. Tests create evaluation artifacts in temporary directories.

## Extensions

- Add a sampling axis in `evaluation/config.py` and `case_sampling.py`.
- Create a new attempt field in `job_execution.py` and aggregate it in `run_artifacts.py` when needed.
- Add retry rules only in `job_execution.py`.
- Implement another decomposition method through `DecompositionAdapter`; prepare and evaluate do not need to change.
- New config types may use `NamedYamlConfigSource` while retaining their own domain-specific Pydantic models.
