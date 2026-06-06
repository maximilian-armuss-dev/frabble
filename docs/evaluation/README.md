# Evaluation

Die Evaluation besteht aus drei getrennten Phasen:

1. `prepare` erzeugt reproduzierbare Grammars, Szenarien und unveraenderliche
   Evaluation-Cases.
2. `evaluate` fuehrt ausgewaehlte Cases gegen ausgewaehlte Modellprofile und
   Sprachrepraesentationen aus.
3. `decompose` uebergibt fehlgeschlagene Evaluation-Versuche an eine gemeinsame
   Decomposition-Schnittstelle.

Diese Trennung verhindert, dass LLM-Aufrufe waehrend eines Runs neue
Testinstanzen erzeugen. Ein vorbereiteter Case kann damit zwischen Modellen,
Promptrepraesentationen und spaeteren Decomposition-Verfahren exakt verglichen
werden.

## Konfiguration und Artefakte

Unter `config/` liegen ausschliesslich von Menschen gepflegte YAML-Dateien:

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
├── grammars/
├── scenarios/
├── cases/
├── schemas/
└── runs/<run-id>/
    ├── run-manifest.json
    ├── attempts/
    ├── summary.json
    └── decomposition/
```

Eine Case-Set-Config definiert die stabile Versuchsmatrix und das
reproduzierbare Sampling. Eine Run-Config waehlt aus dieser Matrix Tiers,
Modellprofile und Sprachrepraesentationen aus.

## Zentrale Begriffe

- **Sampling round**: Eine vollstaendig neue Ziehung aller variablen Parameter,
  Grammars und Boards. Eine weitere Runde erzeugt neue Cases, nicht weitere
  LLM-Aufrufe auf demselben Case.
- **Grammar sample**: Eine unabhaengig gesampelte Sprache innerhalb eines Tiers.
  Mehrere Grammar-Samples verhindern, dass ein zufaelliger Sprachausreisser ein
  komplettes Tier bestimmt.
- **Board sample**: Ein unabhaengiger Generatorlauf mit eigenem Seed fuer eine
  konkrete Grammar.
- **Board depth**: Anzahl bereits ausgefuehrter Witness-Moves im Boardzustand,
  den das Modell sieht. Der zu loesende Move liegt an diesem Transition-Index.
- **Evaluation case**: Vollstaendiger Snapshot von Board, Rack, Grammar,
  Ground-Truth-Move, Parametern, Seeds und Herkunft.
- **Evaluation job**: Kombination aus Evaluation-Case, Modellprofil und
  Sprachrepraesentation.

## Reproduzierbarkeit

Alle Zufallsentscheidungen werden deterministisch aus der Case-Set-ID, dem
Root-Seed, Tier, Sampling-Runde und Sample-Indizes abgeleitet. Prepare schreibt
die angeforderten und tatsaechlich verwendeten Seeds sowie Content-Hashes in
das Manifest.

Ein Case ist nach der Materialisierung unabhaengig von spaeteren Aenderungen an
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
  Datenmodell fuer Evaluation und Decomposition.
