# Evaluation Case Interface

## EvaluationCase

`EvaluationCase` is the shared input for full-puzzle evaluation and decomposition. It is a versioned snapshot with no unresolved YAML inheritance.

Conceptual structure:

```json
{
  "schema_version": 1,
  "case_id": "3g_3b_lmh.low.r00.g00.b00",
  "case_set": "3g_3b_lmh",
  "tier": "low",
  "sampling_round": 0,
  "grammar_sample_index": 0,
  "board_sample_index": 0,
  "seeds": {
    "grammar_requested": 123,
    "grammar_used": 124,
    "board": 456
  },
  "parameters": {
    "grammar": {},
    "generation": {},
    "board_depth": 20
  },
  "grammar": {},
  "board": {},
  "rack": [],
  "ground_truth_move": {},
  "provenance": {
    "grammar_artifact": "...",
    "scenario_artifact": "...",
    "grammar_sha256": "...",
    "scenario_sha256": "...",
    "case_set_config_sha256": "...",
    "git_revision": "..."
  }
}
```

The board and rack describe the exact input before the ground-truth move. The grammar is embedded completely so that later modification or deletion of the grammar file cannot change the case.

## Full-Puzzle Runner

The full-puzzle runner combines the case with:

- a model profile,
- a language representation,
- the fixed board and rack representations.

It produces the prompt, provider response, parsed move, and granular evaluation. The case itself remains unchanged.

## DecompositionRequest

A `DecompositionRequest` contains:

```json
{
  "schema_version": 1,
  "request_id": "...",
  "case": {},
  "failed_attempt": {},
  "requested_at": "..."
}
```

This allows decomposition to be integrated either in-process through a Python protocol or out-of-process through JSON. The interface knows no YAML paths and does not need to reconstruct scenarios.

## Python Protocol

The adapter exposes an interface equivalent to:

```python
class DecompositionAdapter(Protocol):
    async def decompose(
        self,
        request: DecompositionRequest,
    ) -> DecompositionResult: ...
```

The initial stub returns `not_implemented`. Future adapters may create their own prompts or multiple subtasks, but always receive the same case snapshot as the original evaluation.

Prepare writes JSON Schemas derived from the Pydantic models to `outputs/evaluation/<case-set>/schemas/`. External implementations can validate `EvaluationCase`, `DecompositionRequest`, and `DecompositionResult` without importing this Python package.

Internally, `case_snapshot.py` constructs the snapshot from already resolved grammar and scenario contexts. It knows neither case-set YAMLs nor provider access, preserving an explicit boundary between preparation, evaluation, and decomposition.
