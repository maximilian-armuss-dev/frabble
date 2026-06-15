# LLM Scrabble Bench

A formal-language Scrabble-style LLM benchmark with strictly-local grammars, sparse n-dimensional boards, a local slot CSP, and deterministic witness generation.

## Setup

```bash
uv sync
cp .env.example .env
```

Set the provider key required by the model profiles you plan to use. OpenRouter
profiles use `OPENROUTER_API_KEY`; `OPENROUTER_API_BASE` is optional and
defaults to `https://openrouter.ai/api/v1`.

## Workflow

There are three configuration layers:

- `config/grammars/<name>.yaml` fully describes one reproducible grammar sample.
- `config/generation/<name>.yaml` controls a standalone board/scenario run and
  selects a sampled grammar through its ID.
- `config/evaluation/` defines reusable case sets and concrete model runs.

### 1. Sample a grammar

Sample a random strictly-local (SL_k) grammar and save it to `outputs/grammars/<name>.json`:

```bash
uv run sample-grammar --config generator_v1_grammar
```

The filename stem is the grammar ID and the default output name. For example,
`config/grammars/generator_v1_grammar.yaml` produces
`outputs/grammars/generator_v1_grammar.json`. The YAML contains all alphabet,
SL_k, seed, forbidden-fraction, and auto-resampling parameters. An optional
`output_path` overrides the conventional output location.

### 2. Analyse a grammar

Inspect the Perron eigenvalue (language growth rate) and the exact word count at each length:

```bash
uv run analyze-grammar generator_v1_grammar --max-length 10
```

An explicit JSON path is also accepted.

### 3. Generate scenarios

Generator configurations live under `config/generation/`. The YAML file is the single source of truth; the CLI only takes the config name.

Each config references a pre-sampled grammar by ID:

```yaml
grammar: generator_v1_grammar
```

```bash
uv run generate --config evaluation_base
```

`--config generator_v1` loads `config/generation/generator_v1.yaml` and writes
`outputs/scenarios/generator_v1.json` by convention. `config_name` is derived
from the filename. All generator budgets, length ranges, scoring weights, rack
noise, and search-log settings remain explicit YAML fields. `output_path` and
an external `grammar_path` are optional overrides.

### 4. Visualize generated boards and moves

The scenario notebook animates a generated 2D scenario JSON:

```bash
uv run generate --config generator_v1
```

Then run `visualization/inspect_scenario.ipynb`, which loads
`outputs/scenarios/generator_v1.json` by default.

Move inspection is always rendered as 2D axis-pair plots. In
`visualization/inspect_llm_run.ipynb`, a move along axis `a` produces one plot
for every pair `(a, b)` where `b != a`. For example, a 4D move along axis 0
produces `(0, 1)`, `(0, 2)`, and `(0, 3)` automatically.

Move tiles are light blue when newly placed, light green when they overlap an
equal existing symbol, and light red when they conflict with an existing
symbol.

### End-to-end run with a new 2D grammar

To use a newly sampled grammar, create `config/grammars/my_2d_grammar.yaml` and
a generation config such as `config/generation/my_2d.yaml`. The latter only
needs to refer to the grammar ID:

```yaml
grammar: my_2d_grammar
```

Sample the grammar and generate its scenario:

```bash
uv run sample-grammar --config my_2d_grammar
uv run analyze-grammar my_2d_grammar --max-length 7
uv run generate --config my_2d
```

Finally, set `SCENARIO_NAME` in `visualization/inspect_scenario.ipynb` to
`"my_2d"` and run the notebook.

The current checked-in samples use `k = 3`. To run the older V1 convention,
set `k: 2` and `min_word_length: 3` in the grammar YAML.

### 5. Run a scenario against an LLM

Use `visualization/inspect_llm_run.ipynb` for individual scenario runs. Its
configuration cell selects the scenario, transition, model profile, and
`REASONING_EFFORT`. Prompt inspection happens before the explicit model-call
cell. Completed logs are written to `outputs/llm-runs/`.

The log file contains a granular evaluation breakdown:

