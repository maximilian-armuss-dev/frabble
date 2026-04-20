# LLM Scrabble Bench Prototype

Minimaler Prototyp für ein Scrabble-artiges LLM-Environment mit formaler Sprache, DFA-Validator, Prompt-Template, Token-Scoring und optionalem OpenAI-SDK-Call.

## Setup

```bash
uv sync
```

Für einen echten Modell-Call:

```bash
export OPENAI_API_KEY="sk-..."
export OPENAI_MODEL="gpt-5.4"
export OPENAI_REASONING_EFFORT="low"  # optional

uv run scrabble-prototype --call-model
```

Ohne API-Key kann der lokale Oracle-/Validator-Loop laufen:

```bash
uv run scrabble-prototype --dry-run --show-prompt
uv run python -m unittest discover -s tests
```

## Was der Prototyp macht

- Definiert eine kleine formale Sprache über dem Alphabet `{A, B, C}`.
- Nutzt einen schleifenhaltigen DFA für die Sprache `A+ B A* C`.
- Generiert einen simplen 5x5-Boardstate mit einem vorhandenen Anker-Token.
- Sampelt ein Rack aus einer Häufigkeitsverteilung der akzeptierten Wörter.
- Berechnet Token-Scores aus inverser Token-Häufigkeit.
- Enumeriert alle legalen Züge und bestimmt das lokale Optimum.
- Baut ein Prompt-Template mit Grammatik, Board, Rack, Scoring und Output-Schema.
- Validiert die Modellantwort als JSON-Zug.
