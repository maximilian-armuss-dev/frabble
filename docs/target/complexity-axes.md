# Komplexitätsachsen

Langfristig kann der Benchmark als vierdimensionaler Experimentalraum verstanden werden:

- Alphabetklasse.
- Board-Dimensionalität.
- Board-Komplexität.
- Automaten-Komplexität.

Die Alphabetklasse beschreibt, auf welcher Tokenebene die konkreten Symbole liegen. Denkbar sind Sub-Token-Level, Token-Level und Supra-Token-Level. Im Zielbild wird dieselbe abstrakte Platzhaltersprache auf unterschiedliche konkrete Alphabete gemappt, um zu messen, wie stark die Modellleistung von der Symbolrepräsentation abhängt.

Die Board-Dimensionalität skaliert von 2D zu höheren Dimensionen. Für das Paper bleibt interessant, ob Modelle bei gleicher Taskgröße schlechter werden, wenn dieselben lokalen Regeln in einem höherdimensionalen Koordinatenraum angewendet werden müssen.

Die Board-Komplexität beschreibt die Größe und Struktur des Brettzustands. Sie kann über Boardgröße, Anzahl belegter Symbole, Anzahl bereits liegender Wörter, Wortlängen, Rackgröße, Anzahl möglicher Anker und Constraint-Enge wachsen.

Die Automaten-Komplexität beschreibt die Schwierigkeit der formalen Sprache. Relevante Parameter sind Anzahl der Zustände, Übergangsdichte, Akzeptanzdichte, minimale DFA-Größe, erlaubte Wortlängen und Anzahl akzeptierter Strings pro Länge.

Die Skalierungsachsen sollen getrennt steuerbar bleiben. Ein höherdimensionales Board darf nicht automatisch ein größeres oder dichteres Board sein, außer genau das ist Teil des Experiments.
