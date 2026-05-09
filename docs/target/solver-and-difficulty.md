# Solver und Difficulty

Für das Target Picture ist ein CSP- oder Solver-Ansatz nützlich, aber nicht als Teil jeder Szenariogenerierung notwendig. Der compute-effizientere Standardpfad bleibt Generierung mit bekanntem Witness. Ein Solver kann offline oder begrenzt genutzt werden, um Schwierigkeit zu kalibrieren, Lösungsmengen zu zählen oder Instanzen mit bestimmten Eigenschaften zu filtern.

Ein Difficulty-Score kann später mehrere Features kombinieren:

- Anzahl gültiger Lösungen, falls effizient zählbar oder schätzbar.
- Board-Dimensionalität.
- Boardgröße.
- Anzahl belegter Symbole.
- Anzahl bestehender Sequenzen.
- Anzahl möglicher Anchors.
- Rack-Slack, also wie viele zusätzliche oder alternative Symbole im Rack liegen.
- Sprachdichte der zugrunde liegenden formalen Sprache.
- Anzahl entstehender Querconstraints beim Witness-Zug.

Eine Instanz mit nur einer Lösung ist tendenziell schwerer, aber Lösungsanzahl allein reicht nicht als Schwierigkeitsscore. Ein einzelner offensichtlicher Kreuzungspunkt kann leichter sein als ein Board mit mehreren subtilen Möglichkeiten. Der Score sollte empirisch gegen Pilotläufe kalibriert werden.
