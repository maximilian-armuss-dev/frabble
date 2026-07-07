# Evaluation Configuration

All configuration types described here follow the same filename-based loading rule. The shared loader lives in `src/configuration.py`; domain-specific Pydantic models and semantic validation remain in their grammar, generator, and evaluation modules.

A config ID is always a name without a parent path or `.yaml` suffix. `config_name` is derived from the filename stem and must not appear in human-maintained YAML files.

## Standalone Grammar Configs

Grammar configs live under `config/grammars/`. The filename without `.yaml` determines the grammar ID:

```bash
uv run sample-grammar --config evaluation_base_grammar
```

```yaml
alphabet_size: 5
k: 3
min_word_length: 3
seed: 42
alphabet_case: upper
forbidden_fraction: 0.4
auto_resample:
  enabled: true
  max_attempts: 20
  perron_min: 1.1
  perron_max: 50.0
  resample_length_min: 3
  resample_length_max: 7
  min_word_count: 20
show_stats: true
```

The default output is `outputs/grammars/<grammar-id>.json`. An optional `output_path` allows standalone experiments to use another location.

For case sets, `alphabet_size` and `k` are fixed globally by the
`grammar_config` referenced from the case set (e.g.
`config/grammars/evaluation_base_grammar.yaml`). `forbidden_fraction` is also
fixed globally in that grammar config. The default evaluation value is `0.4`.
Every grammar sampled for a case set shares these global grammar parameters.

## Standalone Generation Configs

Generation configs remain complete, independently executable generator descriptions:

```bash
uv run generate --config evaluation_base
```

```yaml
dimensions: 2
seed: 71
grammar: evaluation_base_grammar
initial_word_axis: 0
initial_word_length: 5
length_distribution:
  start: 3
  end: 7
top_anchor_count: 40
max_anchor_count: null
top_template_count: 200
target_witness_count: 200
scoring:
  anchor_centroid_weight: 1.0
  anchor_free_span_weight: 1.0
  template_centroid_weight: 1.0
  template_new_cell_bonus_weight: 2.0
  template_local_density_penalty_weight: 1.0
  template_domain_slack_weight: 1.0
additional_rack_noise: 0
include_search_logs: true
```

`additional_rack_noise` is optional and defaults to `0`. When set above `0`, that many random alphabet symbols are added as filler to each rack on top of the symbols the witness move actually needs.

`config_name` is omitted. `grammar` is an ID without a parent path or suffix and resolves to `outputs/grammars/<grammar>.json`. External files can instead be selected with `grammar_path`; both fields cannot be set simultaneously.

The default output is `outputs/scenarios/<generation-id>.json`. `output_path` remains an optional override. All search budgets, heuristics, and scoring weights remain part of the standalone config.

## Case-Set Configs

Case-set configs live under `config/evaluation/case_sets/` and define the
board sizes to prepare:

```yaml
generation_config: evaluation_base
grammar_config: evaluation_base_grammar
root_seed: 42
sampling_rounds: 5
board_sizes:
  - 10
  - 50
  - 150
  - 400
```

`generation_config` and `grammar_config` reference complete standalone configs.
`board_sizes` contains the number of witness transitions already applied to the
board shown to the model. Preparing size `50` therefore generates `51` witness
transitions: 50 to reconstruct the visible board and one ground-truth move to
solve.

Every `(board_size, sampling_round)` pair samples a new grammar and generates a
new board from its own deterministic seed. Smaller sizes are not sliced out of
larger generated boards.

`sampling_rounds` creates additional independent versions per selected board
size. Four board sizes and five rounds produce `4 * 5 = 20` grammars, boards,
and evaluation cases.

## Run Configs

Run configs live under `config/evaluation/runs/`:

```yaml
case_set: 5r_10-50-150-400

models:
  gpt-5-mini: [50, 400]
  gpt-5: [all]

execution:
  max_concurrency: 10
  max_concurrency_per_model: 2
  max_retries: 5
```

`models` maps each model profile from `config/model_configs.yaml` to the board
sizes it should process. `[all]` selects every prepared board size for that
model.

The language representation is fixed to `forbidden-snippets`.
Every evaluation call uses the native `xhigh` reasoning effort value,
which is persisted in the job and attempt artifacts.
Interactive notebook calls pass their selected provider-native effort value
directly through LiteLLM or the OpenRouter SDK.

`max_concurrency` limits all active provider calls. The optional
`max_concurrency_per_model` additionally limits active calls sharing one model
profile. This is useful for OpenRouter runs because upstream capacity and rate
limits remain model-specific.

Model targets use a backend-qualified API ID. For example,
`openrouter/google/gemini-3.1-pro-preview` selects the direct OpenRouter SDK
and sends `google/gemini-3.1-pro-preview` as its model ID. No separate backend
or manually maintained model revision is configured.

`config/model_configs.yaml` defines shared request settings once:

```yaml
defaults:
  temperature: 1
  max_completion_tokens: 32384
  timeout_seconds: 900
```

Profiles inherit these values. OpenRouter omits temperature at the adapter
boundary and sends the shared completion limit as `max_tokens`, while LiteLLM
receives `temperature` and `max_completion_tokens` directly. OpenRouter
profiles pin a provider that supports every requested parameter.

Board and rack representations do not appear in the run config while only one implementation exists for each. Every allowed board-size and model-profile combination becomes a separate job.

There is intentionally no `repetitions` key for resampling. New instances are created through `sampling_rounds` in the case set. Repeated model calls on the exact same case may later be introduced as a separate execution dimension.
