# Puzzle-Generierung

Das langfristige Ziel ist eine Pipeline, die viele unabhängige Szenarien erzeugt und dabei Solvability, Schwierigkeit und Lösungsmengen kontrollieren kann.

## Teilprobleme

Die Pipeline besteht aus drei gekoppelten Teilproblemen:

- Sampling formaler Sprachen oder Automaten mit kontrollierbarer Komplexität.
- Charakterisierung des Lösungsraums, zum Beispiel Anzahl akzeptierter Strings pro Länge.
- Konstruktion von Boards mit bekannter Lösbarkeit und kontrollierbarer Schwierigkeit.
Das LLM bekommt pro Instanz ein frisches Board und soll genau den nächsten Zug vorhersagen. Der Generator darf intern eine Kette gültiger Boardzustände aufbauen, aber diese Kette ist kein Modellkontext.

## Witness-Prinzip

Der Generator erzeugt intern Übergänge `B_t -> B_{t+1}`. Für ein Szenario wird `B_t` als Board an das Modell gegeben und der bekannte Zug nach `B_{t+1}` als Witness zurückgehalten. Dadurch ist mindestens eine Lösung bekannt, ohne dass eine vollständige Lösungsmenge berechnet wird.

## Overlap-only

V1 erzeugt und validiert nur Züge, die mindestens ein bestehendes Symbol konsistent überlappen. Reine Nachbarschaft ohne Überlappung ist ungültig. Diese Einschränkung reduziert die Kandidatensuche und macht die Validierung im Prototypen stabiler.

## Criss-Cross Generation

Der V1-Generator baut intern ein Criss-Cross-Board auf.

In 2D alterniert die Legerichtung effektiv:

```text
axis = 0, dann axis = 1, dann axis = 0, dann axis = 1, ...
```

Ein neues Wort wird über ein gemeinsames Symbol mit der bestehenden Struktur gekreuzt. Wenn das bestehende Wort an der Overlap-Koordinate entlang `axis = 0` liegt, wird das neue Wort entlang `axis = 1` gelegt. Wenn das bestehende Wort dort entlang `axis = 1` liegt, wird das neue Wort entlang `axis = 0` gelegt.

In 3D werden pro Anchor alle Achsen berücksichtigt, auf denen die Anchor-Koordinate noch nicht Teil eines bestehenden Wortes ist. Dieser Ansatz vermeidet Kandidaten entlang derselben Achse und passt zur Regel, dass bestehende Wörter nicht verlängert oder entlang derselben Sequenz überdeckt werden dürfen.

## Unbounded Generation und ROI

Die interne Generierung ist nicht durch eine feste Boardgröße beschränkt. Der Generator kann Koordinaten in einem unbeschränkten zwei- oder dreidimensionalen Raum verwenden und daraus später eine Region of Interest ableiten.

Für das Modell werden alle relevanten belegten Symbole mit Koordinaten sowie eine Bounding Box oder Boardshape ausgegeben. Dadurch wird die Generierung weniger fragil, während die Modellantwort weiterhin einfach über Bounds validiert werden kann.

## Generatorbudget

Der interne Generationslauf wird beendet, sobald `8` nacheinander gesampelte Wörter nicht valide platziert werden konnten. Die Anzahl der erzeugten Boardstates ergibt sich aus dem Verlauf bis zu diesem Abbruch.

Exportierte Szenarien stammen nur aus Übergängen, für die ein Witness-Zug bekannt ist.

## Rack-Strategie als Core Choice

Für die Puzzle-Generierung gibt es eine zentrale offene Designentscheidung:

- Rack-first: Ein Rack wird vorgegeben, danach wird ein gültiges Wort gesucht.
- Witness-first: Zuerst wird ein valides nächstes Wort generiert, danach wird das Rack aus diesem Wort abgeleitet und optional mit Noise-Symbolen ergänzt.

Diese Entscheidung wird nicht im V1-Konzept festgelegt. Sie ist ein Kernpunkt für weitere Recherche und Experimente, weil sie stark beeinflusst, wie schwierig und kontrollierbar Szenarien werden.
