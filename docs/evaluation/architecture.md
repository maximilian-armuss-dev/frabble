# Interne Architektur

Die Evaluation-Pipeline ist nach fachlicher Verantwortung getrennt. Die
öffentlichen Einstiegspunkte bleiben klein und delegieren Sampling,
Providerzugriff und Artefaktverwaltung an eigene Module.

## Einstiegspunkte

`src/evaluation/cli.py` enthält ausschließlich die drei CLI-Adapter:

- `cmd_prepare`
- `cmd_evaluate`
- `cmd_decompose`

Die Adapter parsen `--config`, laden das passende Pydantic-Modell und rufen
den jeweiligen Anwendungsfall auf. Fachlogik und Dateizugriffe liegen nicht in
der CLI.

Die Anwendungsfälle sind:

```text
prepare.py        -> prepare_case_set(...)
runner.py         -> evaluate_run(...)
decomposition.py  -> decompose_run(...)
```

## Gemeinsames Config-Loading

`src/configuration.py` stellt mit `NamedYamlConfigSource` die gemeinsame
Infrastruktur für filename-basierte YAML-Configs bereit:

1. Config-IDs dürfen keinen Pfad oder Suffix enthalten.
2. `<config-id>.yaml` wird im fachlichen Config-Verzeichnis gesucht.
3. Die YAML-Wurzel muss ein Mapping sein.
4. `config_name` darf nicht in der YAML stehen.
5. Der Dateistamm wird vor der Pydantic-Validierung als `config_name`
   eingesetzt.

Die fachlichen Module definieren weiterhin ihre eigenen Schemas und
semantischen Regeln:

- `formal/grammar/config.py`: Grammar-Sampling
- `generator/config.py`: Szenariogenerierung und Grammar-Auflösung
- `evaluation/config.py`: Case Sets, Tiers und Evaluation-Runs

Die gemeinsame Quelle kennt keine Grammar-, Generator- oder
Evaluation-Parameter.

## Prepare

Der Prepare-Pfad ist in folgende Verantwortlichkeiten aufgeteilt:

### `prepare.py`

Composition Root des Anwendungsfalls. Das Modul:

- bestimmt das Output-Verzeichnis,
- berechnet den Case-Set-Config-Hash,
- lädt Basis-Grammar und Basis-Generator,
- initialisiert das Manifest,
- startet `CaseSetPreparer`.

### `case_preparation.py`

Orchestriert die Materialisierung eines Case Sets:

- iteriert Tiers, Sampling-Runden und Sample-Indizes,
- sampelt oder lädt Grammars,
- startet den Szenariogenerator,
- schreibt Cases,
- meldet Fortschritt und Fehler an das Manifest.

`PreparedGrammar`, `PreparedScenario` und `CaseCoordinates` transportieren
zusammengehörige Daten explizit, statt lange lose Parameterlisten oder Tupel
zu verwenden.

### `case_sampling.py`

Enthält deterministische, seiteneffektfreie Sampling- und
Config-Auflösung:

- Ableitung der Board-Seeds,
- Sampling der Boardparameter,
- Auflösung einer konkreten Grammar-Config,
- Auflösung einer konkreten Generator-Config,
- Bildung stabiler Grammar- und Case-IDs.

Dieses Modul schreibt keine Dateien und startet keinen Generator.

### `case_snapshot.py`

Rekonstruiert aus vorbereiteter Grammar und vorbereitetem Szenario den
unveränderlichen `EvaluationCase`. Hier wird die Grenze zwischen
Generatorartefakten und dem gemeinsamen Evaluation-/Decomposition-Interface
gezogen.

### `preparation_artifacts.py`

Besitzt den Prepare-Manifest-Lifecycle:

- Laden oder Erzeugen des Manifests,
- Hash- und Checksum-Prüfung vorhandener Artefakte,
- atomare Manifest-Updates,
- Fehleraufzeichnung,
- Schema-Ausgabe,
- Abschlussstatus.

## Evaluate