| Field | Meaning |
|---|---|
| `overall` | All constraints satisfied |
| `parse_ok` | Response parsed as valid JSON move |
| `sequence_valid` | Sequence accepted by the formal language |
| `min_length_fulfilled` | Sequence meets minimum word length |
| `spatial_valid` | No conflicts with existing board tiles |
| `overlap_valid` | Move touches at least one existing tile |
| `no_word_extension` | Move does not extend an existing valid sequence |
| `cross_words_valid` | All cross-words formed are accepted by the language |
| `rack_symbols_used` | Count of new tiles drawn from the rack |
| `rack_usage_ratio` | `rack_symbols_used / rack_size` |

### 6. Prepare and run an evaluation

Case-set configs define reproducible complexity tiers and sampling:

```bash
uv run prepare --config 1g_1b_lmh
```

Use `--clean` to delete the complete existing case-set output, including old
evaluation runs, before preparing it again:

```bash
uv run prepare --config 1g_1b_lmh --clean
```

Run configs select model profiles with their respective prepared tiers and
language representations. Evaluation calls always use the native `xhigh`
reasoning effort:

```bash
uv run evaluate --config or_all_lmh
uv run decompose --config or_all_lmh
```

`evaluate` uses an asynchronous global request window, retries transient
failures with rate-limit-aware backoff, persists every completed attempt
immediately, and resumes incomplete runs. `decompose` currently materializes
failed-case requests through a stub adapter without making another LLM call.
Prepare also writes portable JSON Schemas for the shared case and
decomposition interfaces under the case-set output directory.

The complete design is documented under [`docs/evaluation/`](docs/evaluation/README.md).

## Tests

```bash
uv run python -m unittest discover -s tests -q
```

## Code Structure

- `domain/`: Core data types — sparse board, moves, segments, templates, and witness types.
- `formal/`: Strictly-local language definition, OR-Tools slot CSP, response parsing, and move validation.
- `formal/grammar/`: Config-driven SL grammar sampling, DFA construction, Perron analysis, serialization, and CLI entry points.
- `generator/`: Strict YAML config loader, candidate ranking, generation engine, scenario codec, file I/O, and board reconstruction.
- `evaluation/`: Thin prepare/evaluate/decompose orchestrators with separate
  modules for deterministic sampling, case snapshots, job execution,
  manifests, run artifacts, and decomposition handoff.
- `configuration.py`: Shared filename-based YAML loading; domain-specific
  config schemas remain in their owning packages.
- `benchmark/`: Board scoring helpers.
- `llm/`: Prompt construction, provider configuration from `.env` and `config/model_configs.yaml`, LiteLLM client, and granular move evaluation.
- `tools/check_model.py`: Small CLI for validating individual or all model profiles.
- `prompts/`: System and user prompt templates.
- `config/grammars/`: Complete standalone grammar sampling configs.
- `config/generation/`: Per-run generator configs (dimensions, grammar reference, target witness count, scoring weights, etc.).
- `config/evaluation/`: Human-maintained case-set, tier, and run configs.
- `config/evaluation/tiers/`: Reusable tier sets that jointly define `low`,
  `medium`, `high`, and `stress` for a particular experimental scale.
- `config/model_configs.yaml`: Model matrix with LiteLLM model IDs and related config values.

OpenRouter profiles are prefixed with `openrouter_`. They use the official
OpenRouter Python SDK directly rather than LiteLLM, so no compatibility layer
rewrites the request. Each profile pins a provider, disables fallbacks,
and requires all request parameters. The YAML stores only the provider slug;
the routing invariants are enforced by the adapter. Reasoning is not part of
the model profile. A combined model target such as
`openrouter/google/gemini-3.1-pro-preview` selects the OpenRouter backend; the
remaining `google/gemini-3.1-pro-preview` is sent unchanged as the API model ID.
Shared request settings such as temperature, completion-token limit, and
timeout live once in the top-level `defaults` block. OpenRouter deliberately
omits temperature from its requests; LiteLLM receives the configured default.

The frontier run config is
`config/evaluation/runs/openrouter_frontier_all.yaml`. Evaluation always
sends the provider-native `xhigh` value and persists the exact routing and
reasoning request settings in each attempt artifact. Interactive notebook
calls pass their selected reasoning value directly to the active SDK.
