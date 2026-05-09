# V1-Prototyp

Der V1-Prototyp ist kein vollständiger Benchmark, sondern ein Machbarkeitstest. Er soll zeigen, ob ein LLM eine stark vereinfachte Scrabble-artige Aufgabe in einem kontrollierten formalen Setting überhaupt lösen kann. Der Prototyp entscheidet damit, ob die spätere Skalierung über größere Boards, schwierigere Sprachen und höhere Dimensionen realistisch ist.

## Fester Scope

Die Board-Dimensionalität ist in V1 fest auf `2` gesetzt. Es gibt also nur ein zweidimensionales Spielbrett. Höhere Dimensionen bleiben für das Paper-Zielbild relevant, werden aber nicht im ersten Prototypen benötigt.

Die Evaluation ist binär. Ein Modelloutput ist entweder ein valider Zug oder kein valider Zug. Scrabble-Punktwerte, Optimierung über eine Lösungsmenge und graduelle Scores werden in V1 bewusst weggelassen. Das Ziel ist nicht, den besten Zug zu finden, sondern überhaupt einen gültigen Zug zu erzeugen.

Die Sprache wird zunächst über abstrakte Platzhalter definiert. Diese Platzhalter werden erst später auf konkrete Symbole gemappt. Für V1 reicht ein einfaches Mapping auf zufällig gewählte ASCII-Zeichen oder ein kleines manuell definiertes Alphabet. Tokenizer-spezifische Sub-Token-, Token- und Supra-Token-Level werden noch nicht systematisch variiert.

## Kernaufgabe

Das Modell erhält ein zweidimensionales Board, ein Rack mit verfügbaren Symbolen und eine formale Sprachdefinition oder ein daraus abgeleitetes Aufgabenformat. Es soll eine Symbolfolge auf dem Board platzieren.

Ein Zug ist valide, wenn alle folgenden Bedingungen erfüllt sind:

- Die Ausgabe erfüllt das erwartete JSON-Schema.
- Die platzierte Symbolfolge verwendet nur verfügbare Rack-Symbole, abzüglich konsistenter Überlappungen mit bereits liegenden Symbolen.
- Die Platzierung liegt vollständig innerhalb des Boards.
- Die Platzierung verläuft horizontal oder vertikal.
- Neue Symbole widersprechen keinen bereits belegten Zellen.
- Die Hauptfolge ist ein gültiges Wort der formalen Sprache.
- Alle durch Nachbarschaften entstehenden Querwörter bleiben ebenfalls gültige Wörter der formalen Sprache.

Diese binäre Validierung reicht für V1 aus. Es muss nicht bekannt sein, wie viele Lösungen ein Board hat und ob der Modellzug optimal ist.

## Board Configuration und Output Schema

Die Board Configuration soll klar vom Modelloutput getrennt werden. Sie beschreibt nur den aktuellen Spielzustand und die verfügbaren Symbole.

Eine V1-Board-Configuration enthält mindestens:

- `dimensions`: Für V1 immer `2`.
- `shape`: Breite und Höhe des Boards.
- `occupied`: Liste belegter Felder als Koordinaten-Symbol-Paare.
- `rack`: verfügbare Symbole für den nächsten Zug.

Beispiel:

```json
{
  "dimensions": 2,
  "shape": [8, 8],
  "occupied": [
    {"coord": [2, 3], "letter": "A"},
    {"coord": [3, 3], "letter": "B"}
  ],
  "rack": ["A", "A", "C", "D"]
}
```

Das Modell soll keinen frei formulierten Zug ausgeben, sondern ein strukturiertes JSON-Objekt. Ein Zug enthält mindestens:

- `start`: Startkoordinate des ersten Symbols.
- `axis`: Richtung des Wortes.
- `sequence`: gelegte Symbolfolge.

Beispiel:

```json
{
  "start": [2, 3],
  "axis": 0,
  "sequence": ["A", "B", "C", "D"]
}
```

Pydantic-Modelle sollen Struktur, Typen und Normalisierung erzwingen. Parsingfehler müssen getrennt von Spielregel- und Sprachfehlern ausgewertet werden. Zu prüfen bleibt, ob LiteLLM strukturierte Outputs über ein Pydantic-Schema oder einen vergleichbaren Parameter providerübergreifend zuverlässig erzwingen kann.

## Prompt-Struktur

Der System Prompt enthält stabile Regeln: Spielregeln, Sprach- oder Automatenbeschreibung und erwartetes Output-Format. Der User Prompt enthält nur den variablen Zustand: Board Configuration, Rack und konkrete Aufgabe.

Für V1 darf die Sprachbeschreibung pragmatisch bleiben. Wichtig ist, dass Prompting, Validator und Sprachdefinition dieselbe Spezifikation verwenden.

## Nicht-Ziele in V1

V1 erzeugt keinen vollständigen 4D-Benchmark-Tensor. Die Achsen Alphabetklasse, Board-Dimensionalität, Board-Komplexität und Automaten-Komplexität werden noch nicht gemeinsam skaliert.

V1 braucht keine CSP-, SAT- oder vollständige Lösungsraumanalyse. Solche Verfahren können später helfen, lösbare Instanzen mit kontrollierter Schwierigkeit zu bauen. Für den ersten Prototypen reicht es, generierte oder manuell erstellte Boards durch einen Validator zu prüfen und Modellantworten binär zu bewerten.

V1 enthält keine Failure-Decomposition ab einem Performance-Threshold. Die Fehlerklassen sollen trotzdem technisch vorbereitet werden, damit ungültige Outputs später besser analysiert werden können.

## Zentrale Risiken

Der wichtigste technische Knackpunkt ist die Boardvalidierung. Schon im 2D-Fall muss korrekt geprüft werden, ob durch einen Zug alle horizontalen und vertikalen Wortsegmente gültig bleiben.

Der zweite Knackpunkt ist die Generierung brauchbarer formaler Sprachen. Die Sprache darf nicht trivial sein, soll aber auch nicht so dünn sein, dass fast kein gültiges Wort aus einem Rack erzeugbar ist.

Der dritte Knackpunkt ist die Boardgenerierung. Wenn bestehende Wörter zufällig auf das Board gelegt werden, muss der Generator das Board schrittweise gültig halten. Gleichzeitig soll die Boardgröße skalierbar bleiben, ohne dass der Generator sofort in unlösbaren oder extrem künstlichen Zuständen landet.

## Technische Fehlerklassen

Auch wenn V1 nur binär bewertet, sollte der Validator intern Fehlerklassen ausgeben. Sinnvolle Klassen sind Schemafehler, Rackfehler, Out-of-bounds-Platzierung, räumlicher Konflikt, fehlende Verbindung, ungültiges Hauptwort und ungültiges Querwort. Diese Klassen sind noch keine vollständige Failure-Decomposition, bereiten sie aber vor.

## Implementierungsbausteine

Die Codebasis sollte die zentralen Verantwortlichkeiten sichtbar trennen:

- Board- und State-Repräsentation.
- Prompt- und Schema-Repräsentation.
- formale Sprache und Automaten.
- Spielregelvalidierung.
- Szenario- und Boardgeneratoren.
- Modellaufrufe über LiteLLM.
- Metriken und Auswertung.

Die Implementierung muss nicht sofort umstrukturiert werden. Für den Prototypen ist aber wichtig, Boardzustand, formale Sprache, Prompting, Modellaufruf und Validierung nicht unnötig zu vermischen.
