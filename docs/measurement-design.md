# Messdesign und Projektstruktur

Dieses Dokument hält fest, welche Kernfragen der Benchmark sichtbar machen soll. Die Projektstruktur soll sich daran orientieren, dass diese Messdimensionen klar getrennt, skalierbar und auswertbar bleiben.

## Zentrale Messidee

Der Benchmark soll Reasoning-Leistung in einem kontrollierten, formalen Spielraum messen. Zwei Eigenschaften stehen im Zentrum:

Erstens skaliert das Spiel räumlich über die Anzahl der Dimensionen. Ein Modell muss einen Zug nicht nur als Wort verstehen, sondern als Platzierung in einem n-dimensionalen Koordinatenraum. Mit steigenden Dimensionen wird es schwieriger, Überlappungen, Nachbarschaften und Gültigkeit räumlich korrekt zu behandeln.

Zweitens entfernt sich der Benchmark bewusst von natürlicher Sprache. Die Wörter entstehen aus einer abstrakten, formal definierten oder randomisierten Vokabularsprache. Dadurch soll die Messung weniger davon abhängen, welche syntaktischen oder semantischen Muster ein LLM im Training natürlicher Sprache gelernt hat.

Das Ziel ist, Reasoning möglichst isoliert zu messen: formale Regelbefolgung, räumliche Konsistenz, Suche im Lösungsraum und Optimierung nach Score.

## Hauptachsen der Skalierung

Die Schwierigkeit soll entlang zweier Achsen kontrolliert skaliert werden.

Die erste Achse ist die Anzahl der Dimensionen des Boards. Ein einfacher Fall ist ein 2D-Board. Schwieriger werden 3D-, 4D- oder 5D-Boards. Wichtig ist dabei, dass die Anzahl der belegten Tokens konstant gehalten werden kann, damit nicht versehentlich gleichzeitig die Taskgröße mitskaliert. Wenn ein 2D-Case 100 belegte Tokens enthält, soll ein 4D-Case für bestimmte Experimente ebenfalls 100 belegte Tokens enthalten. Dann verändert sich primär die räumliche Struktur, nicht die Menge der Information.

Die zweite Achse ist die Komplexität des konkreten Tasks. Dazu gehören unter anderem:

- Boardgröße.
- Anzahl belegter Tokens.
- Dichte und Verteilung der belegten Felder.
- Anzahl und Länge bereits möglicher Wortstrukturen.
- Rackgröße und Rack-Zusammensetzung.
- Anzahl potenzieller Anschlussstellen.
- Einschränkung des Lösungsraums durch bereits liegende Tokens.
- Komplexität der formalen Sprache.
- Score-Funktion und Zielkriterium.

Diese beiden Achsen sollen getrennt steuerbar sein. Ein höherdimensionales Board darf nicht automatisch ein größerer oder dichterer Task sein, außer genau das ist in einem Experiment ausdrücklich gewollt.

## Matrix-Design

Ein gutes Experimentaldesign kann als Matrix verstanden werden:

```text
                    Task-Komplexität
                 niedrig   mittel   hoch
Dimensionen
2D               einfach     ...     ...
3D                  ...      ...     ...
4D                  ...      ...   schwer
5D                  ...      ...   schwerer
```

In der einfachsten Zelle steht ein 2D-Board mit geringer Task-Komplexität. In der schwierigsten Zelle steht ein 4D- oder 5D-Board mit hoher Task-Komplexität. Dadurch lässt sich sichtbar machen, ob Modelle eher an räumlicher Dimensionalität, an Suchraumkomplexität oder an der Kombination aus beidem scheitern.

Die erwarteten Ergebnisse sollten als Kurven und Heatmaps auswertbar sein:

- Performance über steigende Dimensionen bei konstanter Task-Komplexität.
- Performance über steigende Task-Komplexität bei konstanter Dimension.
- Performance über die vollständige Dimensions-Komplexitäts-Matrix.

## Gewünschte Findings

Das Paper soll idealerweise zeigen können, wie sich LLM-Reasoning-Performance verhält, wenn die Anzahl der Dimensionen steigt. Dafür muss die Repräsentation des Boards so einfach und formal sein, dass sinkende Performance nicht plausibel auf schlechtes Daten-Exposure zurückgeführt werden kann.

Zusätzlich soll gezeigt werden, wie Modelle mit zunehmender Task-Komplexität umgehen, wenn die Dimension konstant bleibt. Damit kann man unterscheiden, ob ein Modell vor allem an räumlicher Struktur, an kombinatorischer Suche oder an formaler Sprachvalidierung scheitert.

Die zweite zentrale Perspektive ist der Abstand zu natürlicher Sprache. Durch abstrakte Tokens und formal definierte Vokabulare soll vermieden werden, dass Modelle über gelernte natürliche Sprachmuster profitieren. Der Benchmark soll daher nicht primär testen, ob ein Modell englische oder deutsche Wörter kennt, sondern ob es in einem kontrollierten Symbolsystem gültig und zielgerichtet handeln kann.

## Konsequenzen für die Projektstruktur

Die Codebasis sollte so strukturiert werden, dass die Messachsen explizit bleiben. Module sollten nicht nur technische Hilfsordner sein, sondern die Kernfragen des Projekts widerspiegeln.

Wichtige Bausteine sind:

- Board- und State-Repräsentation.
- Prompt- und Schema-Repräsentation.
- formale Sprache und Automaten.
- Spielregelvalidierung.
- Szenario- und Task-Generatoren.
- Modellaufrufe über LiteLLM.
- Metriken und Auswertung.

Die aktuelle Trennung in `domain`, `benchmark` und `formal` ist dafür noch nicht selbsterklärend genug. Eine spätere Reorganisation sollte klar machen, welche Teile den Spielzustand beschreiben, welche Teile die formale Sprache definieren, welche Teile Tasks erzeugen und welche Teile Messungen auswerten.

## Experimentelle Kontrollprinzipien

Die Repräsentation des Boards soll vollständig, kompakt und verlustfrei sein. Ein Modell soll nicht erst eine unhandliche Visualisierung dekodieren müssen. Deshalb ist eine voxel-basierte Liste belegter Koordinaten ein guter Standard.

Dimension und Taskgröße sollen getrennt kontrolliert werden. Wenn Dimensionen skaliert werden, kann die Anzahl belegter Tokens konstant bleiben. Wenn Task-Komplexität skaliert wird, kann die Dimension konstant bleiben.

Validität und Score sollen deterministisch berechnet werden. Modelloutputs werden strukturiert geparst, formal validiert und anschließend anhand klarer Metriken bewertet.

Der Benchmark soll Fehler erklärbar machen. Ein ungültiger Output sollte klassifizierbar sein, etwa als Schemafehler, Rackfehler, räumlicher Konflikt, ungültige Nebenachse, Sprachfehler oder suboptimaler, aber valider Zug.