Der Evaluation-Pfad ist ebenfalls in Orchestrierung, Ausführung und
Persistenz getrennt.

### `runner.py`

Orchestriert einen Run:

- validiert das Prepare-Manifest,
- wählt oder erzeugt einen resumierbaren Run,
- baut und mischt wartende Jobs,
- erzeugt Semaphore, Cooldown-State und Tasks,
- persistiert Attempts,
- finalisiert Manifest und Summary.

Provider- und Retry-Details sind nicht Teil dieses Moduls.

### `jobs.py`

Expandiert eine Run-Config in `EvaluationJob`-Objekte. Das Modul besitzt:

- Tier-, Modell- und Repräsentationsauswahl,
- Auflösung der Case-Pfade,
- stabile Job-IDs.

### `job_execution.py`

Besitzt die Ausführung eines einzelnen Jobs:

- Promptbau,
- asynchroner LLM-Aufruf,
- Parsing und granulare Evaluation,
- globale Semaphore-Nutzung,
- modellbezogene Cooldowns,
- Retry-Klassifikation und Backoff,
- Aufbau des Attempt-Ergebnisses.

Der LLM-Caller wird als Callback übergeben. Dadurch kann diese Schicht ohne
realen Provider getestet werden.

### `run_artifacts.py`

Besitzt Run-Persistenz und Run-Lookup:

- Resume eines passenden unvollständigen Runs,
- Suche des neuesten abgeschlossenen Runs,
- Erkennung finaler Attempts,
- Laden und Aggregieren von Attempts,
- Schreiben von Run-Manifest und Summary.

Die Decomposition verwendet denselben Run-Lookup und implementiert keine
zweite Manifest-Suche.

## Gemeinsame Modelle und Utilities

- `models.py`: versionierte Pydantic-Modelle und das
  `DecompositionAdapter`-Protokoll.
- `artifacts.py`: kanonisches JSON, SHA-256, atomare JSON-Schreibvorgänge und
  UTC-Zeitstempel.
- `sampling.py`: stabile Seed-Ableitung und begrenztes Normal-Sampling.

Diese Module enthalten keine CLI-Orchestrierung.

## Abhängigkeitsrichtung

Die beabsichtigte Richtung lautet:

```text
CLI
  -> Anwendungsfall-Orchestrierung
      -> fachliche Services und pure Mapper
      -> Artefakt-Persistenz
      -> bestehende Grammar-, Generator- und LLM-Grenzen
```

Pure Sampling- und Mapping-Funktionen greifen nicht auf Manifeste oder
Provider zu. Artefaktmodule bauen keine Prompts und sampeln keine Parameter.
Dadurch können Sampling, Retry-Policy, Snapshot-Aufbau und Persistenz getrennt
getestet und geändert werden.

## Tests

`tests/test_evaluation.py` prüft die wichtigsten Modulgrenzen:

- filename-basierte Config-Namen,
- deterministisches und begrenztes Sampling,
- Prepare-Snapshots und Manifeste,
- globale Concurrency ohne realen Provider,
- Evaluation- und Decomposition-Handoff,
- Auswertung von Rate-Limit-Reset-Headern.

Provideraufrufe werden über den injizierten asynchronen LLM-Caller ersetzt.
Die Tests erzeugen ihre Evaluation-Artefakte in temporären Verzeichnissen.

## Erweiterungen

- Eine neue Sampling-Achse gehört in `evaluation/config.py` und
  `case_sampling.py`.
- Ein neues Attempt-Feld wird in `job_execution.py` erzeugt und bei Bedarf in
  `run_artifacts.py` aggregiert.
- Eine neue Retry-Regel gehört ausschließlich in `job_execution.py`.
- Ein anderes Decomposition-Verfahren implementiert
  `DecompositionAdapter`; Prepare und Evaluate müssen dafür nicht geändert
  werden.
- Neue Config-Arten können `NamedYamlConfigSource` verwenden, behalten aber
  ihr eigenes fachliches Pydantic-Modell.
