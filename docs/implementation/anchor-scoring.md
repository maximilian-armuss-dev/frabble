# Anchor- und Template-Scoring

Das Scoring soll das Board radial und kompakt wachsen lassen, ohne die Suche in überfüllten Regionen zu erzwingen.

Scoring wird nicht als Methode von `Board` implementiert, sondern über eine eigene Helper-Schicht wie `BoardScoring`. `Board` liefert Zustand und geometrische Analyse; `BoardScoring` berechnet daraus Heuristik-Features.

Die Gewichte stehen in der Generator-YAML unter `scoring`, damit Heuristik-Tuning ohne Codeänderung möglich ist. Höhere Gewichte verstärken den jeweiligen Effekt; alle Werte müssen nicht-negativ sein.

Raw-Features werden vor dem gewichteten Score pro Kandidatenpool mit Min-Max auf `[0, 1]` normalisiert. Anchor-Features werden über den aktuellen Anchor-Pool normalisiert, Template-Features über den aktuellen Template-Pool. Wenn ein Feature im Pool überall denselben Wert hat, wird es für alle Kandidaten als `0.0` gewertet. Dadurch verhalten sich die YAML-Werte als relative Gewichte statt als Korrekturfaktoren für unterschiedlich skalierte Rohwerte.

```yaml
scoring:
  anchor_centroid_weight: 1.0
  anchor_free_span_weight: 1.0
  template_bbox_weight: 1.0
  template_centroid_weight: 1.0
  template_new_cell_bonus_weight: 1.5
  template_local_density_penalty_weight: 1.0
```

## Candidate-Reihenfolge

Die Reihenfolge ist:

1. Wortlänge sampeln.
2. Alle belegten Koordinaten als mögliche Anchors billig scoren.
3. Top-M Anchors behalten.
4. Für Top-M Anchors Templates erzeugen.
5. Templates prunen und scoren.
6. Top-K Templates an das lokale Slot-CSP geben.

Damit beeinflusst die Wortlänge die Anchor-Bewertung, ohne dass ein komplexes Joint Sampling über Länge und Anchor-Koordinate nötig ist.

## Anchor-Score

Eine konkrete Anchor-Koordinate wird nicht nur nach Nähe zum Zentrum bewertet. Der Score soll auch berücksichtigen, ob um den Anchor herum überhaupt Platz für die gesampelte Länge existiert.

```text
anchor_score =
  - anchor_centroid_weight  * norm(distance_to_centroid)
  + anchor_free_span_weight * norm(free_cross_axis_span)
```

`distance_to_centroid`: Abstand des Anchors zur aktuellen Boardmitte. `anchor_centroid_weight` höher zieht die Suche stärker in die Mitte; niedriger erlaubt mehr Rand- und Frontier-Wachstum.

`free_cross_axis_span`: Anzahl freier oder geometrisch nutzbarer Slots entlang der Zielachse um den Anchor herum. `anchor_free_span_weight` höher bevorzugt Anchors mit mehr Platz und kann Sackgassen reduzieren; zu hoch kann kompakte Qualitätsmerkmale überstimmen.

Für den Anchor-Score wird kein exakter Template-Count berechnet. `free_cross_axis_span` ist eine billige Approximation, die verhindert, dass vor dem eigentlichen Template-Ranking bereits alle Templates vollständig erzeugt und geprüft werden müssen.

Die besten `top_anchor_count` Anchors werden expandiert. Der Wert ist ein Compute-Limit in der YAML.

Bounding-Box-Wachstum wird bewusst nicht im Anchor-Score verwendet. Beim Anchor wäre es nur eine grobe Approximation über mehrere mögliche Slots und kann gute Anchors unfair abwerten. Die konkrete Bounding-Box-Entscheidung passiert im Template-Score.

## Template-Score

Wenn mehrere Templates für einen Anchor übrig bleiben, werden kompakte Templates bevorzugt, aber dichte Innenbereiche und Ein-Buchstaben-Anbauten werden abgeschwächt:

```text
template_score =
  - template_bbox_weight                  * norm(bbox_area_increase)
  - template_centroid_weight              * norm(distance_of_new_cells_to_centroid)
  + template_new_cell_bonus_weight        * norm(new_cell_count)
  - template_local_density_penalty_weight * norm(local_adjacent_density)
```

`bbox_area_increase`: Wie stark das konkrete Template die Bounding Box vergrößert. `template_bbox_weight` höher verhindert ausufernde Arme; niedriger erleichtert Außenexpansion.

`distance_of_new_cells_to_centroid`: Mittlerer Abstand der neu belegten Zellen zum Schwerpunkt. `template_centroid_weight` höher füllt eher innen und zentral; niedriger gibt Randkandidaten mehr Chancen.

`new_cell_count`: Anzahl neu belegter Zellen durch das Template. `template_new_cell_bonus_weight` höher reduziert Ein-Buchstaben-Anbauten und Lochstopfen; zu hoch kann lange Außenstücke bevorzugen.

`local_adjacent_density`: Anzahl bereits belegter orthogonaler Nachbarzellen um die neu belegten Template-Zellen. Diagonalen zählen nicht, und Nachbarn innerhalb der neuen Template-Zellen zählen nicht. `template_local_density_penalty_weight` höher vermeidet dichte Innenbereiche; zu hoch kann legitime Kreuzungen in gewachsenen Regionen verdrängen.

Bei gleichem Score wird deterministisch das erste Template in der stabil sortierten Reihenfolge genommen. Es wird kein zusätzliches Template-Sampling verwendet.

Die besten `top_template_count` Templates werden an das lokale Slot-CSP gegeben. Der Wert ist ein Compute-Limit in der YAML.

Die Heuristik bevorzugt weiterhin kompakte Boards. Damit daraus kein deterministisches Quadrat entsteht, muss die Config eine echte Längenrange verwenden; V1 sampelt inklusiv von `start = 3` bis `end = 7`. Eine Range mit `start = end = 7` ist nur für Debugging sinnvoll.

Praktische Tuning-Richtung: Wenn der Generator zu viel in dichten Mittelzonen probiert, `template_local_density_penalty_weight` erhöhen oder `template_centroid_weight` senken. Wenn das Board zu stark ausfranst, `template_bbox_weight` erhöhen.
