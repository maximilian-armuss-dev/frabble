# Board-Repräsentation, Prompting und Validierung

Dieses Dokument hält den aktuellen Zielzustand für die Repräsentation des multidimensionalen Scrabble-Benchmarks fest. Es beschreibt noch keine finale Implementierung, sondern die Architektur, an der sich die nächsten Module orientieren sollen.

## Mentales Modell

Der Benchmark soll ein Modell nicht daran scheitern lassen, dass ein multidimensionales Brett schlecht oder unnötig schwer dargestellt wird. Die Darstellung des Spielzustands soll deshalb formal, kompakt und verlustfrei sein. Das Modell soll die eigentliche Aufgabe lösen: einen gültigen und möglichst hoch bewerteten Zug in einem kontrollierten formalen Spielraum finden.

Das Board soll voxel-basiert beschrieben werden. Ein belegtes Feld ist ein Token an einer Koordinate. Jede Koordinate ist ein Vektor mit genau so vielen Einträgen, wie das Board Dimensionen hat. Nicht belegte Felder werden nicht einzeln aufgelistet, sondern gelten implizit als frei.

## Board Configuration

Die Board Configuration soll klar vom Output Schema getrennt werden. Sie beschreibt nur den aktuellen Spielzustand und die aktuell verfügbaren Tokens.

Eine Board Configuration enthält mindestens:

- `dimensions`: Anzahl der Dimensionen.
- `shape`: Größe des Boards pro Dimension.
- `occupied`: Liste aller belegten Felder als Koordinaten-Token-Paare.
- `rack`: aktuell gezogene Tokens, die für den nächsten Zug verwendet werden dürfen.

Beispiel:

```json
{
  "dimensions": 4,
  "shape": [5, 5, 5, 5],
  "occupied": [
    {"coord": [2, 1, 0, 0], "token": "A"},
    {"coord": [2, 2, 0, 0], "token": "B"},
    {"coord": [2, 3, 0, 0], "token": "C"}
  ],
  "rack": ["A", "A", "B", "C"]
}
```

## Output Schema

Das Modell soll keinen frei formulierten Zug ausgeben, sondern ein strukturiertes JSON-Objekt, das per Pydantic validiert und geparst wird. Das Output Schema ist unabhängig von der Board Configuration.

Ein Zug enthält mindestens:

- `start`: Startkoordinate des ersten Tokens.
- `axis`: Dimension, entlang der das Wort gelegt wird.
- `tokens`: Tokenfolge des gelegten Wortes.

Beispiel:

```json
{
  "start": [2, 1, 0, 0],
  "axis": 1,
  "tokens": "ABAC"
}
```

Die Pydantic-Modelle sollen dafür zuständig sein, die Struktur zu erzwingen, Typen zu normalisieren und Parsing-Fehler klar von Spielregel-Fehlern zu trennen. LiteLLM bleibt die einheitliche Schnittstelle zu den verschiedenen Modellprovidern. Wenn der jeweilige Provider strukturierte Outputs unterstützt, soll das Pydantic-Schema darüber möglichst direkt eingebunden werden.

Spannend wäre, ob das mit LiteLLM enforcebar ist als kwarg im completion call.

## Prompt-Struktur

Der System Prompt soll die stabilen, wiederverwendbaren Regeln enthalten. Dazu gehören:

- Spielregeln.
- Definition des Automaten.
- Definition der formalen Sprache.
- Beschreibung des erwarteten Output-Formats.

Der User Prompt soll pro einzelner Session nur den variablen Zustand enthalten:

- Board Configuration.
- Rack.
- konkrete Aufgabe, etwa einen validen Zug mit möglichst hohem Score zu finden.

Für Spielregeln und Automaten kann zunächst ein Platzhalter verwendet werden. Wichtig ist die saubere Trennung: stabile Regeln in den System Prompt, aktueller Spielzustand in den User Prompt.

## Spielregeln

Die endgültigen Spielregeln müssen noch präzisiert werden. Als Zielbild gilt eine multidimensionale Scrabble-Variante:

Ein neuer Zug legt eine Tokenfolge entlang genau einer Achse. Neu gelegte Tokens dürfen bestehende Tokens konsistent überlappen, aber nie widersprechen. Jeder neu gelegte Token muss außerdem in allen relevanten Achsen mit angrenzenden bereits liegenden Tokens gültige Wörter bilden. Es reicht also nicht, dass nur die Hauptachse des neu gelegten Wortes gültig ist, wenn durch seitliche Nachbarschaften zusätzliche Wörter entstehen.

Diese Regeln sollen später gemeinsam mit der Automaten- und Sprachdefinition formalisiert werden, damit Validierung und Prompting dieselbe Spezifikation verwenden.

Weiterhin müssen Scoring Regeln klarer definiert und dem LLM verständlich gemacht werden.

## Modulidee

Es soll ein neues Modul entstehen, das die Board Configuration und das strukturierte Parsing bündelt. Dieses Modul sollte nicht mit der formalen Sprachvalidierung vermischt werden.

Mögliche Verantwortlichkeiten:

- Pydantic-Modelle für Board Configuration und Move Output.
- Serialisierung der Board Configuration in Prompt-taugliches JSON.
- Parsing und Normalisierung der Modellantwort.
- klare Fehlerklassen für Schemafehler, Boardfehler und spätere Sprach-/Automatenfehler.

Die aktuellen Ordner `domain`, `benchmark` und `formal` sind dafür noch nicht überzeugend genug. Die nächste Struktur sollte stärker an den zentralen Projektfragen ausgerichtet werden: Repräsentation, Spielzustand, formale Sprache, Prompting, Modellaufruf, Validierung und Auswertung.
