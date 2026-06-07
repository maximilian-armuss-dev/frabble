# Lifecycle and Artifacts

## Prepare

```bash
uv run prepare --config screening_v1
```

Prepare:

1. Loads and validates the case set.
2. Expands sampling rounds, tiers, and sample indices.
3. Samples grammar parameters and grammars.
4. Samples board parameters and generates scenarios.
5. Reconstructs the board state at `board_depth`.
6. Materializes an immutable evaluation case.
7. Updates the prepare manifest atomically.

`prepare.py` remains the small entry point. `case_preparation.py` orchestrates materialization, `case_sampling.py` contains deterministic sampling, `case_snapshot.py` builds the shared snapshot, and `preparation_artifacts.py` owns the manifest lifecycle. See [architecture.md](architecture.md) for the detailed split.

For a case with `board_depth = n`, the resolved generator creates at least `n + 1` witness transitions. The model sees the board after transitions `0` through `n - 1` and must use the rack at transition index `n`.

Prepare is model-independent. An existing artifact is reused only if its ID, config hash, and file checksum match the manifest.

## Evaluate

```bash
uv run evaluate --config gpt5_mini_all
```

Evaluate:

1. Loads the run config and referenced prepare manifest.
2. Filters cases by tier.
3. Expands models and language representations.
4. Creates stable job IDs.
5. Shuffles pending jobs deterministically.
6. Executes them with the asynchronous concurrency window.
7. Persists each final job result immediately after its retry sequence.
8. Writes the manifest and summaries.

`runner.py` coordinates this flow. Job expansion, provider execution, and run persistence are separated into `jobs.py`, `job_execution.py`, and `run_artifacts.py`.

A semantically invalid model move is a completed evaluation attempt with `overall = false`. Transport, authentication, and provider errors are not model failures and are classified separately.

## Decompose

```bash
uv run decompose --config gpt5_mini_all
```

Decompose uses the same run config. It finds the newest completed evaluation run with the same canonical run-config hash and processes its semantically failed attempts.

The initial adapter creates versioned `DecompositionRequest` artifacts and returns `not_implemented`. It makes no LLM calls. A future implementation can implement the Python protocol directly or consume the JSON artifacts separately.

## Resume

Every phase is resumable:

- Prepare skips complete, hash-compatible grammars, scenarios, and cases.
- Evaluate skips jobs with final attempt artifacts.
- Retryable provider failures remain executable while retry budget remains.
- Exhausted or non-retryable infrastructure failures are recorded visibly in the run manifest.
- Decompose skips requests and results that already exist.

Manifests are updated after every completed artifact. An interruption therefore loses at most the currently active provider call.

## Identities and Hashes

IDs are built from stable domain components:

- Grammar: case set, tier, sampling round, and grammar index.
- Scenario and case: case set, tier, sampling round, grammar index, and board index.
- Job: case ID, model profile, reasoning effort, and language representation.

Hashes are built from canonical JSON with sorted keys. Timestamps and absolute local paths are not part of semantic content hashes.
