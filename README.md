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

`--config generator_v1` loads `config/generation/generator_v1.yaml`, `--config generator_3d` loads the 3D variant. Missing or incomplete config values cause a hard error; there are no silent code defaults.

### 4. Visualize a generated 2D board

The notebook reads a generated scenario JSON, not a grammar JSON. The checked-in
`generator_v1` config and the 2D notebook already agree on the scenario path:

```bash
uv run generate --config generator_v1
```

Then run `visualization/visualize_2d.ipynb`, which loads
`outputs/generator_v1.json`.

### End-to-end run with a new 2D grammar

To use a newly sampled grammar without replacing the checked-in example, create
a generation config such as `config/generation/my_2d.yaml` from
`generator_v1.yaml` and change these fields:

```yaml
config_name: my_2d
grammar_path: outputs/grammars/my_2d_grammar.json
output_path: outputs/my_2d.json
```

Sample the grammar and generate its scenario:

```bash
uv run sample-grammar --name my_2d_grammar --alphabet-size 5 --k 3 --seed 42 --show-stats
uv run analyze-grammar outputs/grammars/my_2d_grammar.json --max-length 7
uv run generate --config my_2d
```

Finally, set `SCENARIO_PATH` in `visualization/visualize_2d.ipynb` to
`ROOT / "outputs" / "my_2d.json"` and run the notebook.

The current checked-in samples use `k = 3`. To run the older V1 convention
described in `docs/implementation/README.md` (`k = 2` while still rejecting
words shorter than length 3), sample with `--k 2 --min-word-length 3`.

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
- `llm/`: Prompt construction, model configuration from `.env` and `config/model_configs.yaml`, and the LiteLLM client.
- `tools/check_model.py`: Small CLI for validating individual or all model profiles.
- `prompts/`: System and user prompt templates.
- `config/grammar_configs.yaml`: Global defaults for SL grammar sampling.
- `config/generation/`: Per-run generator configs (dimensions, grammar path, target witness count, scoring weights, etc.).
- `config/model_configs.yaml`: Model matrix with LiteLLM model IDs and related config values.
