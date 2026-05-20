# Anchor- und Template-Scoring

Das Scoring soll das Board radial und kompakt wachsen lassen, ohne die Suche in überfüllten Regionen zu erzwingen.

Scoring wird nicht als Methode von `Board` implementiert, sondern über eine eigene Helper-Schicht wie `BoardScoring`. `Board` liefert Zustand und geometrische Analyse; `BoardScoring` berechnet daraus Heuristik-Features.

## Candidate-Reihenfolge

V1 nutzt keine gemeinsame Verteilung über Länge und Anchor-Koordinate.

Die Reihenfolge ist:

1. Wortlänge sampeln.
2. alle belegten Koordinaten als mögliche Anchors billig scoren.
3. Top-M Anchors behalten.
4. für Top-M Anchors Templates erzeugen.
5. Templates prunen und scoren.
6. Top-K Templates an das lokale Slot-CSP geben.

Damit beeinflusst die Wortlänge die Anchor-Bewertung, ohne dass ein komplexes Joint Sampling über Länge und Anchor-Koordinate nötig ist.

## Anchor-Koordinaten-Score

Eine konkrete Anchor-Koordinate wird nicht nur nach Nähe zum Zentrum bewertet. Der Score soll auch berücksichtigen, ob um den Anchor herum überhaupt Platz für die gesampelte Länge existiert.

Ein einfacher V1-Score:

```text
score =
  - bbox_area_increase
  - distance_to_centroid
  + free_cross_axis_span
```

## Features

`bbox_area_increase`: Wie stark würde ein Kandidat die Bounding Box vergrößern. Kleinere Werte sind besser.

`distance_to_centroid`: Abstand des Anchor zur aktuellen Boardmitte. Kleinere Werte fördern radiales Wachstum.

`free_cross_axis_span`: Anzahl freier oder geometrisch nutzbarer Zellen entlang der Zielachse um den Anchor herum. Größere Werte bedeuten, dass die Region mehr Spielraum für die gesampelte Wortlänge hat.

Für den Anchor-Score wird kein exakter Template-Count berechnet. `free_cross_axis_span` ist eine billige Approximation, die verhindert, dass vor dem eigentlichen Template-Ranking bereits alle Templates vollständig erzeugt und geprüft werden müssen.

Die besten `top_anchor_count` Anchors werden expandiert. Für V1 ist `top_anchor_count = 12` ein sinnvoller Default.

## Template-Score

Wenn mehrere Templates für einen Anchor übrig bleiben, werden kompakte Templates bevorzugt:

```text
template_score =
  - bbox_area_increase
  - distance_of_new_cells_to_centroid
  + 1.5 * new_cell_count
  - 1.0 * local_adjacent_density
```

`new_cell_count`: Anzahl neu belegter Zellen durch das Template. Mehr neue Zellen sind besser, weil der Generator nicht bevorzugt einzelne Buchstaben in fast fertige Strukturen quetschen soll.

`local_adjacent_density`: Anzahl bereits belegter orthogonaler Nachbarzellen um die neu belegten Template-Zellen. Diagonalen zählen nicht, und Nachbarn innerhalb der neuen Template-Zellen zählen nicht. Höhere Dichte ist schlechter.

Bei gleichem Score wird deterministisch das erste Template in der stabil sortierten Reihenfolge genommen. Es wird kein zusätzliches Template-Sampling verwendet.

Die besten `top_template_count` Templates werden an das lokale Slot-CSP gegeben. Für V1 ist `top_template_count = 120` ein sinnvoller Default.

Die Heuristik bevorzugt weiterhin kompakte Boards. Damit daraus kein deterministisches Quadrat entsteht, muss die Config eine echte Längenrange verwenden; V1 sampelt inklusiv von `start = 3` bis `end = 7`. Eine Range mit `start = end = 7` ist nur für Debugging sinnvoll.
