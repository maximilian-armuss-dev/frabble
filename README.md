# LLM Scrabble Bench

A formal-language Scrabble-style LLM benchmark with strictly-local grammars, sparse n-dimensional boards, a local slot CSP, and deterministic witness generation.

## Setup

```bash
uv sync
```

## Workflow

### 1. Sample a grammar

Sample a random strictly-local (SL_k) grammar and save it to `outputs/grammars/<name>.json`:

```bash
uv run sample-grammar --name my_grammar --alphabet-size 5 --k 3 --seed 42 --show-stats
```

Global defaults (Perron bounds, word-count window, DFA minimisation, etc.) are read from `config/grammar_configs.yaml`. Any CLI flag overrides just that one value for the run. All resolved parameters are written into the JSON for full traceability.

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

`--config generator_v1` loads `config/generation/generator_v1.yaml`, `--config generator_3d` loads the 3D variant. Missing or incomplete config values cause a hard error; there are no silent code defaults.

### 4. Run a scenario against an LLM

Pick a generated scenario file and a transition index. The board is replayed up to that transition, and the model is asked to place a valid word using the rack from that step. Because the CSP solver found a solution at every step, a valid move is guaranteed to exist.

```bash
uv run run-scenario --scenario outputs/generator_v1.json --transition 20 --model my_model
```

The model name must match a profile in `config/model_configs.yaml`. The run log (prompts, raw response, and evaluation) is written to `outputs/runs/`.

Key flags:

```
--scenario PATH       Scenario JSON file produced by the generate step
--transition INT      Transition index N (0-indexed); board is populated with transitions 0..N-1
--model TEXT          Model name from config/model_configs.yaml
--output-dir PATH     Output directory for run logs (default: outputs/runs/)
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
