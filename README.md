# LLM Scrabble Bench Prototype

Minimal prototype for a Scrabble-like LLM environment with a formal language, DFA validator, prompt templates, token scoring, and optional model calls through [litellm](https://github.com/BerriAI/litellm) (supporting OpenAI, Anthropic, Google, Cohere, and more).

## Setup

```bash
uv sync
```

For a real model call:

```bash
cp .env.example .env
# Set the active profile (LLM_MODEL_NAME) and the required provider keys in .env.
# Model profiles are defined in model_configs.yaml.

uv run scrabble-prototype --call-model
```

You can also set the variables directly in the shell. Shell variables override values from `.env`.

Without an API key, you can still run the local oracle/validator loop:

```bash
uv run scrabble-prototype --dry-run --show-prompt
uv run scrabble-prototype --dry-run --reference-max-length 5
uv run scrabble-prototype --call-model --model-name google_gemini_flash
uv run check-model --model-name openai_gpt5_mini
uv run check-model --all
uv run python -m unittest discover -s tests
```

A DFA visualization can be generated as a PNG:

```bash
uv run scrabble-prototype --dry-run --visualize-dfa outputs/demo-dfa.png
```

## Grammar Sampling

Instead of the hard-coded demo DFA, you can sample a random **Strictly Local (SL_k)** grammar and use it as the formal language for a scenario.

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

## Model Check

The additional CLI intentionally sends only a minimal ping/pong prompt to the selected model to keep token usage low.

```bash
uv run check-model --model-name openai_gpt5_mini
uv run check-model --all
```

The output shows the profile name, the concrete LiteLLM model, and the first 80 characters of the response or an error.
