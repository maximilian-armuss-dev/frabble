# Backoff und Abbruchlogik

Der Generator muss nicht beweisen, dass kein weiterer Zug existiert. Er muss nur effizient gültige Witness-Übergänge erzeugen und bei Erschöpfung des konfigurierten Suchraums verständlich abbrechen.

## Suchraum pro Board-State

Für jeden aktuellen Board-State wird die konfigurierte Längenrange einmal ohne Zurücklegen durchsucht.

Ein Suchversuch besteht aus:

1. Sample eine bisher unbenutzte Wortlänge aus `length_distribution`.
2. Baue den Top-M Anchor-Pool für diese Länge.
3. Baue den Top-K Template-Pool aus diesen Anchors.
4. Versuche die Templates in Score-Reihenfolge mit dem Slot-CSP.
5. Bei Erfolg: platziere den Move und starte für den neuen Board-State wieder mit einer frischen Längenrange.
6. Bei Misserfolg: markiere diese Länge als verbraucht und sample die nächste noch unbenutzte Länge.

Dadurch wird dieselbe Länge für denselben unveränderten Board-State nicht erneut geprüft. Wiederholte Arbeit entsteht erst wieder nach einem erfolgreichen Move, weil sich Board-Geometrie und Candidate-Scores geändert haben.

## Failure Modes

Wenn alle Längen der Range für einen Board-State erschöpft sind, bricht der Lauf mit einem Fehler ab. Der Fehler nennt die pro Länge beobachteten Gründe:

- `no_anchor_candidates`: Es gab keine belegte Koordinate mit zulässiger Cross-Achse.
- `no_template_candidates`: Anchors existierten, aber alle daraus erzeugten Templates wurden geometrisch geprunt.
- `no_solver_solution`: Templates wurden versucht, aber das Slot-CSP fand keine Sequenz.
- `validator_rejected_all`: Das Slot-CSP fand Sequenzen, aber der Validator verwarf alle mit tolerierten Failure-Typen.
- `templates_exhausted`: Gemischte Template-Fehlschläge ohne erfolgreiche Platzierung.

Die Terminalmeldung enthält zusätzlich Counts für Anchors, Templates und Solver-Versuche sowie eine kurze Empfehlung, welche Config-Hebel naheliegen: `top_anchor_count`, `top_template_count`, `length_distribution`, Scoring oder Sprachconstraints.

## Kein Solvability-Anspruch

Ein erschöpfter Candidate-Pool bedeutet nicht, dass das Board unlösbar ist. Es bedeutet nur, dass der durch die Config begrenzte Suchraum keinen nächsten Witness-Move gefunden hat.

Ein Generationslauf gilt nur als erfolgreich, wenn `target_witness_count` erreicht wurde. Wird vorher der konfigurierte Suchraum für einen Board-State ausgeschöpft, bricht der Generator mit einem Fehler ab und schreibt keine neue Szenariodatei als erfolgreichen Lauf.

## Validator als Assertion

Obwohl das Slot-CSP konstruktiv ein gültiges Wort liefern soll, bleibt der Validator Pflicht:

```text
generated_move -> validator -> must be valid
```

Ein harter Validator-Fehlschlag bedeutet einen Bug in Template-Erzeugung, Constraint-Extraktion, Solver-Adapter oder Sprachkompilierung. Bekannte weiche Fehlschläge wie `word_extension` und `invalid_main_word` werden als Template-Fehlschläge behandelt und führen zum nächsten Template.
