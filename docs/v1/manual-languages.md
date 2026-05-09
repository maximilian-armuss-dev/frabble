# Manuelle V1-Sprachen

V1 nutzt genau `5` manuell definierte Strictly-Local-Sprachen. Alle Sprachen verwenden `k = 2`, Alphabetgröße `6` und das Alphabet `{A, B, C, D, E, F}`. Wörter der Länge `1` sind ungültig.

Die Sprachen sollen verschiedene Komplexitätsprofile abdecken, ohne für die Boardgenerierung ungeeignet zu sein. Jede Sprache hat Zyklen, keine isolierten Symbole und keine offensichtlichen Sackgassen.

## L1: Ausgewogen und dicht

```text
A: B, C, D
B: A, D, E
C: A, E, F
D: B, C, F
E: A, C, D
F: A, B, E
```

Diese Sprache ist für einfache Szenarien geeignet. Sie hat `18` von `36` möglichen Übergängen und damit mittlere Dichte. Alle Symbole haben drei ausgehende Übergänge. Dadurch entstehen viele gültige Wörter und der Boardgenerator findet leicht Overlaps.

## L2: Zwei Cluster mit Brücken

```text
A: B, C, D
B: A, C, E
C: A, B, F
D: A, E, F
E: B, D, F
F: C, D, E
```

Diese Sprache besteht aus zwei lokalen Clustern `{A, B, C}` und `{D, E, F}` mit mehreren Brücken. Sie ist geeignet, weil sie strukturierter ist als L1, aber nicht in getrennte Komponenten zerfällt. Der Generator kann innerhalb eines Clusters viele Wörter bilden und über Brückensymbole zwischen Bereichen wechseln.

## L3: Sparse, aber zyklisch

```text
A: B, D
B: C, E
C: A, F
D: E, A
E: F, B
F: D, C
```

Diese Sprache hat `12` von `36` möglichen Übergängen. Sie ist deutlich restriktiver, aber jedes Symbol hat zwei ausgehende Übergänge und bleibt produktiv. Dadurch ist sie schwerer, ohne dass der Sampler schnell in Sackgassen läuft.

## L4: Hub-Struktur

```text
A: B, C, D
B: A, E
C: A, F
D: A, E
E: B, C, F
F: C, D, A
```

Diese Sprache hat mehrere Wege über zentrale Symbole, besonders `A`, bleibt aber nicht sternförmig degeneriert. Sie ist geeignet, um zu testen, ob das Modell lokale Übergangsregeln mit asymmetrischen Symbolrollen befolgt.

## L5: Alternierende Teilräume

```text
A: D, E
B: D, F
C: E, F
D: A, B
E: A, C
F: B, C
```

Diese Sprache erzwingt Wechsel zwischen den Gruppen `{A, B, C}` und `{D, E, F}`. Sie ist strukturell klar, aber nicht trivial, weil nicht jeder Wechsel erlaubt ist. Für Overlap-basierte Boardgenerierung ist sie geeignet, da alle Symbole in kurzen und langen Wörtern produktiv bleiben.
