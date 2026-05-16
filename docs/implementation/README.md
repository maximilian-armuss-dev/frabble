# V1-Implementierung

Dieser Ordner enthält die implementierungsnahe Spezifikation für den V1-Puzzle-Generator. Die Dateien hier sind als direkte Grundlage für Code gedacht. Allgemeine Motivation, Paper-Zielbild und spätere Erweiterungen bleiben außerhalb dieses Ordners.

## Dateien

- [data-structures.md](data-structures.md): Datenmodelle und Indizes.
- [generator-algorithm.md](generator-algorithm.md): Ablauf der Puzzle-Generierung.
- [slot-csp.md](slot-csp.md): lokales CSP für einzelne Wortslots.
- [anchor-scoring.md](anchor-scoring.md): Anchor- und Template-Heuristiken.
- [backoff-and-budget.md](backoff-and-budget.md): Backoff-Modell und Abbruchlogik.

## V1-Festlegungen

- Boardgenerierung ist unbounded.
- Exportierte Szenarien erhalten später eine ROI beziehungsweise Bounding Box.
- V1 nutzt `dimensions = 2`.
- V1 nutzt `k = 2`.
- V1 nutzt eine einfache Strictly-Local-Sprache über forbidden snippets.
- Wörter der Länge `1` und `2` sind ungültig.
- V1 nutzt lokale Slot-CSPs, nicht ein globales Board-CSP.
- V1 nutzt kein Joint Sampling von Wortlänge und konkreter Anchor-Koordinate.
- V1 nutzt einen globalen Candidate-Ansatz pro gesampelter Wortlänge: Anchors werden billig pre-scoren, Top-M Anchors werden expandiert, Top-K Templates werden an den Slot-CSP gegeben.
- V1-Generierung läuft seeded und reproduzierbar: gleiche Config plus gleicher Seed erzeugt dieselben Szenarien.
