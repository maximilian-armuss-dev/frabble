# LLM Scrabble Bench

A formal-language Scrabble-style LLM benchmark with strictly-local grammars, sparse n-dimensional boards, a local slot CSP, and deterministic witness generation.

## Setup

```bash
uv sync
```

## Workflow

There are two configuration layers:

- `config/grammar_configs.yaml` contains defaults used while sampling a grammar. Sampling produces a concrete, reproducible JSON grammar under `outputs/grammars/`.
- `config/generation/<name>.yaml` controls a board/scenario run and selects one
  sampled grammar through `grammar_path`.

### 1. Sample a grammar

Sample a random strictly-local (SL_k) grammar and save it to `outputs/grammars/<name>.json`:

```bash
uv run sample-grammar --name my_grammar --alphabet-size 5 --k 3 --seed 42 --show-stats
```

Global defaults (forbidden fraction, Perron bounds, word-count window, etc.) are read from `config/grammar_configs.yaml`. Any CLI flag overrides just that one value for the run. All resolved parameters are written into the JSON for full traceability.

Key flags (all optional — unset flags fall back to `config/grammar_configs.yaml`):

```
--name TEXT                  Grammar name; file saved as outputs/grammars/<name>.json
--output-dir PATH            Output directory (default: outputs/grammars/)
--alphabet-size INT          Number of symbols (default: 5)
--k INT                      Forbidden pattern length (default: 3)
--forbidden-fraction FLOAT   Fraction of k-grams to forbid independently
--min-word-length INT        Minimum accepted word length (default: k)
--seed INT                   Base random seed (default: 42)
--alphabet-case upper|lower
--auto-resample / --no-auto-resample
--max-attempts INT           Max resample attempts
--perron-min FLOAT           Minimum Perron eigenvalue for auto-resample
--perron-max FLOAT           Maximum Perron eigenvalue for auto-resample
--resample-length-min INT    Word-count window start length
--resample-length-max INT    Word-count window end length
--min-word-count INT         Min words in the resample length window
--show-stats                 Print Perron eigenvalue and word-count spectrum
```

### 2. Analyse a grammar

Inspect the Perron eigenvalue (language growth rate) and the exact word count at each length:

```bash
uv run analyze-grammar outputs/grammars/my_grammar.json --max-length 10
```

### 3. Generate scenarios

Generator configurations live under `config/generation/`. The YAML file is the single source of truth; the CLI only takes the config name.

Each config references a pre-sampled grammar via `grammar_path`. Generate the grammar first (step 1), then point the config at it.

```bash
uv run generate --config generator_v1
uv run generate --config generator_3d
```

`--config generator_v1` loads `config/generation/generator_v1.yaml`, `--config generator_3d` loads the 3D variant. A generation config may set any `dimensions >= 2`, including higher-dimensional scenarios. Missing or incomplete config values cause a hard error; there are no silent code defaults.

### 4. Visualize a generated 2D board

The notebook reads a generated scenario JSON, not a grammar JSON. The checked-in
`generator_v1` config and the 2D notebook already agree on the scenario path:

```bash
uv run generate --config generator_v1
```

Then run `visualization/visualize_2d.ipynb`, which loads
`outputs/scenarios/generator_v1.json`.

Use `visualization/visualize_3d.ipynb` for scenarios generated with
`dimensions: 3`. For higher-dimensional boards, choose two or three visible
axes and fix every remaining coordinate to render a slice:

```python
from visualization.board_figures import board_from_scenario_json, plot_board_3d

board = board_from_scenario_json("outputs/scenarios/my_7d.json")
plot_board_3d(
    board,
    axes=(0, 1, 2),
    slice_coords={3: 0, 4: 0, 5: 0, 6: 0},
)
```

`plot_board_2d` and `animate_scenario_2d` use the same `slice_coords`
argument, requiring one fixed coordinate for each axis not shown.

