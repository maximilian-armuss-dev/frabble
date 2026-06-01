# Anchor- und Template-Scoring

Das Scoring soll das Board radial und kompakt wachsen lassen, ohne die Suche in überfüllten Regionen zu erzwingen.

Scoring wird nicht als Methode von `Board` implementiert, sondern über eine eigene Helper-Schicht wie `BoardScoring`. `Board` liefert Zustand und geometrische Analyse; `BoardScoring` berechnet daraus Heuristik-Features.

Die Gewichte stehen in der Generator-YAML unter `scoring`, damit Heuristik-Tuning ohne Codeänderung möglich ist. Höhere Gewichte verstärken den jeweiligen Effekt; alle Werte müssen nicht-negativ sein.

Raw-Features werden vor dem gewichteten Score pro Kandidatenpool mit Min-Max auf `[0, 1]` normalisiert. Anchor-Features werden über den aktuellen Anchor-Pool normalisiert, Template-Features über den aktuellen Template-Pool. Wenn ein Feature im Pool überall denselben Wert hat, wird es für alle Kandidaten als `0.0` gewertet. Dadurch verhalten sich die YAML-Werte als relative Gewichte statt als Korrekturfaktoren für unterschiedlich skalierte Rohwerte.

```yaml
scoring:
  anchor_centroid_weight: 1.0
  anchor_free_span_weight: 1.0
  template_centroid_weight: 1.0
  template_new_cell_bonus_weight: 1.5
  template_local_density_penalty_weight: 1.0
  template_domain_slack_weight: 1.0
```

## Candidate-Reihenfolge

Die Reihenfolge ist:

1. Wortlänge sampeln.
2. Alle zulässigen Anchor-Achsen-Paare billig scoren.
3. Anchors einmal stabil sortieren.
4. Den nächsten, noch nicht geprüften Anchor-Batch expandieren.
5. Templates mit deterministischen Wortverlängerungen auf berührten Achsen oder leeren Cross-Domains entfernen.
6. Machbare Templates inklusive Domain-Slack scoren.
7. Bis zum globalen CSP-Budget die besten Templates versuchen; bei Bedarf den nächsten Anchor-Batch öffnen.

Damit beeinflusst die Wortlänge die Anchor-Bewertung, ohne dass ein komplexes Joint Sampling über Länge und Anchor-Koordinate nötig ist.

## Anchor-Score

Ein konkretes Anchor-Achsen-Paar wird nicht nur nach Nähe zum Zentrum bewertet. Der Score soll auch berücksichtigen, ob entlang der Zielachse um den Anchor herum überhaupt Platz für die gesampelte Länge existiert.

```text
anchor_score =
  - anchor_centroid_weight  * norm(distance_to_centroid)
  + anchor_free_span_weight * norm(free_cross_axis_span)
```

`distance_to_centroid`: Abstand des Anchors zur aktuellen Boardmitte. `anchor_centroid_weight` höher zieht die Suche stärker in die Mitte; niedriger erlaubt mehr Rand- und Frontier-Wachstum.

`free_cross_axis_span`: Anzahl freier oder geometrisch nutzbarer Slots entlang der Zielachse um den Anchor herum. `anchor_free_span_weight` höher bevorzugt Anchors mit mehr Platz und kann Sackgassen reduzieren; zu hoch kann kompakte Qualitätsmerkmale überstimmen.

Für den Anchor-Score wird kein exakter Feasibility-Count berechnet. `free_cross_axis_span` ist eine billige Approximation, die die Reihenfolge für die spätere genaue Template-Prüfung bestimmt. Ob ein Anchor tatsächlich legbare Templates liefert, wird erst beim Expandieren seines Batches festgestellt.

`top_anchor_count` bezeichnet die Batchgröße: Zuerst werden beispielsweise Anchors `1..40` expandiert, danach bei Bedarf ausschließlich `41..80`. Ein Anchor wird im selben Board-State und für dieselbe Wortlänge nicht erneut expandiert. `max_anchor_count` kann optional eine harte Obergrenze setzen; ohne Wert können weitere gerankte Anchors schrittweise betrachtet werden, solange das kumulative CSP-Budget noch nicht ausgeschöpft ist.

## Template-Score

Wenn mehrere Templates für einen Anchor übrig bleiben, werden zentrale neue Zellen bevorzugt, aber dichte Innenbereiche und Ein-Buchstaben-Anbauten werden abgeschwächt:

```text
template_score =
  - template_centroid_weight              * norm(distance_of_new_cells_to_centroid)
  + template_new_cell_bonus_weight        * norm(new_cell_count)
  - template_local_density_penalty_weight * norm(local_adjacent_density)
  + template_domain_slack_weight          * norm(domain_slack)
```

`distance_of_new_cells_to_centroid`: Mittlerer Abstand der neu belegten Zellen zum Schwerpunkt. `template_centroid_weight` höher füllt eher innen und zentral; niedriger gibt Randkandidaten mehr Chancen.

`new_cell_count`: Anzahl neu belegter Zellen durch das Template. `template_new_cell_bonus_weight` höher reduziert Ein-Buchstaben-Anbauten und Lochstopfen; zu hoch kann lange Außenstücke bevorzugen.

`local_adjacent_density`: Anzahl bereits belegter orthogonaler Nachbarzellen um die neu belegten Template-Zellen. Diagonalen zählen nicht, und Nachbarn innerhalb der neuen Template-Zellen zählen nicht. `template_local_density_penalty_weight` höher vermeidet dichte Innenbereiche; zu hoch kann legitime Kreuzungen in gewachsenen Regionen verdrängen.

`domain_slack`: Summe der nach den Cross-Wort-Constraints noch erlaubten Symbole über alle neu zu belegenden Zellen. Eine leere Domain bedeutet, dass an mindestens einer Position kein Symbol alle erzeugten Kreuzwörter gültig machen kann; solche Templates werden vor dem Ranking entfernt. Ein höherer `template_domain_slack_weight` bevorzugt unter den verbleibenden Templates sprachlich flexiblere Platzierungen.

Bei gleichem Score wird deterministisch das erste Template in der stabil sortierten Reihenfolge genommen. Es wird kein zusätzliches Template-Sampling verwendet.

`top_template_count` ist das kumulative CSP-Versuchsbudget pro Wortlänge und Board-State über alle geöffneten Anchor-Batches. Geometrisch ungültige Templates, deterministische Wortverlängerungen, Duplikate desselben Slots und Templates mit leerer Domain verbrauchen dieses Budget nicht.

Die Heuristik bevorzugt weiterhin zentrale Expansion. Damit daraus kein deterministisches Quadrat entsteht, muss die Config eine echte Längenrange verwenden; V1 sampelt inklusiv von `start = 3` bis `end = 7`. Eine Range mit `start = end = 7` ist nur für Debugging sinnvoll.

Praktische Tuning-Richtung: Wenn machbare, aber fragile Innen-Templates zu oft bevorzugt werden, `template_domain_slack_weight` erhöhen. Wenn die Form trotz machbarer Alternativen zu dicht wird, `template_local_density_penalty_weight` erhöhen oder `template_centroid_weight` senken. Wenn Ein-Buchstaben-Anbauten zu häufig werden, `template_new_cell_bonus_weight` erhöhen.
