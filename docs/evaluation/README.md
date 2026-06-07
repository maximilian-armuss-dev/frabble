# Evaluation

Die Evaluation besteht aus drei getrennten Phasen:

1. `prepare` erzeugt reproduzierbare Grammars, Szenarien und unveränderliche
   Evaluation-Cases.
2. `evaluate` führt ausgewählte Cases gegen ausgewählte Modellprofile und
   Sprachrepräsentationen aus.
3. `decompose` übergibt fehlgeschlagene Evaluation-Versuche an eine gemeinsame
   Decomposition-Schnittstelle.

Diese Trennung verhindert, dass LLM-Aufrufe während eines Runs neue
Testinstanzen erzeugen. Ein vorbereiteter Case kann damit zwischen Modellen,
Promptrepräsentationen und späteren Decomposition-Verfahren exakt verglichen
werden.

## Konfiguration und Artefakte

Unter `config/` liegen ausschließlich von Menschen gepflegte YAML-Dateien:

```text
config/
├── grammars/
├── generation/
├── evaluation/
│   ├── case_sets/
│   └── runs/
└── model_configs.yaml
```

Alle generierten JSON-Dateien liegen unter `outputs/`:

```text
outputs/evaluation/<case-set>/
├── prepare-manifest.json
├── results-index.json
├── grammars/
├── scenarios/
├── cases/
├── schemas/
└── runs/<run-id>/
    ├── run-manifest.json
    ├── attempts/
    ├── summary.json
    ├── aggregate.json
    ├── results.csv
    └── decomposition/
```

`summary.json` enthält die kompakte Gesamt-, Tier-, Modell- und
Fehlerübersicht. `aggregate.json` speichert die vollständige Gruppierung nach
Tier, Modell und Sprachrepräsentation sowie Ergebnisse pro Grammar-Sample.
`results.csv` stellt dieselben Metriken im Long-Format für externe Analysen
bereit. `visualization/inspect_evaluation.ipynb` visualisiert Passraten,
primäre Fehlerklassen, die Robustheit zwischen Grammar-Samples sowie
durchschnittliche Token-Nutzung und LLM-Laufzeit.

`results-index.json` ist der persistente, run-übergreifende Datenpool eines
Case-Sets. Er wird nach vollständigen Runs und bei Bedarf beim Laden des
Notebooks aktualisiert. Für jede Kombination aus Case, Modell,
Sprachrepräsentation und Reasoning-Effort bleibt der Attempt aus dem neuesten
abgeschlossenen Run erhalten. Mit `RUN_ID = None` verwendet das Notebook diesen
Pool; eine konkrete Run-ID lädt weiterhin nur den angegebenen Einzelrun.

Überlappende
Constraint-Fehler bleiben als Diagnosewerte in `aggregate.json` erhalten.

Eine Case-Set-Config definiert die stabile Versuchsmatrix und das
reproduzierbare Sampling. Eine Run-Config ordnet Modellprofilen Tiers zu und
wählt Sprachrepräsentationen sowie den gemeinsamen Reasoning-Effort.

## Zentrale Begriffe

- **Sampling round**: Eine vollständig neue Ziehung aller variablen Parameter,
  Grammars und Boards. Eine weitere Runde erzeugt neue Cases, nicht weitere
  LLM-Aufrufe auf demselben Case.
- **Grammar sample**: Eine unabhängig gesampelte Sprache innerhalb eines Tiers.
  Mehrere Grammar-Samples verhindern, dass ein zufälliger Sprachausreißer ein
  komplettes Tier bestimmt.
- **Board sample**: Ein unabhängiger Generatorlauf mit eigenem Seed für eine
  konkrete Grammar.
- **Board depth**: Anzahl bereits ausgeführter Witness-Moves im Boardzustand,
  den das Modell sieht. Der zu lösende Move liegt an diesem Transition-Index.
- **Evaluation case**: Vollständiger Snapshot von Board, Rack, Grammar,
  Ground-Truth-Move, Parametern, Seeds und Herkunft.
- **Evaluation job**: Kombination aus Evaluation-Case, Modellprofil und
  Sprachrepräsentation.

## Reproduzierbarkeit

Alle Zufallsentscheidungen werden deterministisch aus der Case-Set-ID, dem
Root-Seed, Tier, Sampling-Runde und Sample-Indizes abgeleitet. Prepare schreibt
die angeforderten und tatsächlich verwendeten Seeds sowie Content-Hashes in
das Manifest.

Ein Case ist nach der Materialisierung unabhängig von späteren Änderungen an
YAML-Dateien oder Quellartefakten. Evaluation und Decomposition verwenden
denselben Snapshot.

## Dokumente

- [configuration.md](configuration.md): Standalone-, Case-Set- und Run-Configs.
- [architecture.md](architecture.md): Interne Modulgrenzen,
  Verantwortlichkeiten und Erweiterungspunkte.
- [lifecycle-and-artifacts.md](lifecycle-and-artifacts.md): Commands,
  Verzeichnisstruktur, Resume und Fehlermodell.
- [asynchronous-execution.md](asynchronous-execution.md): Concurrency-Window,
  Cooldowns und Retry-Verhalten.
- [evaluation-case-interface.md](evaluation-case-interface.md): Gemeinsames
  Datenmodell für Evaluation und Decomposition.
