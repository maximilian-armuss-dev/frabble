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
