# Evaluation-Konfiguration

Alle hier beschriebenen Config-Arten folgen derselben filename-basierten
Laderegel. Der gemeinsame Loader liegt in `src/configuration.py`; die
fachlichen Pydantic-Modelle und Zusatzvalidierungen bleiben in den jeweiligen
Grammar-, Generator- und Evaluation-Modulen.

Eine Config-ID ist immer ein Name ohne Parent-Pfad und ohne `.yaml`-Suffix.
`config_name` wird aus dem Dateistamm abgeleitet und ist in allen
menschengepflegten YAML-Dateien ungültig.

## Standalone Grammar-Configs

Grammar-Configs liegen unter `config/grammars/`. Der Dateiname ohne `.yaml`
bestimmt die Grammar-ID:

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

Standardoutput ist `outputs/grammars/<grammar-id>.json`. Ein optionales
`output_path` erlaubt für Standalone-Experimente einen abweichenden Pfad.

## Standalone Generation-Configs

Generation-Configs bleiben vollständige, einzeln ausführbare
Generatorbeschreibungen:

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
additional_rack_noise: 1
include_search_logs: true
```

`config_name` entfällt. `grammar` ist eine ID ohne Parent-Pfad oder Suffix und
wird nach `outputs/grammars/<grammar>.json` aufgelöst. Für externe Dateien
kann alternativ `grammar_path` gesetzt werden. Beide Felder gleichzeitig sind
ungültig.

Standardoutput ist `outputs/scenarios/<generation-id>.json`. `output_path`
bleibt ein optionaler Override. Alle Suchbudgets, Heuristiken und
Scoring-Gewichte bleiben Teil der Standalone-Config.

## Case-Set-Configs

Case-Set-Configs liegen unter `config/evaluation/case_sets/`.

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
    additional_rack_noise: {min: 0, max: 1}
    alphabet_size: 3
    forbidden_fraction: {min: 0.10, max: 0.20}
    k: 2

  medium:
    dimensions: 3
    board_depth: {min: 54, max: 102}
    additional_rack_noise: {min: 2, max: 3}
    alphabet_size: 4
    forbidden_fraction: {min: 0.20, max: 0.30}
    k: 2

  high:
    dimensions: 4
    board_depth: {min: 103, max: 151}
    additional_rack_noise: {min: 4, max: 5}
    alphabet_size: 5
    forbidden_fraction: {min: 0.30, max: 0.40}
    k: 3

  stress:
    dimensions: 5
    board_depth: {min: 152, max: 200}
    additional_rack_noise: {min: 6, max: 7}
    alphabet_size: 6
    forbidden_fraction: {min: 0.40, max: 0.50}
    k: 4
```

`generation_config` und `grammar_config` referenzieren vollständige
Standalone-Configs. Das Case Set überschreibt nur IDs, Seeds, Outputs und die
experimentell skalierten Achsen.

Ein Achsenwert ist entweder ein fester Scalar oder ein Intervall mit `min` und
`max`. Intervalle werden mit einer begrenzten Normalverteilung gesampelt:

- Mittelwert: Intervallmitte.
- Standardabweichung: Intervallbreite geteilt durch sechs.
- Ziehungen außerhalb des Intervalls werden wiederholt.
- Integerfelder werden gerundet und abschließend begrenzt.

Grammarparameter werden pro Grammar-Sample gezogen. Boardparameter werden pro
Board-Sample gezogen.

`sampling_rounds` erzeugt vollständig neue Parameter, Grammars und Boards. Bei
vier Tiers, einer Runde, drei Grammar-Samples und zehn Boards entstehen
`4 * 1 * 3 * 10 = 120` Cases.

## Run-Configs

Run-Configs liegen unter `config/evaluation/runs/`:

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

`models` bildet jeden Modellprofilnamen aus `config/model_configs.yaml` auf
die Complexity-Tiers ab, die dieses Modell bearbeiten soll. `[all]` wählt
alle vorbereiteten Tiers für genau dieses Modell.
`language_representations` akzeptiert eine Liste oder den Wert `all`.
`reasoning_effort` gilt für alle Modellaufrufe des Runs, wird explizit an
LiteLLM übergeben und ist Teil des Run-Config-Hashes. Modellprofile enthalten
deshalb keine Reasoning-Einstellung.

Board- und Rack-Repräsentationen erscheinen nicht in der Run-Config, solange
jeweils nur eine Implementierung existiert. Jede zugelassene Kombination aus
Case-Tier, Modellprofil und Sprachrepräsentation ist ein eigener Job.

Es gibt absichtlich keinen `repetitions`-Key für erneutes Sampling. Neue
Instanzen werden durch `sampling_rounds` im Case Set erzeugt. Wiederholte
Modellaufrufe auf exakt demselben Case können später als separate
Ausführungsdimension eingeführt werden.
