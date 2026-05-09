# Experimentelle Bedingungen

Dieses Dokument beschreibt spätere experimentelle Bedingungen. Sie sind nicht vollständig Teil des V1-Prototyps. V1 soll zunächst nur den Full-Puzzle-Kern in 2D mit binärer Validierung testen.

## E1: Membership

Das Modell klassifiziert, ob eine gegebene Symbolfolge zur formalen Sprache gehört. Diese Bedingung testet die reine Sprachkonformität ohne Board, Rack oder Platzierung.

Varianten:

- Die Grammatik oder der Automat wird explizit gegeben.
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

Diese Bedingung ist die Headline-Aufgabe. Sie sollte gegen E1 bis E3 gelesen werden, damit ein Scheitern nicht nur als einzelner Fehlerwert erscheint, sondern einer Teilfähigkeit zugeordnet werden kann.

## Verhältnis zu V1

V1 implementiert nur einen kleinen Ausschnitt dieser Bedingungen. Der erste Prototyp darf als vereinfachtes E4 verstanden werden: 2D-Board, binäre Validierung, keine Score-Optimierung, keine vollständige Decomposition und keine bekannte Lösungsanzahl.

Die experimentellen Bedingungen werden relevant, sobald der Validator, die Sprachgenerierung und die Boardgenerierung stabil genug sind.
