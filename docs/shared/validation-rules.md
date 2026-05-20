# Validierungsregeln

Ein Zug ist valide, wenn alle folgenden Bedingungen erfüllt sind:

- Die Ausgabe erfüllt das erwartete JSON-Schema.
- Die angegebene `sequence` ist ein gültiges Wort der formalen Sprache.
- Die Platzierung liegt vollständig innerhalb des Boards.
- Neue Symbole widersprechen keinen bereits belegten Zellen.
- Der Zug legt mindestens ein neues Symbol.
- Der Zug verbindet sich durch mindestens eine konsistente Überlappung mit der bestehenden Boardstruktur.
- Der Zug verlängert kein bereits bestehendes Wort entlang derselben Achse.
- Alle durch den Zug entstehenden Sequenzen entlang aller relevanten Achsen sind gültige Wörter der formalen Sprache.
- Die neu zu legenden Symbole können aus dem Rack bezahlt werden.
- Wörter der Länge `<3` sind nicht gültig.

V1 akzeptiert nur Overlap-Verbindungen. Reine Nachbarschaft ohne Überlappung ist in V1 ungültig, auch wenn dadurch gültige Querwörter entstehen würden. Das reduziert die Validierung und Szenariogenerierung im Prototypen.

## Wortverlängerung

Ein Zug darf ein bestehendes Wort nicht entlang derselben Achse verlängern. Eine Verlängerung liegt vor, wenn der Zug an eine bereits vorhandene gültige Sequenz auf seiner Legerichtung andockt oder sie überlappt und durch neue Symbole zu einer längeren zusammenhängenden Sequenz macht.

Das gilt auch dann, wenn die vorhandene Sequenz nicht als eigenes Segment gespeichert wurde, sondern nur implizit aus Buchstaben anderer Kreuzungswörter entstanden ist. Entscheidend ist die Board-Geometrie vor dem Zug: Liegen auf der Legerichtung bereits mindestens drei zusammenhängende Symbole, die ein gültiges Wort der formalen Sprache bilden, darf der neue Zug diese Sequenz nicht erweitern.

Erlaubt bleibt, bestehende Symbole aus anderen Wörtern als Kreuzungen auf der Legerichtung zu nutzen, wenn diese Symbole vor dem Zug noch keine gültige zusammenhängende Sequenz auf dieser Achse bilden. Dadurch darf ein neuer Zug Lücken füllen und erst mit den neu gelegten Symbolen ein gültiges Wortbild erzeugen.

## Validierungsreihenfolge

Die geplante Validierungsreihenfolge ist:

1. Parse und normalisiere das JSON.
2. Prüfe, ob die angegebene `sequence` selbst ein gültiges Wort der Sprache ist.
3. Berechne die betroffenen Koordinaten aus `start`, `axis` und Sequenzlänge.
4. Prüfe Boardgrenzen.
5. Prüfe Overlaps und räumliche Konflikte.
6. Prüfe, ob mindestens ein neues Symbol gelegt wird.
7. Prüfe, ob mindestens eine konsistente Überlappung mit der bestehenden Boardstruktur existiert.
8. Prüfe, dass kein bestehendes Wort entlang der Legerichtung verlängert wird.
9. Simuliere den Boardzustand nach dem Zug.
10. Extrahiere alle durch den Zug entstehenden relevanten Sequenzen entlang aller Achsen.
11. Prüfe, dass alle Sequenzen der Länge mindestens `3` gültige Wörter der Sprache sind.
12. Ziehe die bereits auf dem Board liegenden, konsistent überlappten Symbole von der `sequence` ab und prüfe, ob die übrigen Symbole aus dem Rack bezahlt werden können.
13. Gib binär `valid = true` oder `valid = false` zurück und speichere zusätzlich die Fehlerklasse.

## Fehlerklassen

Auch wenn V1 nur binär bewertet, gibt der Validator intern Fehlerklassen aus:

- Schemafehler.
- ungültige Sequenz.
- Out-of-bounds-Platzierung.
- räumlicher Konflikt.
- fehlende Überlappung.
- unerlaubte Wortverlängerung.
- ungültiges Hauptwort.
- ungültiges Querwort.
- Rackfehler.
