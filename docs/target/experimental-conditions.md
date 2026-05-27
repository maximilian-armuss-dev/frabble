# Experimentelle Bedingungen

Diese Bedingungen gehören zum späteren Benchmark-Zielbild. V1 implementiert nur einen kleinen Full-Puzzle-Kern mit binärer Validierung; die sparse Board-Dimensionalität ist für beliebige Werte `dimensions >= 2` konfigurierbar.

## E1: Membership

Das Modell klassifiziert, ob eine gegebene Symbolfolge zur formalen Sprache gehört. Diese Bedingung testet reine Sprachkonformität ohne Board, Rack oder Platzierung.

Varianten:

- Grammatik oder Automat wird explizit gegeben.
- Das Modell erhält nur Beispiele und muss die Sprache induzieren.

## E2.1: Generation mit induzierter Grammatik

Das Modell soll aus einem Rack eine gültige Symbolfolge erzeugen, erhält aber nur Beispiele statt einer expliziten Grammatik. Diese Bedingung kombiniert Induktion und constrained generation.

Die Performance kann als Kurve über die Anzahl der Beispiele berichtet werden.

## E2.2: Generation mit gegebener Grammatik

Das Modell soll aus einem Rack eine gültige Symbolfolge erzeugen und erhält die Grammatik explizit. Diese Bedingung isoliert constrained generation stärker, weil die Induktionslast reduziert wird.

Der Abstand zwischen E2.1 und E2.2 kann als Induktionskosten interpretiert werden.

## E3: Placement

Das Modell erhält ein Board, Tiles und eine oracle-supplied Liste gültiger Wörter. Es muss nur die Platzierung lösen. Diese Bedingung isoliert räumliche Planung und Boardconstraints.

Der Vergleich mit E2.2 zeigt, wie stark die Platzierungskomponente zusätzlich belastet.

## E4: Full Puzzle

Das Modell erhält Board, Rack und die relevante Sprachinformation oder Beispiele, aber keine Oracle-Lösung. Es muss ein gültiges Wort erzeugen und korrekt platzieren.

Diese Bedingung ist die Headline-Aufgabe. Sie wird gegen E1 bis E3 gelesen, damit ein Scheitern einer Teilfähigkeit zugeordnet werden kann.