### End-to-end run with a new 2D grammar

To use a newly sampled grammar without replacing the checked-in example, create
a generation config such as `config/generation/my_2d.yaml` from
`generator_v1.yaml` and change these fields:

```yaml
config_name: my_2d
grammar_path: outputs/grammars/my_2d_grammar.json
output_path: outputs/scenarios/my_2d.json
```

Sample the grammar and generate its scenario:

```bash
uv run sample-grammar --name my_2d_grammar --alphabet-size 5 --k 3 --seed 42 --show-stats
uv run analyze-grammar outputs/grammars/my_2d_grammar.json --max-length 7
uv run generate --config my_2d
```

Finally, set `SCENARIO_NAME` in `visualization/inspect_scenario.ipynb` to
`"my_2d"` and run the notebook.

The current checked-in samples use `k = 3`. To run the older V1 convention
described in `docs/implementation/README.md` (`k = 2` while still rejecting
words shorter than length 3), sample with `--k 2 --min-word-length 3`.

### 4. Run a scenario against an LLM

Pick a generated scenario file and a transition index. The board is replayed up to that transition, and the model is asked to place a valid word using the rack from that step. Because the CSP solver found a solution at every step, a valid move is guaranteed to exist.

```bash
uv run run-scenario --scenario outputs/scenarios/generator_v1.json --transition 20 --model my_model
```

The model name must match a profile in `config/model_configs.yaml`. The run log (prompts, raw response, and evaluation) is written to `outputs/llm-runs/`.

Key flags:

```
--scenario PATH              Scenario JSON file produced by the generate step
--transition INT             Transition index N (0-indexed); board is populated with transitions 0..N-1
--model TEXT                 Model name from config/model_configs.yaml (not required with --dry-run)
--output-dir PATH            Output directory for run logs (default: outputs/llm-runs/)
--dry-run                    Build the prompt but skip the LLM call and do not write any output
--show-prompt                Print the system and user prompts before calling the LLM
--language-representer NAME  How to present the formal language (choices: forbidden-snippets [default], forbidden-snippets-production-rules, generic-production-rules)
--board-representer NAME     How to present the board (choices: coordinates-json [default])
--rack-representer NAME      How to present the rack (choices: symbol-json [default])
```

The representer names logged under `representers` in every run log identify which formatting was used. Passing an invalid name is rejected at startup with the list of valid choices.

To verify that scenario loading and prompt generation work without making an API call:

```bash
uv run run-scenario --scenario outputs/scenarios/generator_v1.json --transition 20 --dry-run
uv run run-scenario --scenario outputs/scenarios/generator_v1.json --transition 20 --dry-run --show-prompt
```

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

## Tests

```bash
uv run python -m unittest discover -s tests -q
```

## Code Structure

- `domain/`: Core data types — sparse board, moves, segments, templates, and witness types.
- `formal/`: Strictly-local language definition, OR-Tools slot CSP, response parsing, and move validation.
- `formal/grammar/`: SL grammar sampling, DFA construction, Perron analysis, serialization, and the `sample-grammar` / `analyze-grammar` CLI entry points.
- `generator/`: Strict YAML config loader, candidate ranking, generation engine, scenario codec, file I/O, and board reconstruction.
- `benchmark/`: Board scoring helpers.
- `llm/`: Prompt construction, model configuration from `.env` and `config/model_configs.yaml`, LiteLLM client, granular move evaluator (`evaluation.py`), and the `run-scenario` CLI entry point (`run_cli.py`).
- `tools/check_model.py`: Small CLI for validating individual or all model profiles.
- `prompts/`: System and user prompt templates.
- `config/grammar_configs.yaml`: Global defaults for SL grammar sampling.
- `config/generation/`: Per-run generator configs (dimensions, grammar path, target witness count, scoring weights, etc.).
- `config/model_configs.yaml`: Model matrix with LiteLLM model IDs and related config values.
