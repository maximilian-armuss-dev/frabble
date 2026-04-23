# LLM Scrabble Bench Prototype

Minimaler Prototyp für ein Scrabble-artiges LLM-Environment mit formaler Sprache, DFA-Validator, Prompt-Template, Token-Scoring und optionalem Modell-Call über [litellm](https://github.com/BerriAI/litellm) (unterstützt OpenAI, Anthropic, Google, Cohere u.v.m.).

## Setup

```bash
uv sync
```

Für einen echten Modell-Call:

```bash
cp .env.example .env
# In .env das aktive Profil (LLM_MODEL_NAME) und die benötigten Provider-Keys setzen.
# Die Modellprofile selbst stehen in model_configs.yaml.

uv run scrabble-prototype --call-model
```

Alternativ können die Variablen weiterhin direkt in der Shell gesetzt werden. Shell-Variablen überschreiben Werte aus `.env`.

Ohne API-Key kann der lokale Oracle-/Validator-Loop laufen:

```bash
uv run scrabble-prototype --dry-run --show-prompt
uv run scrabble-prototype --dry-run --reference-max-length 5
uv run scrabble-prototype --call-model --model-name google_gemini_flash
uv run python -m unittest discover -s tests
```

Eine DFA-Grafik kann als PNG erzeugt werden:

```bash
uv run scrabble-prototype --dry-run --visualize-dfa outputs/demo-dfa.png
```

## Was der Prototyp macht

- Definiert eine kleine formale Sprache über dem Alphabet `{A, B, C}`.
- Nutzt einen schleifenhaltigen DFA für die Sprache `A+ B A* C`.
- Repräsentiert Boards als n-dimensionale NumPy-Arrays.
- Generiert einen simplen 5x5-Demo-Boardstate mit einem vorhandenen Anker-Token.
- Sampelt ein Rack aus einer Häufigkeitsverteilung einer endlichen Referenzmenge akzeptierter Wörter.
- Berechnet Token-Scores aus inverser Token-Häufigkeit.
- Enumeriert alle legalen Züge und bestimmt das lokale Optimum.
- Baut ein Prompt-Template mit Grammatik, Board, Rack, Scoring und Output-Schema.
- Validiert die Modellantwort als Pydantic-geprüften JSON-Zug mit `start`, `axis` und `tokens`.

## Code-Struktur

- `models.py`: Datenklassen für DFA, NumPy-basiertes Board, Move, Scenario und ValidationResult.
- `automata.py`: Demo-DFA und Enumeration akzeptierter Wörter bis zu einer Längengrenze.
- `board.py`: Aufbau des minimalen Demo-Boards.
- `scoring.py`: Häufigkeitsanalyse, Token-Scores und Optimum-Berechnung.
- `validation.py`: Move-Validator und Enumeration legaler Züge.
- `visualization.py`: Erzeugt DFA-Grafiken als PNG.
- `generation.py`: Szenario- und Rack-Generierung.
- `prompting.py`: Lädt und rendert Prompt-Templates.
- `prompts/`: System- und User-Prompt-Templates.
- `parsing.py`: JSON-Parsing der Modellantwort.
- `env.py`: Lädt `.env`, liest `model_configs.yaml` und stellt validierte Environment-/Modellzugriffe bereit.
- `model_configs.yaml`: Modellmatrix mit LiteLLM-Modell-ID und zugehörigen Konfigurationswerten.
- `llm_client.py`: Modell-Call via litellm mit direkter Parametergabe (`api_key`, `base_url`, `api_version`, `reasoning_effort`).
- `cli.py`: Kommandozeilen-Loop.
- `prototype.py`: Re-exportiert alle Public-Symbole.
