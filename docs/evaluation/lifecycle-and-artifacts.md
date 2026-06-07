# Lifecycle und Artefakte

## Prepare

```bash
uv run prepare --config screening_v1
```

Prepare:

1. lädt und validiert das Case Set,
2. expandiert Sampling-Runden, Tiers und Sample-Indizes,
3. sampelt Grammarparameter und Grammars,
4. sampelt Boardparameter und generiert Szenarien,
5. rekonstruiert den Boardzustand am `board_depth`,
6. materialisiert einen unveränderlichen Evaluation-Case,
7. aktualisiert das Prepare-Manifest atomar.

Intern bleibt `prepare.py` dabei der kleine Einstiegspunkt.
`case_preparation.py` orchestriert die Materialisierung,
`case_sampling.py` enthält das deterministische Sampling,
`case_snapshot.py` baut den gemeinsamen Case-Snapshot und
`preparation_artifacts.py` besitzt den Manifest-Lifecycle. Die genaue
Aufteilung ist in [architecture.md](architecture.md) beschrieben.

Für einen Case mit `board_depth = n` erzeugt der aufgelöste Generator
mindestens `n + 1` Witness-Transitionen. Das Modell sieht das Board nach den
Transitionen `0` bis `n - 1` und soll den Rack am Transition-Index `n`
verwenden.

Prepare ist modellunabhängig. Ein vorhandenes Artefakt wird nur
wiederverwendet, wenn ID, Config-Hash und Datei-Checksum zum Manifest passen.

## Evaluate

```bash
uv run evaluate --config gpt5_mini_all
```

Evaluate:

1. lädt die Run-Config und das referenzierte Prepare-Manifest,
2. filtert Cases nach Tier,
3. expandiert Modelle und Sprachrepräsentationen,
4. erzeugt stabile Job-IDs,
5. mischt wartende Jobs deterministisch,
6. führt sie mit dem asynchronen Concurrency-Window aus,
7. persistiert jedes finale Job-Ergebnis unmittelbar nach der
   Retry-Sequenz,
8. schreibt Manifest und Zusammenfassung.

`runner.py` koordiniert diesen Ablauf. Jobexpansion, Providerausführung und
Run-Persistenz liegen getrennt in `jobs.py`, `job_execution.py` und
`run_artifacts.py`.

Ein fachlich ungültiger Modellzug ist ein abgeschlossener Evaluation-Versuch
mit `overall = false`. Transport-, Authentifizierungs- und Providerfehler sind
keine Modellfehler und werden separat klassifiziert.

## Decompose

```bash
uv run decompose --config gpt5_mini_all
```

Decompose verwendet dieselbe Run-Config. Es sucht den neuesten abgeschlossenen
Evaluation-Run mit demselben kanonischen Run-Config-Hash und verarbeitet dessen
fachlich fehlgeschlagene Versuche.

Der erste Adapter erzeugt versionierte `DecompositionRequest`-Artefakte und
antwortet mit `not_implemented`. Er führt keine LLM-Aufrufe aus. Die spätere
Implementierung kann das Python-Protokoll direkt implementieren oder die
JSON-Artefakte separat konsumieren.

## Resume

Jede Phase ist resumierbar:

- Prepare überspringt vollständige, hash-kompatible Grammars, Szenarien und
  Cases.
- Evaluate überspringt Jobs mit abgeschlossenem Attempt-Artefakt.
- Retrybare Providerfehler bleiben erneut ausführbar.
- Nicht-retrybare Infrastrukturfehler werden sichtbar im Run-Manifest
  festgehalten.
- Decompose überspringt bereits erzeugte Requests und Resultate.

Manifeste werden nach jedem abgeschlossenen Artefakt aktualisiert. Ein Abbruch
verliert damit höchstens den gerade aktiven Provideraufruf.

## Identitäten und Hashes

IDs werden aus stabilen fachlichen Komponenten gebildet:

- Grammar: Case Set, Tier, Sampling-Runde, Grammar-Index.
- Scenario und Case: Case Set, Tier, Sampling-Runde, Grammar-Index und
  Board-Index.
- Job: Case-ID, Modellprofil und Sprachrepräsentation.

Hashes werden aus kanonischem JSON mit sortierten Keys gebildet. Zeitstempel
und absolute lokale Pfade sind kein Bestandteil fachlicher Content-Hashes.
