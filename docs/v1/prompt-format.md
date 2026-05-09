# V1-Promptformat

Der System Prompt enthält stabile Regeln: Spielregeln, Sprachbeschreibung und erwartetes Output-Format. Der User Prompt enthält den variablen Zustand: Board Configuration, Rack und konkrete Aufgabe.

Das Modell gibt nur JSON aus, keine Begründung.

## Sprachrepräsentation

Die Sprache wird im V1-Prompt über forbidden snippets oder eine daraus abgeleitete einfache Regel dargestellt. Zusätzlich wird ein kurzes One-Shot-Beispiel autogeneriert, das eine gültige und eine ungültige Sequenz erklärt. Hoffnung dahinter: Durch Beispiele kann das LLM die Komplexität der Sprachrepräsentation besser überwinden.

## Boardrepräsentation

Das Board wird als JSON-kompatible Board Configuration dargestellt:

```json
{
  "dimensions": 2,
  "shape": [8, 8],
  "occupied": [
    {"coord": [2, 3], "symbol": "A"},
    {"coord": [3, 3], "symbol": "B"}
  ],
  "rack": ["A", "A", "C", "D"]
}
```

## Output

Das erwartete Modelloutputformat ist:

```json
{
  "start": [2, 3],
  "axis": 0,
  "sequence": ["A", "B", "C", "D"]
}
```
