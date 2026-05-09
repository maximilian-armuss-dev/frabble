# Komplexitätsachsen

Langfristig kann der Benchmark als vierdimensionaler Experimentalraum verstanden werden:

- Alphabetklasse.
- Board-Dimensionalität.
- Board-Komplexität.
- Automaten-Komplexität.

Die Alphabetklasse beschreibt, auf welcher Tokenebene die konkreten Symbole liegen. Denkbar sind Sub-Token-Level, Token-Level und Supra-Token-Level. Im Zielbild wird dieselbe abstrakte Platzhaltersprache auf unterschiedliche konkrete Alphabete gemappt, um zu messen, wie stark die Modellleistung von der Symbolrepräsentation abhängt.

Die Board-Dimensionalität skaliert von 2D zu höheren Dimensionen. Für das Paper bleibt interessant, ob Modelle bei gleicher Taskgröße schlechter werden, wenn dieselben lokalen Regeln in einem höherdimensionalen Koordinatenraum angewendet werden müssen.

Die Board-Komplexität beschreibt die Größe und Struktur des Brettzustands. Sie kann über Boardgröße, Anzahl belegter Symbole, Anzahl bereits liegender Wörter, Wortlängen, Rackgröße, Anzahl möglicher Anker und Constraint-Enge wachsen.

Die Automaten-Komplexität beschreibt die Schwierigkeit der formalen Sprache. Relevante Parameter sind `k`, Anzahl und Länge verbotener Snippets, Anzahl der Zustände, Übergangsdichte, Akzeptanzdichte, minimale DFA-Größe, erlaubte Wortlängen und Anzahl akzeptierter Strings pro Länge.

Für das Target Picture können Strictly-Local-Sprachen über mixed-width forbidden snippets erzeugt werden. Bei maximalem `k = 3` können also beispielsweise verbotene Snippets der Länge `2` und `3` kombiniert werden. Dadurch lässt sich die Dichte der Sprache feiner steuern als bei einer festen Übergangsliste.

Die Transfer Matrix der Sprache kann genutzt werden, um die Anzahl gültiger Strings pro Länge effizient zu berechnen. Die Perron-Eigenvalue der Transfer Matrix gibt zusätzlich ein Signal für die asymptotische Wachstumsrate der Sprache und damit für die Dichte des Lösungsraums. Diese Werte können verwendet werden, um zufällig generierte Sprachen zu filtern und Komplexitätsklassen zu bilden.

Die Skalierungsachsen sollen getrennt steuerbar bleiben. Ein höherdimensionales Board darf nicht automatisch ein größeres oder dichteres Board sein, außer genau das ist Teil des Experiments.
