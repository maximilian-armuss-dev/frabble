# Paper-Zielbild

Das Paper-Zielbild ist ein skalierbarer Benchmark für LLMs in einem kontrollierten formalen Spielraum. Die zentrale Motivation bleibt Reasoning: Aktuelle Benchmarks können Performancegewinne mitmessen, die aus gelernten Mustern natürlicher Sprache stammen. Der Benchmark soll diese Quelle so weit wie möglich entkoppeln, indem natürliche Wörter durch formal erzeugte Symbolsprachen ersetzt werden.

Die Contribution soll aber nicht nur ein einzelner Leaderboard-Wert sein. Aussagekräftiger ist eine dekomponierte Evaluation, die sichtbar macht, ob ein Modell an formaler Sprachkonformität, constrained generation, räumlicher Planung oder an der Komposition dieser Fähigkeiten scheitert.

## Skalierungsachsen

Langfristig kann der Benchmark als vierdimensionaler Experimentalraum verstanden werden:

- Alphabetklasse.
- Board-Dimensionalität.
- Board-Komplexität.
- Automaten-Komplexität.

Die Alphabetklasse beschreibt, auf welcher Tokenebene die konkreten Symbole liegen. Denkbar sind Sub-Token-Level, Token-Level und Supra-Token-Level. Im Zielbild wird dieselbe abstrakte Platzhaltersprache auf unterschiedliche konkrete Alphabete gemappt, um zu messen, wie stark die Modellleistung von der Symbolrepräsentation abhängt.

Die Board-Dimensionalität skaliert von 2D zu höheren Dimensionen. Für das Paper bleibt interessant, ob Modelle bei gleicher Taskgröße schlechter werden, wenn dieselben lokalen Regeln in einem höherdimensionalen Koordinatenraum angewendet werden müssen.

Die Board-Komplexität beschreibt die Größe und Struktur des Brettzustands. Sie kann über Boardgröße, Anzahl belegter Symbole, Anzahl bereits liegender Wörter, Wortlängen, Rackgröße, Anzahl möglicher Anker und Constraint-Enge wachsen.

Die Automaten-Komplexität beschreibt die Schwierigkeit der formalen Sprache. Relevante Parameter sind Anzahl der Zustände, Übergangsdichte, Akzeptanzdichte, minimale DFA-Größe, erlaubte Wortlängen und Anzahl akzeptierter Strings pro Länge.

## Kontrollprinzipien

Die Skalierungsachsen sollen getrennt steuerbar bleiben. Ein höherdimensionales Board darf nicht automatisch ein größeres oder dichteres Board sein, außer genau das ist Teil des Experiments. Wenn die Dimensionalität skaliert wird, kann zum Beispiel die Anzahl belegter Symbole konstant bleiben. Wenn die Board-Komplexität skaliert wird, kann die Dimensionalität konstant bleiben.

Die Boardrepräsentation soll vollständig, kompakt und verlustfrei sein. Ein Modell soll nicht primär daran scheitern, dass ein mehrdimensionales Brett umständlich visualisiert wird. Für höhere Dimensionen ist deshalb eine voxel-artige Liste belegter Koordinaten ein sinnvoller Standard: Jede belegte Zelle ist ein Symbol an einem Koordinatenvektor, leere Zellen werden nicht einzeln aufgelistet.

Validität und spätere Scores müssen deterministisch berechnet werden. Modelloutputs werden strukturiert geparst, formal validiert und anschließend anhand klarer Metriken bewertet.

## Auswertung

Die Ergebnisse sollen als Kurven und Heatmaps auswertbar sein:

- Performance über steigende Board-Dimensionalität bei konstanter Board-Komplexität.
- Performance über steigende Board-Komplexität bei konstanter Dimensionalität.
- Performance über steigende Automaten-Komplexität bei konstantem Boardsetting.
- Performance über Alphabetklassen bei gleicher abstrakter Platzhaltersprache.
- Performance über die vollständige Kombination der Skalierungsachsen, sobald der Benchmark stabil genug ist.

Diese Auswertung soll sichtbar machen, ob Modelle eher an räumlicher Dimensionalität, kombinatorischer Suche, formaler Sprachvalidierung, Symbolrepräsentation oder an der Kombination dieser Faktoren scheitern.

## Decomposition

Später soll die Evaluation nicht nur sagen, dass ein Modell gescheitert ist, sondern auch wo. Dafür kann ein Performance-Threshold definiert werden. Wenn ein Modell unter diesen Threshold fällt, wird die Aufgabe in kleinere Komponenten zerlegt.

Mögliche Komponenten sind:

- Membership: Ist eine gegebene Symbolfolge Teil der Sprache?
- Generation: Kann das Modell eine gültige Symbolfolge aus einem Rack erzeugen?
- Tile Constraint: Nutzt das Modell nur verfügbare Symbole?
- Placement: Kann das Modell eine gültige Position und Richtung wählen?
- Cross Words: Bleiben alle durch Nachbarschaften entstehenden Wörter gültig?
- Output Schema: Liefert das Modell überhaupt parsebares strukturiertes JSON?

Diese Decomposition ist kein V1-Ziel. Sie beschreibt, wie spätere Experimente aus Fehlern erklärbare Signale gewinnen können.

Spätere Score-Funktionen können auf dieser Grundlage eingeführt werden. Sie sollten aber nicht mit Scrabble-Punktwerten starten, sondern zunächst messen, ob ein Output formal gültig ist, welche Constraints verletzt wurden und ob ein valider Output nur suboptimal war.

## Framing

Das Paper kann Reasoning als Motivation verwenden, sollte die messbaren Beiträge aber präziser formulieren. Der Benchmark untersucht Reasoning unter kontrollierten Bedingungen, indem er natürliche Sprachmuster durch formale Symbolsysteme ersetzt und die Aufgabe in überprüfbare Teilfähigkeiten zerlegt.

Eine mögliche Kurzformulierung ist:

> Wir führen einen Scrabble-artigen Benchmark ein, der LLM-Evaluation von natürlicher Sprachmemorisation entkoppelt, indem englische oder deutsche Wörter durch formal erzeugte Symbolsprachen ersetzt werden. Durch dekomponierte Bedingungen messen wir formale Sprachkonformität, constrained generation und räumliche Planung getrennt und in Kombination.
