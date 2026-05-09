# Sprachmodell

Die formale Sprache wird unabhängig von der konkreten sichtbaren Symbolrepräsentation definiert. Intern kann die Sprache mit Platzhaltern wie `A`, `B`, `C` oder abstrakten Symbol-IDs arbeiten. Erst in einem separaten Mapping-Schritt werden diese Platzhalter auf konkrete sichtbare Einheiten abgebildet.

## Platzhalter und Mapping

Für V1 wird noch kein echtes Tokenizer-Mapping genutzt. Die Platzhalter werden direkt als einfache Buchstaben angezeigt. Praktisch kann das sichtbare Alphabet aus `A` bis `Z` bestehen, während eine konkrete Sprache zunächst nur eine Teilmenge von `6` Symbolen verwendet.

Das spätere Mapping muss bidirektional sein. Wenn der Platzhalter `A` beispielsweise auf das sichtbare Symbol `Haus` gemappt wird, muss der Validator `Haus` wieder eindeutig auf `A` zurückführen können. Mehrzeichen-Symbole sind deshalb von Anfang an mitzudenken; die Modellantwort liefert `sequence` als Liste von Symbolen, nicht als zusammengezogenen String.

## Strictly Local Languages

Strictly Local Languages sind eine eingeschränkte Klasse regulärer Sprachen. Eine Sprache ist `k`-strictly-local, wenn die Gültigkeit eines Wortes durch erlaubte lokale Teilstrings der Länge `k` bestimmt wird, typischerweise inklusive Wortgrenzen. Vereinfacht: Ein Wort ist gültig, wenn alle seine lokalen Fenster erlaubt sind.

Für V1 gilt `k = 2`. Damit kann die Sprache als gerichteter Graph über Symbolen verstanden werden. Ein Wort ist gültig, wenn jedes benachbarte Symbolpaar einer erlaubten Kante entspricht.

## Adjazenzlisten

Für V1 wird die Sprache textbasiert als Adjazenzliste erklärt. Eine Adjazenzliste beschreibt für jedes Symbol, welche Symbole direkt danach kommen dürfen.

Beispiel:

```text
A: B, C
B: A
C: A, B
```

Diese Liste bedeutet: Nach `A` darf `B` oder `C` kommen, nach `B` nur `A`, nach `C` `A` oder `B`. Die Sequenz `A B A C B` ist gültig, weil alle lokalen Übergänge erlaubt sind. Die Sequenz `A A B` ist ungültig, weil `A -> A` nicht erlaubt ist.

Konkrete Promptbeispiele können aus den Sprachdefinitionen autogeneriert werden.

## Komplexitätsparameter

Für jede Sprache werden mindestens folgende Kennzahlen gespeichert:

- Alphabetgröße.
- Wortlängenbereich.
- Anzahl erlaubter Übergänge.
- Übergangsdichte relativ zu allen möglichen Übergängen.
- Anteil akzeptierter Strings pro Länge, soweit effizient berechenbar oder schätzbar.
- Anzahl erreichbarer und produktiver Symbole.
- Größe des daraus abgeleiteten minimalen DFA.
