# Sprachmodell

Die formale Sprache wird unabhängig von der konkreten sichtbaren Symbolrepräsentation definiert. Intern kann die Sprache mit Platzhaltern wie `A`, `B`, `C` oder abstrakten Symbol-IDs arbeiten. Erst in einem separaten Mapping-Schritt werden diese Platzhalter auf konkrete sichtbare Einheiten abgebildet.

## Platzhalter und Mapping

Für V1 wird noch kein echtes Tokenizer-Mapping genutzt. Die Platzhalter werden direkt als einfache Buchstaben angezeigt. Praktisch kann das sichtbare Alphabet aus `A` bis `Z` bestehen, während eine konkrete Sprache zunächst nur eine Teilmenge von `6` Symbolen verwendet.

Das spätere Mapping muss bidirektional sein. Wenn der Platzhalter `A` beispielsweise auf das sichtbare Symbol `Haus` gemappt wird, muss der Validator `Haus` wieder eindeutig auf `A` zurückführen können. Mehrzeichen-Symbole sind deshalb von Anfang an mitzudenken; die Modellantwort liefert `sequence` als Liste von Symbolen, nicht als zusammengezogenen String.

## Strictly Local Languages

Strictly Local Languages sind eine eingeschränkte Klasse regulärer Sprachen. Eine Sprache ist `k`-strictly-local, wenn die Gültigkeit eines Wortes durch lokale Teilstrings der Länge höchstens `k` bestimmt wird. Für den Benchmark wird die Sprache bevorzugt über verbotene Snippets beschrieben.

Ein Wort ist gültig, wenn es kein verbotenes Snippet enthält und die minimale Wortlänge erfüllt.

Beispiel mit Alphabet `{A, B, C}`, `k = 3` und forbidden snippets `{AAA, BCB}`:

- `ABCABC` ist gültig.
- `AAAB` ist ungültig, weil `AAA` vorkommt.
- `ABCB` ist ungültig, weil `BCB` vorkommt.

## Forbidden-Snippet-Approach

Der forbidden-snippet-Approach ist für Skalierung geeignet, weil die Dichte der Sprache über Anzahl und Struktur verbotener Snippets kontrolliert werden kann. Werden mehr lokale Muster verboten, sinkt die Anzahl gültiger Strings. Werden weniger lokale Muster verboten, wird die Sprache dichter.

Für V1 kann eine einzelne einfache Strictly-Local-Sprache fest definiert werden. Für das Target Picture können forbidden snippets zufällig gesampelt werden.

## Adjazenzlisten

Für `k = 2` kann eine forbidden-snippet-Sprache äquivalent als Adjazenzliste dargestellt werden. Eine Adjazenzliste beschreibt für jedes Symbol, welche Symbole direkt danach kommen dürfen.

Beispiel:

```text
A: B, C
B: A
C: A, B
```

Diese Liste bedeutet: Nach `A` darf `B` oder `C` kommen, nach `B` nur `A`, nach `C` `A` oder `B`. Die Sequenz `A B A C B` ist gültig. Die Sequenz `A A B` ist ungültig, weil `A -> A` nicht erlaubt ist.

Adjazenzlisten bleiben eine gute Prompt-Repräsentation für `k = 2`, auch wenn die interne Generierung über forbidden snippets beschrieben wird.
