# Board-Generierung und Validierung

Für V1 steht nicht die vollständige Lösungsraumanalyse im Vordergrund, sondern ein zuverlässiger 2D-Validator. Der Validator muss entscheiden können, ob ein einzelner Modellzug das Board in einen gültigen Zustand überführt.

## 2D-Boardmodell

Das V1-Board ist ein rechteckiges zweidimensionales Grid. Jede belegte Zelle enthält genau ein Symbol. Leere Zellen sind implizit frei. Die Repräsentation soll vollständig, kompakt und verlustfrei sein; eine Liste belegter Koordinaten reicht dafür aus und vermeidet unnötig große leere Matrizen im Prompt.

Ein Modellzug besteht aus:

- Startkoordinate.
- Richtung, horizontal oder vertikal.
- Symbolfolge.

Die Symbolfolge wird entlang der Richtung auf das Board gelegt. Bereits belegte Zellen dürfen überlappt werden, wenn das Symbol identisch ist. Widersprüchliche Überlappungen machen den Zug ungültig.

Der erste Zug ist ein Sonderfall, weil noch keine Verbindung zu bestehendem Boardinhalt möglich ist. Alle späteren Züge sollten mindestens ein bestehendes Symbol überlappen oder an ein bestehendes Wort anschließen, damit keine unabhängigen Inseln entstehen.

## Binäre Validierung

Nach dem hypothetischen Legen des Zuges wird der neue Boardzustand geprüft. Dafür reicht im 2D-Fall ein lokaler Ansatz.

Zuerst wird die Hauptfolge entlang der Legerichtung extrahiert. Dabei müssen nicht nur die neu gelegten Symbole betrachtet werden, sondern das gesamte zusammenhängende Wortsegment, das durch bestehende Nachbarzellen verlängert werden kann.

Danach werden für jedes neu belegte Feld die Quersegmente geprüft. Ein horizontal gelegtes Wort erzeugt potenziell vertikale Querwörter; ein vertikal gelegtes Wort erzeugt potenziell horizontale Querwörter. Quersegmente der Länge `1` können je nach Regeldefinition ignoriert oder als triviale Wörter behandelt werden. Diese Entscheidung muss explizit festgelegt werden.

Der Zug ist valide, wenn alle relevanten Segmente Wörter der formalen Sprache sind und keine Board- oder Rackregel verletzt wurde.

Die Validierung sollte lokal implementierbar sein. Nach einem Kandidatenzug müssen nur die Hauptachse und die Querachsen an neu belegten Feldern neu extrahiert werden; unveränderte Wortsegmente bleiben gültig, sofern das Ausgangsboard gültig war.

## Board-Komplexität

Für V1 kann Board-Komplexität primär über die Boardgröße und die Anzahl bereits liegender Wörter skaliert werden. Die relative Sparsity soll grob vergleichbar bleiben: größere Boards dürfen mehr bestehende Wörter enthalten, sollten aber nicht automatisch extrem dicht werden.

Eine mögliche einfache Staffelung ist:

- klein: kleines Board, wenige kurze Wörter, wenige Anker.
- mittel: größeres Board, mehr bestehende Wörter, mehrere mögliche Anschlussstellen.
- groß: deutlich größeres Board, viele bestehende Wörter, mehrere Querconstraints.

Die genaue Metrik muss nicht sofort perfekt sein. Wichtig ist, dass Generatorparameter gespeichert werden, damit Ergebnisse später nachvollziehbar bleiben.

## Prozedurale Boardgenerierung

Ein pragmatischer Generator kann ein Board Schritt für Schritt aufbauen:

1. Erzeuge oder sample ein gültiges Wort aus der Sprache.
2. Lege es zufällig auf ein leeres Board.
3. Wiederhole: sample ein weiteres gültiges Wort, wähle eine mögliche Überlappung oder Anschlussstelle und versuche eine gültige Platzierung.
4. Übernimm die Platzierung nur, wenn der Validator bestätigt, dass der neue Zustand gültig bleibt.
5. Stoppe nach einer Zielanzahl akzeptierter Wörter oder nach einer maximalen Anzahl fehlgeschlagener Versuche.

Dieser Ansatz garantiert keine bekannte Lösungsanzahl, ist aber ausreichend für V1, solange die erzeugten Boards selbst gültig sind. Für spätere Experimente kann ein CSP-, SAT- oder Backtracking-Ansatz ergänzt werden, um lösbare Instanzen mit kontrollierter Lösungsmengen-Größe zu bauen.

## Offene Regelfragen

Es muss festgelegt werden, ob jedes neu gelegte Symbol mindestens mit einem bestehenden Symbol verbunden sein muss. Für Scrabble-artige Aufgaben ist das wahrscheinlich sinnvoll, außer beim ersten Zug.

Es muss entschieden werden, wie Wörter der Länge `1` behandelt werden. Wenn die formale Sprache einstellige Wörter erlaubt, können einzelne Nachbarprüfungen missverständlich werden. Für V1 ist eine klare Sonderregel einfacher.

Es muss definiert werden, ob ein Zug mindestens ein neues Symbol legen muss oder ob eine reine Überdeckung eines bestehenden Wortes verboten ist. Für V1 sollte mindestens ein neues Symbol erforderlich sein.
