# Future Work

Auf Basis des Papers kann eine spätere Benchmark-Variante die reine Zugproduktion mit einer Solvability-Entscheidung kombinieren.

Ein mögliches Szenario:

- Das Modell erhält weiterhin Board, Rack und Sprachdefinition.
- Mit `50%` Wahrscheinlichkeit ist das Board lösbar.
- Mit `50%` Wahrscheinlichkeit ist das Board unlösbar.
- Das Output-Schema enthält zusätzlich eine Option, mit der das Modell angeben kann, dass kein valider Zug existiert.

Damit würde nicht nur getestet, ob ein Modell einen gültigen Zug finden kann, sondern auch, ob es erkennt, wann die Constraints keine Lösung zulassen. Diese Variante benötigt eine zuverlässige Generator- oder Solver-Pipeline, die lösbare und unlösbare Instanzen kontrolliert erzeugen kann.
