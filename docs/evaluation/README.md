# Evaluation

The evaluation pipeline consists of three separate phases:

1. `prepare` creates reproducible grammars, scenarios, and immutable evaluation cases.
2. `evaluate` runs selected cases against selected model profiles and language representations.
3. `decompose` passes failed evaluation attempts to a shared decomposition interface.

This separation prevents LLM calls from generating new test instances during a run. A prepared case can therefore be compared exactly across models, prompt representations, and future decomposition methods.

## Configuration and Artifacts

Only human-maintained YAML files live under `config/`:

```text
config/
├── grammars/
├── generation/
├── evaluation/
│   ├── case_sets/
│   ├── runs/
│   └── tiers/
└── model_configs.yaml
```

All generated JSON files live under `outputs/`:

```text
outputs/evaluation/<case-set>/
├── prepare-manifest.json
├── grammars/
├── scenarios/
├── cases/
├── schemas/
└── runs/<run-id>/
    ├── run-manifest.json
    ├── attempts/
    ├── summary.json
    ├── aggregate.json
    ├── results.csv
    └── decomposition/
```

`summary.json` contains compact overall, tier, model, and failure summaries. `aggregate.json` stores the complete grouping by tier, model, and language representation, including per-grammar-sample results. `results.csv` exposes the same metrics in long format for external analysis.

`visualization/inspect_evaluation.ipynb` visualizes pass rates, primary failure classes, robustness across grammar samples, average token usage, and LLM runtime. Pass rate measures the formal validity of a move; `rack_usage_ratio` is aggregated separately as solution quality. Average request runtime includes final transport failures and timeouts.

The notebook accepts either a case-set name or a concrete run ID. A case-set
name selects its newest completed run. A run ID selects exactly that run,
independently of its case set. Cross-run aggregation is intentionally left to
explicit post-processing.

Overlapping constraint failures remain available as diagnostic values in `aggregate.json`.

A case-set config defines the stable experiment matrix and reproducible sampling. A run config maps model profiles to tiers and selects language representations. Evaluation reasoning is fixed to native `xhigh`.

## Core Terms

- **Sampling round**: A completely new draw of all variable parameters, grammars, and boards. Another round creates new cases, not additional LLM calls on the same case.
- **Grammar sample**: An independently sampled language within a tier. Multiple grammar samples prevent one accidental language outlier from determining an entire tier.
- **Board sample**: An independent generator run with its own seed for a specific grammar.
- **Board depth**: The number of witness moves already applied to the board state shown to the model. The move to solve is at this transition index.
- **Evaluation case**: A complete snapshot of the board, rack, grammar, ground-truth move, parameters, seeds, and provenance.
- **Evaluation job**: A combination of evaluation case, model profile, and language representation.

## Reproducibility

All random decisions are derived deterministically from the case-set ID, root seed, tier, sampling round, and sample indices. Prepare records the requested and actual seeds as well as content hashes in the manifest.

After materialization, a case is independent of later changes to YAML files or source artifacts. Evaluation and decomposition use the same snapshot.

## Documents

- [configuration.md](configuration.md): Standalone, case-set, and run configs.
- [architecture.md](architecture.md): Internal module boundaries, responsibilities, and extension points.
- [lifecycle-and-artifacts.md](lifecycle-and-artifacts.md): Commands, directory layout, resume behavior, and failure model.
- [asynchronous-execution.md](asynchronous-execution.md): Concurrency window, cooldowns, and retry behavior.
- [evaluation-case-interface.md](evaluation-case-interface.md): Shared data model for evaluation and decomposition.
