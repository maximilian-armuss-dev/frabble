# Evaluation Configuration

All configuration types described here follow the same filename-based loading rule. The shared loader lives in `src/configuration.py`; domain-specific Pydantic models and semantic validation remain in their grammar, generator, and evaluation modules.

A config ID is always a name without a parent path or `.yaml` suffix. `config_name` is derived from the filename stem and must not appear in human-maintained YAML files.

## Standalone Grammar Configs

Grammar configs live under `config/grammars/`. The filename without `.yaml` determines the grammar ID:

```bash
uv run sample-grammar --config generator_v1_grammar
```

```yaml
alphabet_size: 5
k: 3
min_word_length: 3
seed: 42
alphabet_case: upper
forbidden_fraction: 0.35
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

## Standalone Generation Configs

Generation configs remain complete, independently executable generator descriptions:

```bash
uv run generate --config generator_v1
```

```yaml
dimensions: 2
seed: 71
grammar: generator_v1_grammar
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

Case-set configs live under `config/evaluation/case_sets/`.

```yaml
generation_config: evaluation_base
grammar_config: evaluation_base
root_seed: 42

sampling_rounds: 1
grammar_samples_per_tier: 3
boards_per_grammar: 10

tiers:
  low:
    dimensions: 2
    board_depth: {min: 5, max: 53}
    alphabet_size: 3
    forbidden_fraction: {min: 0.10, max: 0.20}
    k: 2

  medium:
    dimensions: 3
    board_depth: {min: 54, max: 102}
    alphabet_size: 4
    forbidden_fraction: {min: 0.20, max: 0.30}
    k: 2

  high:
    dimensions: 4
    board_depth: {min: 103, max: 151}
    alphabet_size: 5
    forbidden_fraction: {min: 0.30, max: 0.40}
    k: 3

  stress:
    dimensions: 5
    board_depth: {min: 152, max: 200}
    alphabet_size: 6
    forbidden_fraction: {min: 0.40, max: 0.50}
    k: 4
```

`generation_config` and `grammar_config` reference complete standalone configs. The case set overrides only IDs, seeds, outputs, and experimentally scaled axes.

An axis value can be either a fixed scalar or an interval with `min` and `max`. Intervals are sampled with a bounded normal distribution:

- Mean: interval midpoint.
- Standard deviation: interval width divided by six.
- Values outside the interval are redrawn.
- Integer fields are rounded and finally clamped.

Grammar parameters are drawn per grammar sample. Board parameters are drawn per board sample.

`sampling_rounds` creates completely new parameters, grammars, and boards. Four tiers, one round, three grammar samples, and ten boards produce `4 * 1 * 3 * 10 = 120` cases.

## Run Configs

Run configs live under `config/evaluation/runs/`:

```yaml
case_set: screening_v1

models:
  gpt-5-mini: [low, medium]
  gpt-5: [high]

language_representations:
  - forbidden-snippets
  - generic-production-rules

reasoning_effort: low

execution:
  max_concurrency: 10
  max_retries: 5
```

`models` maps each model profile from `config/model_configs.yaml` to the complexity tiers it should process. `[all]` selects every prepared tier for that model.

`language_representations` accepts a list or `all`. `reasoning_effort` applies to every model call in the run, is passed explicitly to LiteLLM, and is part of the run-config hash. Model profiles therefore do not contain a reasoning setting.

Board and rack representations do not appear in the run config while only one implementation exists for each. Every allowed case-tier, model-profile, and language-representation combination becomes a separate job.

There is intentionally no `repetitions` key for resampling. New instances are created through `sampling_rounds` in the case set. Repeated model calls on the exact same case may later be introduced as a separate execution dimension.
