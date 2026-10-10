# Development and regression checks

The local suite checks the path from a sampled language through generation,
frozen cases, model-response validation, saved results, and notebook views.
Small fixed inputs keep these checks independent of whichever experiments are
currently selected in `config/`.

## Running checks

From the repository root:

```bash
uv sync --locked --dev
uv run pytest
uv run ruff check .
```

`uv run pytest tests/test_optimality.py` runs one area; `uv run pytest -k resume`
selects tests by name. `uv run pytest --durations=10` shows the slowest checks.
The existing unittest cases also remain runnable with
`uv run python -m unittest discover -s tests`; use pytest for the complete suite,
including the additional CLI, config-reference, and artifact compatibility tests.

No provider credentials, prepared evaluation sets, or generated scenarios are
needed. Tests create outputs in temporary directories. Pytest blocks network
sockets while allowing the local Unix sockets used by asyncio. LiteLLM uses its
bundled model metadata, including in spawned probes. Provider tests use mocks or
HTTPX's in-memory transport; process probes only run local preparation.

The [CI workflow](../.github/workflows/tests.yml) installs the lockfile and runs
the same checks on Python 3.11 and 3.12. Ruff currently checks undefined names,
unused imports, and other Pyflakes errors. Notebooks and the separate paper tree
are excluded from linting; this avoids a wholesale formatting change.

## Code boundaries

| Boundary | Responsibility and invariants |
|---|---|
| [`domain`](../src/domain/) and [`formal`](../src/formal/) | Sparse boards, moves, language membership, and independent move legality. |
| [`generator`](../src/generator/) and [`benchmark`](../src/benchmark/) | Candidate search proposes a rack; exact optimization certifies its best move. Serialization preserves move order and the distinction between historical references and certified optima. |
| [`evaluation`](../src/evaluation/) | Preparation freezes cases; workers generate independent scenarios; execution persists attempts; aggregation derives results from saved attempts. Retry/resume behavior belongs here. |
| [`llm`](../src/llm/) | Prompt representations, provider configuration, transport, and response parsing. Provider calls are mocked in tests. |
| [`visualization/src`](../visualization/src/) | Reads artifacts and presents boards/results. `notebook_views.py` deliberately re-exports notebook entry points; an import there is not necessarily unused. |

The current separation is useful for submission: the solver and benchmark
semantics can be checked independently of provider transport and interactive
views. The remaining large plotting and core/evaluation test files are candidates
for later focused splits. Renaming the installed `src` package or reorganizing
artifact schemas would affect more interfaces than this cleanup needs.

The installed commands are declared in [`pyproject.toml`](../pyproject.toml):
`sample-grammar`, `analyze-grammar`, `generate`, `prepare`, `evaluate`,
`check-model`, and `optimize-score`. The former `decompose` command only invoked
an unimplemented adapter and has been removed. Its Python extension interface and
saved schemas remain for compatibility with existing artifacts.

## Names and compatibility

Config IDs come from YAML filenames; `config_name` is supplied by the loader.
A case-set selects frozen puzzles, while a run selects models and execution
settings for those puzzles. The two config types may share an ID such as
`sanity_check` without representing the same object.

`board_size` counts placed word segments, not occupied cells. The notebook label
“visible sequences” refers to that same count. A `reference_move` is a general
term: historical version-1 artifacts use `ground_truth_move` for a feasible
move, while version-2 artifacts use `optimal_move` and `optimal_score` for a
certified optimum. Historical field names and notebook selection defaults are
retained so old artifacts and saved calls still work.

`attempt_has_valid_response` refers to provider completion, not move legality.
An invalid move can therefore be a final evaluated attempt. This distinction
controls whether rerunning an evaluation sends another provider request.

## Regression evidence

| Tests | What they protect |
|---|---|
| [`test_core.py`](../tests/test_core.py), [`test_optimality.py`](../tests/test_optimality.py) | Move legality, scoring, generation, and optimal scores checked against independent exhaustive enumeration. |
| [`test_generation_cache.py`](../tests/test_generation_cache.py) | Slot enumeration and move results against the frozen uncached enumerator, including cache lifetime. |
| [`test_preparation_parallel.py`](../tests/test_preparation_parallel.py) | Serial/spawn equivalence, hash-seed independence, exact serialized bytes, interruption, worker failure, and resume. |
| [`test_evaluation.py`](../tests/test_evaluation.py), [`test_result_aggregation.py`](../tests/test_result_aggregation.py) | Frozen cases, concurrency, retries, resumability, and result denominators. |
| [`test_providers.py`](../tests/test_providers.py), [`test_reasoning_config.py`](../tests/test_reasoning_config.py) | Provider dispatch, request schemas, defaults, and reasoning settings using fixed profiles. |
| [`test_notebook_runs.py`](../tests/test_notebook_runs.py), overview/catalog tests | Saved and mocked responses, presentation, and artifact selection. |
| [`test_cli.py`](../tests/test_cli.py), [`test_repository_configs.py`](../tests/test_repository_configs.py) | Installed entry points, required arguments, the local generation workflow, and references between checked-in recipes. |
| [`test_scenario_compatibility.py`](../tests/test_scenario_compatibility.py) | Historical scenario round trips and rejection of incomplete optimality certificates. |

[`tests/support.py`](../tests/support.py) owns the small test recipes and model
profiles. The [generation reference](../tests/fixtures/generation_reference.json)
is stored as plain JSON so it is visible in source diffs and included alongside
the test code. It includes its source revision and was captured before the
initial cleanup. Only temporary paths are normalized; moves,
racks, scores, search logs, and slot domains remain comparison targets. A changed
reference should be reviewed as a behavioral change rather than regenerated
merely to make a failing test pass.
