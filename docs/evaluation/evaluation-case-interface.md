# Evaluation-Case-Schnittstelle

## EvaluationCase

`EvaluationCase` ist die gemeinsame Eingabe für Full-Puzzle-Evaluation und
Decomposition. Es ist ein versionierter Snapshot und enthält keine
aufzulösenden YAML-Vererbungen.

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
Grammar ist vollständig eingebettet, damit eine spätere Änderung oder
Löschung der Grammar-Datei den Case nicht verändert.

## Full-Puzzle-Runner

Der Full-Puzzle-Runner kombiniert den Case mit:

- einem Modellprofil,
- einer Sprachrepräsentation,
- den festen Board- und Rack-Repräsentationen.

Er erzeugt Prompt, Providerantwort, geparsten Move und granulare Evaluation.
Der Case selbst wird nicht verändert.

## DecompositionRequest

Ein `DecompositionRequest` enthält:

```json
{
  "schema_version": 1,
  "request_id": "...",
  "case": {},
  "failed_attempt": {},
  "requested_at": "..."
}
```

Damit kann die Decomposition sowohl in-process über ein Python-Protokoll als
auch out-of-process über JSON integriert werden. Die Schnittstelle kennt
keine YAML-Pfade und muss Szenarien nicht rekonstruieren.

## Python-Protokoll

Der Adapter stellt sinngemäß folgende Schnittstelle bereit:

```python
class DecompositionAdapter(Protocol):
    async def decompose(
        self,
        request: DecompositionRequest,
    ) -> DecompositionResult: ...
```

Der initiale Stub liefert den Status `not_implemented`. Spätere Adapter
dürfen eigene Prompts oder mehrere Teilaufgaben erzeugen, erhalten aber immer
denselben Case-Snapshot wie die ursprüngliche Evaluation.

Prepare schreibt die aus den Pydantic-Modellen abgeleiteten JSON Schemas nach
`outputs/evaluation/<case-set>/schemas/`. Externe Implementierungen können
damit `EvaluationCase`, `DecompositionRequest` und `DecompositionResult`
validieren, ohne dieses Python-Package zu importieren.

Intern wird der Snapshot in `case_snapshot.py` aufgebaut. Das Modul erhält
bereits aufgelöste Grammar- und Scenario-Kontexte und kennt weder
Case-Set-YAMLs noch Providerzugriffe. Dadurch bleibt diese Schnittstelle eine
explizite Grenze zwischen Preparation, Evaluation und Decomposition.
