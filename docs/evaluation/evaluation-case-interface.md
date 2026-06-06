# Evaluation-Case-Schnittstelle

## EvaluationCase

`EvaluationCase` ist die gemeinsame Eingabe fuer Full-Puzzle-Evaluation und
Decomposition. Es ist ein versionierter Snapshot und enthaelt keine
aufzuloesenden YAML-Vererbungen.

Konzeptionelle Struktur:

```json
{
  "schema_version": 1,
  "case_id": "screening_v1.low.r00.g00.b00",
  "case_set": "screening_v1",
  "tier": "low",
  "sampling_round": 0,
  "grammar_sample_index": 0,
  "board_sample_index": 0,
  "seeds": {
    "grammar_requested": 123,
    "grammar_used": 124,
    "board": 456
  },
  "parameters": {
    "grammar": {},
    "generation": {},
    "board_depth": 20
  },
  "grammar": {},
  "board": {},
  "rack": [],
  "ground_truth_move": {},
  "provenance": {
    "grammar_artifact": "...",
    "scenario_artifact": "...",
    "grammar_sha256": "...",
    "scenario_sha256": "...",
    "case_set_config_sha256": "...",
    "git_revision": "..."
  }
}
```

Board und Rack beschreiben exakt die Eingabe vor dem Ground-Truth-Move. Die
Grammar ist vollstaendig eingebettet, damit eine spaetere Aenderung oder
Loeschung der Grammar-Datei den Case nicht veraendert.

## Full-Puzzle-Runner

Der Full-Puzzle-Runner kombiniert den Case mit:

- einem Modellprofil,
- einer Sprachrepraesentation,
- den festen Board- und Rack-Repraesentationen.

Er erzeugt Prompt, Providerantwort, geparsten Move und granulare Evaluation.
Der Case selbst wird nicht veraendert.

## DecompositionRequest

Ein `DecompositionRequest` enthaelt:

```json
{
  "schema_version": 1,
  "request_id": "...",
  "case": {},
  "failed_attempt": {},
  "requested_at": "..."
}
```

Damit kann die Decomposition sowohl in-process ueber ein Python-Protokoll als
auch out-of-process ueber JSON integriert werden. Die Schnittstelle kennt
keine YAML-Pfade und muss Szenarien nicht rekonstruieren.

## Python-Protokoll

Der Adapter stellt sinngemaess folgende Schnittstelle bereit:

```python
class DecompositionAdapter(Protocol):
    async def decompose(
        self,
        request: DecompositionRequest,
    ) -> DecompositionResult: ...
```

Der initiale Stub liefert den Status `not_implemented`. Spaetere Adapter
duerfen eigene Prompts oder mehrere Teilaufgaben erzeugen, erhalten aber immer
denselben Case-Snapshot wie die urspruengliche Evaluation.

Prepare schreibt die aus den Pydantic-Modellen abgeleiteten JSON Schemas nach
`outputs/evaluation/<case-set>/schemas/`. Externe Implementierungen koennen
damit `EvaluationCase`, `DecompositionRequest` und `DecompositionResult`
validieren, ohne dieses Python-Package zu importieren.

Intern wird der Snapshot in `case_snapshot.py` aufgebaut. Das Modul erhaelt
bereits aufgeloeste Grammar- und Scenario-Kontexte und kennt weder
Case-Set-YAMLs noch Providerzugriffe. Dadurch bleibt diese Schnittstelle eine
explizite Grenze zwischen Preparation, Evaluation und Decomposition.
