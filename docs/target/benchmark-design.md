# Benchmark-Zielbild

Das Paper-Zielbild ist ein skalierbarer Benchmark für LLMs in einem kontrollierten formalen Spielraum. Die zentrale Motivation bleibt Reasoning: Aktuelle Benchmarks können Performancegewinne mitmessen, die aus gelernten Mustern natürlicher Sprache stammen. Der Benchmark soll diese Quelle entkoppeln, indem natürliche Wörter durch formal erzeugte Symbolsprachen ersetzt werden.

Die Contribution ist nicht nur ein einzelner Leaderboard-Wert. Aussagekräftiger ist eine dekomponierte Evaluation, die sichtbar macht, ob ein Modell an formaler Sprachkonformität, constrained generation, räumlicher Planung oder an der Komposition dieser Fähigkeiten scheitert.

Die Basisstrukturen aus V1 bleiben erhalten: Koordinaten sind 0-basiert indexierte Vektoren, Boards sind sparse Maps von Koordinaten auf Symbole, und `axis` referenziert dieselbe Indexlogik wie die Koordinatenachsen.
