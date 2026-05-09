# Puzzle-Generierung

Das langfristige Ziel ist eine Pipeline, die viele unabhängige Szenarien erzeugt und dabei Solvability, Schwierigkeit und Lösungsmengen kontrollieren kann.

## Teilprobleme

Die Pipeline besteht aus drei gekoppelten Teilproblemen:

- Sampling formaler Sprachen oder Automaten mit kontrollierbarer Komplexität.
- Charakterisierung des Lösungsraums, zum Beispiel Anzahl akzeptierter Strings pro Länge.
- Konstruktion von Boards mit bekannter Lösbarkeit und kontrollierbarer Schwierigkeit.

## Witness zuerst

Der compute-effiziente Standardpfad bleibt auch im Target Picture eine Generierung mit bekanntem Witness. Dabei wird ein gültiger Übergang `B_t -> B_{t+1}` erzeugt, `B_t` als Szenario exportiert und der bekannte Zug als Witness zurückgehalten.

Dieser Ansatz garantiert mindestens eine Lösung, ohne alle Lösungen zu enumerieren.

## Solver als Kalibrierung

CSP-, SAT- oder Backtracking-Verfahren werden als Offline-Oracle oder Kalibrierungswerkzeug genutzt. Sie sind besonders nützlich für:

- Zählen oder Schätzen gültiger Lösungen.
- Filtern ungewollt leichter oder schwerer Instanzen.
- Erzeugen von Instanzen mit bestimmter Lösungsanzahl.
- Validieren, dass Generatorheuristiken keine systematischen Degenerationen erzeugen.

Solver sollen nicht zwingend im Hot Path jeder Szenariogenerierung laufen.

## Compute-Strategie

Die Suche bleibt beherrschbar, solange der Solver nicht ganze Boards frei belegt, sondern nur nächste Züge analysiert. Ein Zug ist durch Startkoordinate, Achse, Sequenzlänge und Symbolfolge beschränkt. Dadurch kann die Kandidatenmenge über Anchors, Rack, Sprache und Boardgrenzen stark reduziert werden.

Für höhere Dimensionen wächst die Anzahl der Achsen und Querconstraints, aber ein Zug bleibt weiterhin eindimensional entlang genau einer Achse.
