# Backoff und Budget

Der Generator muss nicht beweisen, dass kein weiterer Zug existiert. Er muss nur effizient gültige Witness-Übergänge erzeugen.

## Budget

V1 bricht einen internen Generationslauf ab, wenn `8` Suchversuche nacheinander scheitern.

Ein Suchversuch ist ein Versuch, aus einer gesampelten Wortlänge, den Top-M Anchors und den Top-K Templates einen gültigen nächsten Move zu erzeugen.

Die Zählung der Suchversuche ist deterministisch. Bei gleicher Config und gleichem Seed werden dieselben Wortlängen, Anchor-Scores, Templates und Backoff-Schritte durchlaufen.

## Backoff-Reihenfolge

Wenn für ein Template kein Wort gefunden wird:

1. nächstes Template aus den Top-K Templates derselben Wortlänge.
2. wenn alle Top-K Templates scheitern, zählt der Suchversuch als fehlgeschlagen.
3. danach wird eine neue Wortlänge gesampelt und der globale Candidate-Ansatz erneut ausgeführt.

Wenn alle Templates eines Suchversuchs scheitern, zählt der Suchversuch als fehlgeschlagen.

## Kein Solvability-Anspruch

Ein fehlgeschlagener Suchversuch bedeutet nicht, dass das Board unlösbar ist. Für V1 ist das egal. Exportiert werden nur Zustände, für die bereits ein Witness-Move bekannt ist.

## Validator als Assertion

Obwohl das Slot-CSP konstruktiv ein gültiges Wort liefern soll, bleibt der Validator Pflicht:

```text
generated_move -> validator -> must be valid
```

Ein Validator-Fehlschlag bedeutet einen Bug in Template-Erzeugung, Constraint-Extraktion, Solver-Adapter oder Sprachkompilierung.
