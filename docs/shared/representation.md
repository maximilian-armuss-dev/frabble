# Repräsentation

Koordinaten werden als 0-basierter Vektor `x = [x0, x1, ..., x_{d-1}]` verstanden. Für V1 gilt `d = 2`; dieselbe Repräsentation bleibt für höhere Dimensionen gültig.

Achsen referenzieren dieselbe Indexlogik wie Koordinaten:

- `axis = 0` bedeutet Bewegung entlang `x0`.
- `axis = 1` bedeutet Bewegung entlang `x1`.
- Allgemein bedeutet `axis = i` Bewegung entlang `xi`.

Das Indexing ist im Prompt, im JSON-Format und intern 0-basiert.

## Board

Das Board wird als sparse Map beziehungsweise als Liste belegter Koordinaten repräsentiert. Jede belegte Zelle enthält genau ein Symbol. Leere Zellen werden nicht einzeln aufgeführt.

Eine Board Configuration enthält mindestens:

- `dimensions`: Anzahl der Dimensionen.
- `shape`: Größe des Boards pro Koordinatenachse.
- `occupied`: Liste belegter Felder als Koordinaten-Symbol-Paare.
- `rack`: verfügbare Symbole für den nächsten Zug.

Beispiel:

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

## Move Output

Das Modell gibt genau ein strukturiertes JSON-Objekt aus:

```json
{
  "start": [2, 3],
  "axis": 0,
  "sequence": ["A", "B", "C", "D"]
}
```

Die `sequence` ist die vollständige Wortsequenz. Sie enthält sowohl neu gelegte Rack-Symbole als auch bereits auf dem Board liegende Symbole, die konsistent überlappt werden. `sequence` ist eine Liste, damit spätere Mehrzeichen-Symbole eindeutig getrennt bleiben.

Pydantic-Modelle sollen Struktur, Typen und Normalisierung erzwingen. Parsingfehler werden getrennt von Spielregel- und Sprachfehlern ausgewertet. Wenn ein Provider über LiteLLM strukturierte Outputs unterstützt, soll das Pydantic-Schema dort eingebunden werden; andernfalls wird die Modellantwort nachträglich geparst und validiert.
