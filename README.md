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
