# Decomposition

Später soll die Evaluation nicht nur sagen, dass ein Modell gescheitert ist, sondern auch wo. Dafür kann ein Performance-Threshold definiert werden. Wenn ein Modell unter diesen Threshold fällt, wird die Aufgabe in kleinere Komponenten zerlegt.

Mögliche Komponenten sind:

- Membership: Klassifikation, ob eine gegebene Symbolfolge Teil der Sprache ist.
- Generation: Erzeugung einer gültigen Symbolfolge aus einem Rack.
- Tile Constraint: Nutzung nur verfügbarer Symbole.
- Placement: Wahl einer gültigen Position und Achse.
- Cross Words: Gültigkeit aller durch den Zug entstehenden Sequenzen.
- Output Schema: parsebares strukturiertes JSON.

Diese Decomposition ist kein V1-Ziel. Sie beschreibt, wie spätere Experimente aus Fehlern erklärbare Signale gewinnen können.
