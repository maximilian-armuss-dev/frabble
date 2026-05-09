# V1-Scope

Der V1-Prototyp ist ein Machbarkeitstest. Er soll zeigen, ob ein LLM eine Scrabble-artige Aufgabe in einem kontrollierten formalen Setting überhaupt lösen kann.

## Festlegungen

- Board-Dimensionalität ist fest `2`.
- Evaluation ist binär: valider Zug oder ungültiger Zug.
- Kein Scrabble-Punktwert.
- Keine Optimierung über eine Lösungsmenge.
- Keine vollständige Lösungsraumanalyse.
- Keine CSP-, SAT- oder Backtracking-Abhängigkeit für den Prototypen.
- Keine Tokenizer-spezifischen Sub-Token-, Token- oder Supra-Token-Experimente.
- V1 nutzt Platzhalteralphabete, sichtbar als Buchstaben.
- V1 nutzt `5` manuell definierte Strictly-Local-Sprachen mit `k = 2` und Alphabetgröße `6`.
- V1 akzeptiert nur Overlap-Verbindungen zwischen neuem Zug und bestehender Boardstruktur.

## Kernaufgabe

Das Modell erhält ein frisches zweidimensionales Board, ein Rack mit verfügbaren Symbolen und eine formale Sprachdefinition. Es soll genau eine vollständige Symbolsequenz auf dem Board platzieren.

Evaluationsinstanzen sind voneinander unabhängig. Das Modell spielt keinen fortlaufenden Spielverlauf, sondern bekommt pro Instanz ein neues Board in einem arbiträren Zustand.
