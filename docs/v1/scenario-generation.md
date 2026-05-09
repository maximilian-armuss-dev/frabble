# V1-Szenariogenerierung

V1 generiert unabhängige Szenarien. Das LLM bekommt pro Instanz ein frisches Board und soll genau den nächsten Zug vorhersagen. Der Generator darf intern eine Kette gültiger Boardzustände aufbauen, aber diese Kette ist kein Modellkontext.

## Witness-Prinzip

Der Generator erzeugt intern Übergänge `B_t -> B_{t+1}`. Für ein Szenario wird `B_t` als Board an das Modell gegeben und der bekannte Zug nach `B_{t+1}` als Witness zurückgehalten. Dadurch ist mindestens eine Lösung bekannt, ohne dass eine vollständige Lösungsmenge berechnet wird.

## Overlap-only

V1 erzeugt und validiert nur Züge, die mindestens ein bestehendes Symbol konsistent überlappen. Reine Nachbarschaft ohne Überlappung ist ungültig. Diese Einschränkung reduziert die Kandidatensuche und macht die Validierung im Prototypen stabiler.

## Generatorbudget

Der interne Generationslauf wird beendet, sobald `8` nacheinander gesampelte Wörter nicht valide platziert werden konnten. Die Anzahl der erzeugten Boardstates ergibt sich aus dem Verlauf bis zu diesem Abbruch.

Exportierte Szenarien stammen nur aus Übergängen, für die ein Witness-Zug bekannt ist.

## Anchor-driven Candidate Enumeration

Die Generierung kombiniert zufällige Wortauswahl mit deterministischer Kandidatenkonstruktion:

1. Sample ein gültiges Wort aus der Sprache.
2. Bestimme alle Symbole im Wort, die bereits auf dem Board vorkommen.
3. Erzeuge Overlap-Kandidaten über identische Symbole statt zufällige Koordinaten zu probieren.
4. Bestimme für jede mögliche Overlap-Zelle die Achsen, auf denen sie bereits Teil einer bestehenden Sequenz ist.
5. Erzeuge Kandidaten nur entlang der anderen Achsen.
6. Prüfe jeden Kandidaten mit demselben Validator, der später Modelloutputs bewertet.
7. Wähle aus den validen Kandidaten zufällig oder nach einem einfachen Diversitätskriterium einen aus.
8. Wenn kein Kandidat valide ist, zählt das Wort als fehlgeschlagen.

Im 2D-Fall bedeutet das: Wenn die Overlap-Zelle bereits Teil einer Sequenz entlang `axis = 0` ist, darf das neue Wort dort nur entlang `axis = 1` kreuzen. Wenn die Overlap-Zelle bereits Teil einer Sequenz entlang `axis = 1` ist, darf das neue Wort dort nur entlang `axis = 0` kreuzen.

In höheren Dimensionen gilt dieselbe Regel:

```text
candidate_axes = all_axes - existing_axes_at_overlap_coord
```

Dadurch werden Kandidaten entlang derselben Achse vermieden. Das passt zur V1-Regel, dass bestehende Wörter nicht verlängert oder entlang derselben Sequenz überdeckt werden dürfen.

## Word Pool und Symbolindex

Der Generator sollte nicht jedes Wort vollständig neu suchen. Pro Sprache wird ein Pool gültiger Wörter für erlaubte Längen erzeugt. Zusätzlich wird ein Index gehalten:

```text
symbol -> Wörter, die dieses Symbol enthalten
```

Für ein konkretes Board wird außerdem ein Boardindex gehalten:

```text
symbol -> belegte Koordinaten mit diesem Symbol
```

Damit kann der Generator bevorzugt Wörter auswählen, die mindestens ein Symbol mit dem Board teilen. Das reduziert fehlgeschlagene Versuche, weil nur Wörter gesampelt werden, die überhaupt eine Overlap-Verbindung erzeugen können.

## Kandidatenwahl

Wenn mehrere valide Kandidaten existieren, kann der Generator zufällig wählen oder eine einfache Diversitätsheuristik nutzen. Geeignete Heuristiken sind:

- vermeide Platzierungen direkt am Rand, wenn es gleichwertige Alternativen gibt.
- bevorzuge Kandidaten, die das Board kompakt halten.
- bevorzuge Kandidaten, die neue Anschlussmöglichkeiten erzeugen.
- mische Achsen, damit Boards nicht fast nur in einer Richtung wachsen.

Diese Heuristiken steuern nur die Generierung. Die spätere Modellbewertung bleibt binär.

Dieser Ansatz vermeidet pure Random Search über Boardkoordinaten. Zufall bleibt nur bei Wortwahl und Auswahl zwischen validen Kandidaten erhalten.
