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

Ein Zug darf ein bestehendes Wort nicht entlang derselben Achse verlängern. Eine Verlängerung liegt vor, wenn auf einer Achse bereits eine Sequenz liegt und der neue Zug entlang derselben Achse direkt benachbart so platziert wird, dass beide Sequenzen als eine einzige längere Sequenz interpretiert werden könnten.

Erlaubt bleibt, ein bestehendes Symbol als Kreuzung auf einer anderen Achse zu nutzen, solange die neue Sequenz und alle entstehenden Sequenzen gültig sind.

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
