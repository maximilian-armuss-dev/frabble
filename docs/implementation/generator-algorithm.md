# Generator-Algorithmus

Der Generator baut intern ein unbounded Board auf. Aus jedem erfolgreichen Übergang kann ein Szenario mit Witness extrahiert werden.

## Reproduzierbarkeit

Die Generierung muss seeded ablaufen. Gleiche Generatorconfig plus gleicher Seed muss dieselben Szenarien erzeugen. Unterschiedliche Seeds dürfen andere, aber ebenfalls reproduzierbare Szenarien erzeugen.

Alle zufälligen Entscheidungen nutzen denselben kontrollierten RNG oder deterministisch abgeleitete Child-Seeds. Dazu gehören:

- initiales Wort.
- Wortlänge.
- eventuelle Auswahl aus gleichwertigen Kandidaten, falls Sampling aktiviert wird.

Sortierungen sind stabil. Bei gleichem Score wird deterministisch nach festen Feldern sortiert, zum Beispiel nach Koordinate, Achse, Anchor-Index und Sequenz. Dadurch hängt das Ergebnis nicht von Dictionary-Iteration oder Set-Reihenfolgen ab.

## Ablauf

1. Starte mit einem leeren Board.
2. Sample ein initiales gültiges Wort aus der V1-Sprache.
3. Lege das initiale Wort entlang `axis = 0` um den Ursprung.
4. Speichere das erste Segment.
5. Wiederhole bis zum Abbruch:
   - sample eine Wortlänge aus der erlaubten Längenverteilung.
   - score alle belegten Koordinaten billig als mögliche Anchors.
   - behalte die Top-M Anchors.
   - bestimme pro Top-M Anchor die Zielachse über Criss-Cross-Logik.
   - erzeuge SlotTemplates für alle möglichen Anchor-Indizes dieser Länge.
   - prune geometrisch unmögliche Templates.
   - score alle übrigen Templates.
   - behalte die Top-K Templates.
   - löse pro Top-K Template ein lokales Slot-CSP.
   - bei Lösung: platziere Wort, speichere Segment, speichere Transition als Witness.
   - bei keiner Lösung: gehe ins Backoff-Modell.

## Globaler Candidate-Ansatz

V1 sampelt nicht zuerst ein einzelnes Anchor-Symbol. Stattdessen wird pro Schritt eine Wortlänge gesampelt und anschließend ein globaler Kandidatenpool aufgebaut.

Der Ablauf ist:

```text
sample length L
score all occupied coords as anchors
top_anchors = top M anchors
templates = expand top_anchors for length L
templates = cheap geometry prune
top_templates = top K templates by template_score
try slot CSP for top_templates in order
```

Dadurch entscheidet nicht die Symbolfrequenz allein, sondern die konkrete geometrische Qualität eines Anchors und seiner Templates. Das reduziert schlechte frühe Anchor-Entscheidungen, begrenzt aber trotzdem die Compute-Kosten.

Für V1 sind sinnvolle Defaults:

```text
top_anchor_count = 12
top_template_count = 24
```

Diese Werte sind Generatorparameter und werden mit der Config gespeichert.

## Criss-Cross-Achsenlogik

Im 2D-Fall gilt:

- Wenn der Anchor Teil eines bestehenden Wortes entlang `axis = 0` ist, wird entlang `axis = 1` gelegt.
- Wenn der Anchor Teil eines bestehenden Wortes entlang `axis = 1` ist, wird entlang `axis = 0` gelegt.

In höheren Dimensionen wird später eine Ordnung über die zulässigen Cross-Achsen definiert. V1 implementiert nur den 2D-Fall.

## Template-Pruning

Bevor ein Template an den Solver geht, werden einfache geometrische Fälle entfernt:

- das Template enthält nicht die Anchor-Koordinate an `anchor_index`.
- eine belegte Zelle im Slot enthält ein anderes Symbol als das später dort fixierte Symbol.
- der Slot würde ein bestehendes Wort entlang derselben Achse verlängern.
- der Slot läuft entlang derselben Achse in ein bestehendes Segment hinein.
- das Template hat keine konsistente Overlap-Verbindung.

Das Pruning soll billig sein. Es ersetzt nicht den Validator, sondern reduziert nur die Anzahl der Solver-Aufrufe.

## Deterministische Candidate-Wahl

Alle Anchors und Templates werden stabil sortiert. Templates werden in Score-Reihenfolge an das lokale Slot-CSP gegeben. Wenn mehrere Templates denselben Score haben, wird das erste Template in stabiler Sortierreihenfolge genutzt.

Dadurch ist die Generierung bei gleicher Config und gleichem Seed reproduzierbar.

## Logging

Für jedes generierte Szenario sollen gespeichert werden:

- Generatorconfig.
- Seed.
- Sprach-ID und forbidden snippets.
- Wortlängenverteilung.
- Top-M Anchor-Koordinaten und Scores.
- Top-K Templates und Scores.
- Solverstatus pro versuchtem Template.
- Witness-Move.

## Witness

Wenn der Solver ein Wort für ein Template findet, entsteht ein Move. Vor dem Anwenden wird der Move mit dem regulären Validator geprüft. Der Lauf wird inkrementell gespeichert: einmal das Initial-Board und danach pro Witness nur der Übergang.

```text
initial_board = board_after_initial_word
transition:
  rack = rack_before_move
  move = full_move
  placed = newly_occupied_cells
  search_log = solver_and_candidate_trace
```

Ein Board vor oder nach einem Witness wird bei Bedarf aus `initial_board` plus den vorherigen Transitions rekonstruiert. Dadurch werden Board-Kopien im internen Modell und im JSON-Export vermieden.
