# V1-Sprache

V1 startet mit genau einer einfachen Strictly-Local-Sprache. Ziel ist nicht, die Sprachachse schon breit zu benchmarken, sondern zu prüfen, ob der Prototyp technisch funktioniert und ob das LLM bereits bei einer einfachen formalen Sprache Probleme hat.

## Festlegungen

- Alphabetgröße `6`.
- Alphabet `{A, B, C, D, E, F}`.
- Strictly Local Language.
- Forbidden-snippet-Repräsentation.
- Wörter der Länge `1` und `2` sind ungültig.
- Minimale Wortlänge ist `3`.

## Startsprache

Für den ersten Prototypen kann eine einfache `k = 2`-Sprache genutzt werden, die gleiche benachbarte Symbole verbietet:

```text
forbidden = {
  "AA", "BB", "CC", "DD", "EE", "FF"
}
```

Ein Wort ist gültig, wenn es Länge mindestens `3` hat und kein Symbol direkt zweimal hintereinander vorkommt.

Gültig:

```text
A B C
A C A D
F E D C
```

Ungültig:

```text
A B
A A C
D E E F
```

Diese Sprache ist absichtlich simpel. Sie hat keine Sackgassen, alle Symbole bleiben produktiv und der Generator findet leicht gültige Wörter. Sie dient als erster End-to-end-Test für Prompting, Parsing, Boardvalidierung und Szenariogenerierung.
