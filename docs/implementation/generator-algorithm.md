# Generator-Algorithmus

Der Generator baut intern ein unbounded Board auf. Aus jedem erfolgreichen Übergang kann ein Szenario mit Witness extrahiert werden.

## Reproduzierbarkeit

Die Generierung muss seeded ablaufen. Gleiche Generatorconfig plus gleicher Seed muss dieselben Szenarien erzeugen. Unterschiedliche Seeds dürfen andere, aber ebenfalls reproduzierbare Szenarien erzeugen.

Alle zufälligen Entscheidungen nutzen denselben kontrollierten RNG oder deterministisch abgeleitete Child-Seeds. Dazu gehören:

- initiales Wort.
- Wortlänge.

Sortierungen sind stabil. Bei gleichem Score wird deterministisch nach festen Feldern sortiert, zum Beispiel nach Koordinate, Achse, Anchor-Index und Sequenz.

## Ablauf

1. Starte mit einem leeren Board.
2. Sample ein initiales gültiges Wort aus der V1-Sprache.
3. Lege das initiale Wort entlang `axis = 0` um den Ursprung.
4. Speichere das erste Segment.
5. Wiederhole bis zum Abbruch:
   - sample eine Wortlänge aus der erlaubten Längenverteilung.
   - score und sortiere alle Anchor-Achsen-Paare billig.
   - expandiere zunächst nur den nächsten Anchor-Batch.
   - erzeuge SlotTemplates für alle möglichen Anchor-Indizes dieser Länge.
   - prune geometrisch unmögliche Templates, doppelte Slots und deterministische Wortverlängerungen auf allen berührten Achsen.
   - extrahiere Cross-Domains und prune Templates mit mindestens einer leeren Domain.
   - score die verbleibenden Templates inklusive Domain-Slack.
   - löse Templates bis zum kumulativen Top-K-CSP-Budget.
   - bei keinem Erfolg: expandiere nur den nächsten noch nicht betrachteten Anchor-Batch.
   - bei Lösung: platziere Wort, speichere Segment, speichere Transition als Witness.
   - bei keiner Lösung: markiere die Länge für diesen Board-State als verbraucht und beginne von vorn, bis der Pool an möglichen Längen erschöpft ist.

## Feasibility-Aware Candidate-Ansatz

V1 sampelt nicht zuerst ein einzelnes Anchor-Symbol. Stattdessen wird pro Schritt eine Wortlänge gesampelt und anschließend ein globaler Kandidatenpool aufgebaut.

Der Ablauf ist:

```text
sample length L
score and sort all anchor-axis candidates once
for fresh batch in sorted_anchors[0:40], [40:80], ...:
    templates = expand only fresh batch for length L
    templates = geometry / duplicate / any-axis deterministic-extension prune
    templates = cross-domain extraction and empty-domain prune
    templates = rank feasible templates including domain slack
    try new templates while cumulative CSP attempts < K
    stop on first valid move
```

Dadurch bleibt zentrale Expansion die erste Präferenz, blockiert die Suche aber nicht dauerhaft: Liefert ein dichter innerer Batch keine machbaren Templates, werden ohne Wiederholung weiter außen liegende Anchors untersucht, solange das kumulative CSP-Budget noch nicht ausgeschöpft ist. Exakte Feasibility wird auf Template-Ebene bewertet, weil erst das konkrete Template seine Cross-Wort-Constraints bestimmt.

Pro unverändertem Board-State wird jede Länge aus der konfigurierten Range höchstens einmal gesampelt. Wenn keine Länge einen Move erzeugt, bricht der Generator mit einem Failure-Report ab. Nach einem erfolgreichen Move wird die Längenrange für den neuen Board-State wieder frisch verwendet.

Für V1 sind sinnvolle Defaults:

```text
top_anchor_count = 40
top_template_count = 120
max_anchor_count = null
```

`top_anchor_count` ist die Größe eines Anchor-Batches, nicht mehr der zwingende Gesamtabbruch nach den zentralsten Anchors. `top_template_count` begrenzt CSP-Versuche je Wortlänge kumulativ über alle Batches. `max_anchor_count` ist optional und schränkt das Widening hart ein.

Die Längenverteilung ist eine inklusive Range:

```text
length_distribution.start = 3
length_distribution.end = 7
```

Eine Range mit `start = end = 7` sampelt zwar formal pro Schritt neu, erzeugt aber praktisch immer gleich breite Slots; zusammen mit Centroid-Heuristik führt das zu einem sehr regelmäßigen Auffüllen.

## Criss-Cross-Achsenlogik

Für jeden Anchor werden alle Achsen erzeugt, auf denen die Anchor-Koordinate noch nicht Teil eines bestehenden Wortes ist. Im 2D-Fall ergibt das die klassische Criss-Cross-Logik:

- Wenn der Anchor Teil eines bestehenden Wortes entlang `axis = 0` ist, wird entlang `axis = 1` gelegt.
- Wenn der Anchor Teil eines bestehenden Wortes entlang `axis = 1` ist, wird entlang `axis = 0` gelegt.

Im 3D-Fall kann eine Anchor-Koordinate mehrere Zielachsen erzeugen. Liegt ein Tile nur auf `axis = 0`, entstehen Kandidaten entlang `axis = 1` und `axis = 2`. Liegt ein Tile bereits auf `axis = 0` und `axis = 1`, bleibt nur `axis = 2`. Die spätere stabile Sortierung über Score, Koordinate und Achse hält die Generierung reproduzierbar, die Beschränkung auf Top-K Kandidaten hält sie kompakt.

## Template-Pruning

Bevor ein Template an den Solver geht, werden einfache geometrische Fälle entfernt:

- das Template enthält nicht die Anchor-Koordinate an `anchor_index`.
- eine belegte Zelle im Slot enthält ein anderes Symbol als das später dort fixierte Symbol.
- der Slot würde ein bestehendes Wort entlang derselben Achse verlängern.
- der Slot läuft entlang derselben Achse in ein bestehendes Segment hinein.
- das Template hat keine konsistente Overlap-Verbindung.
- der Slot ist ein Duplikat eines bereits aus einem anderen Anchor betrachteten geometrischen Slots.
- der Slot würde eine bereits vorhandene gültige Sequenz auf der Legeachse oder auf einer durch neue Tiles berührten Cross-Achse deterministisch verlängern.
- mindestens eine Cross-Domain ist leer, also erlaubt für eine neue Zelle kein Symbol ein gültiges Kreuzwort.

Ein Cross-Wort darf damit neu entstehen, aber kein bereits gültiges Wort verlängern. Die berechneten nicht-leeren Domains werden für den nachfolgenden Slot-CSP wiederverwendet. Das Pruning ersetzt nicht den Validator, sondern reduziert Solver-Aufrufe und verhindert, dass beweisbar unmögliche Innenkandidaten das Top-K-Budget verbrauchen.

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
