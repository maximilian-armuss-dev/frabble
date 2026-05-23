# LLM Scrabble Bench

V1-Implementierung für einen Scrabble-artigen LLM-Benchmark mit formaler Sprache, sparse Board, lokalem Slot-CSP und deterministischer Witness-Generierung.

## Setup

```bash
uv sync
```

## Szenarien generieren

Generator-Konfigurationen liegen unter `config/generation/`. Der fachliche Konfigurationsort ist die YAML-Datei; die CLI bleibt absichtlich dünn und nimmt nur den Confignamen entgegen.

```bash
uv run generate --config generator_v1
uv run generate --config generator_3d
```

`--config generator_v1` lädt `config/generation/generator_v1.yaml`, `--config generator_3d` lädt die 3D-Variante. Fehlende oder unvollständige Config-Werte führen zu einem harten Fehler; es gibt keine stillen Code-Defaults.

## Tests

```bash
uv run python -m unittest discover -s tests -q
```

### Sample a grammar

```bash
uv run sample-grammar --name my_grammar --alphabet-size 5 --k 3 --seed 42 --show-stats
```

The grammar is saved to `grammars/my_grammar.json`. Global defaults (Perron bounds, word-count window, DFA minimisation, etc.) are read from `config/grammar_configs.yaml`; any flag overrides just that one value for this run. All resolved parameters are written into the JSON for full traceability.

Key flags (all optional — unset flags fall back to `grammar_configs.yaml`):

```
--name TEXT                 Grammar name; file saved as grammars/<name>.json
--alphabet-size INT         Number of symbols (default: 5)
--k INT                     Forbidden pattern length (default: 3)
--forbidden-fraction FLOAT  Fraction of k-grams to forbid independently
--min-word-length INT       Minimum accepted word length (default: k)
--seed INT                  Base random seed (default: 42)
--alphabet-case upper|lower
--minimize-dfa / --no-minimize-dfa
--auto-resample / --no-auto-resample
--perron-min FLOAT          Minimum Perron eigenvalue for auto-resample
--perron-max FLOAT          Maximum Perron eigenvalue for auto-resample
--min-word-count INT        Min words in the resample length window
--show-stats                Print Perron eigenvalue and word-count spectrum
```

### Validate words against a grammar

```bash
uv run check-grammar grammars/my_grammar.json --word "ABCAB"
uv run check-grammar grammars/my_grammar.json --words-file wordlist.txt
```

### Analyse a grammar

```bash
uv run analyze-grammar grammars/my_grammar.json --max-length 10
```

Prints the Perron eigenvalue (growth rate of the language) and the exact word count at each length.

### Visualize a grammar's DFA

```bash
uv run visualize-grammar grammars/my_grammar.json
uv run visualize-grammar grammars/my_grammar.json --minimize-dfa
uv run visualize-grammar grammars/my_grammar.json --no-minimize-dfa
```

Renders the grammar's DFA as a PNG saved next to the grammar file. Without `--minimize-dfa` / `--no-minimize-dfa` the value from the saved grammar's config is used. Output paths:

- default / `--no-minimize-dfa`: `grammars/<name>_dfa.png`
- `--minimize-dfa`: `grammars/<name>_dfa_minimized.png`

### Use a grammar in a scenario

Pass `--grammar` to `scrabble-prototype` to replace the demo DFA:

```bash
uv run scrabble-prototype --dry-run --grammar grammars/my_grammar.json --show-prompt
```

## What The Prototype Does

- Defines a small formal language over the alphabet `{A, B, C}`.
- Uses a loop-capable DFA for the language `A+ B A* C`.
- Represents boards as n-dimensional NumPy arrays.
- Generates a simple 5x5 demo board state with one anchor token already placed.
- Samples a rack from the token-frequency distribution of a finite reference set of accepted words.
- Computes token scores from inverse token frequency.
- Enumerates all legal moves and determines the local optimum.
- Builds a prompt template with grammar, board, rack, scoring, and output schema.
- Validates the model response as a Pydantic-checked JSON move with `start`, `axis`, and `tokens`.

## Code Structure

- `domain/`: core data types, board helpers, and DFA visualization.
- `formal/`: automata logic, response parsing, and rule validation.
- `benchmark/`: scenario generation, prompt construction, and scoring.
- `llm/`: model configuration from `.env` and `model_configs.yaml`, plus the LiteLLM client.
- `tools/check_model.py`: minimal ping/pong CLI for validating one or all model profiles.
- `prompts/`: system and user prompt templates.
- `model_configs.yaml`: model matrix with LiteLLM model IDs and related config values.
- `cli.py`: command-line loop.
- `prototype.py`: re-exports all public symbols.

## Modellcheck

Der zusätzliche Modellcheck sendet nur einen minimalen Ping/Pong-Prompt an ein konfiguriertes Modell.

```bash
uv run check-model --model-name openai_gpt5_mini
uv run check-model --all
```

## Code-Struktur

- `domain/`: Sparse-Board, Moves, Segmente, Templates und Witness-Typen.
- `formal/`: Strictly-Local-Sprache, OR-Tools-Slot-CSP, Parsing und Validierung.
- `generator/`: strikter YAML-Config-Loader, Candidate-Ranking, Generationslauf, Scenario-Codec, Datei-I/O und Board-Rekonstruktion.
- `benchmark/`: Board-Scoring-Helfer.
- `llm/`: Prompt-Aufbau, Modellkonfiguration aus `.env` und `model_configs.yaml` sowie der LiteLLM-Client.
- `tools/check_model.py`: kleine CLI zum Prüfen einzelner oder aller Modellprofile.
- `prompts/`: System- und User-Prompt-Templates.
