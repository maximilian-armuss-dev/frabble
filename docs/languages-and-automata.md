# Sprachen und Automaten

Die formale Sprache soll unabhängig von der konkreten sichtbaren Symbolrepräsentation definiert werden. Intern kann die Sprache mit Platzhaltern wie `A`, `B`, `C` oder abstrakten Symbol-IDs arbeiten. Erst in einem separaten Mapping-Schritt werden diese Platzhalter auf konkrete sichtbare Einheiten abgebildet.

## Platzhalter und Mapping

Für V1 reicht ein einfaches Alphabet aus zufällig gewählten ASCII-Zeichen oder manuell festgelegten Symbolen. Wichtig ist die Entkopplung:

- Die Sprache kennt nur abstrakte Alphabet-Symbole.
- Das Board und die Prompts zeigen konkrete gemappte Symbole.
- Der Validator kann Modelloutputs wieder auf abstrakte Symbole zurückführen.

Damit bleibt die Sprachdefinition stabil, während unterschiedliche Repräsentationen getestet werden können. Später kann derselbe Mechanismus für tokenizer-spezifische Alphabete genutzt werden.

## Token-Level als späterer Faktor

Das langfristige Ziel kennt drei Alphabetklassen:

- Sub-Token-Level: sichtbare Einheiten, die für ein Modell typischerweise innerhalb eines Tokens liegen können, etwa einzelne Zeichen oder Zeichenfragmente.
- Token-Level: sichtbare Einheiten, die möglichst genau einem Token des jeweiligen Modelltokenizers entsprechen.
- Supra-Token-Level: sichtbare Einheiten, die mehrere Tokens umfassen können, etwa synthetische Wörter oder längere Symbolblöcke.

Diese Unterscheidung ist für V1 noch kein Experimentalfaktor. Sie sollte aber architektonisch nicht verbaut werden.

## Reguläre Sprachen

Reguläre Sprachen sind ausdrucksstark genug, um kontrollierte Symbolsprachen mit endlichen Automaten zu definieren. Sie sind außerdem deterministisch validierbar. Das Problem liegt nicht in der Validierung, sondern in der Generierung sinnvoller Instanzen: zufällige reguläre Sprachen können zu trivial, zu dünn, zu dicht oder strukturell künstlich sein.

Ein unerwünschtes Beispiel wäre ein baumartiger Automat mit wenigen langen Branches. Solche Automaten erzeugen eher eine kleine Liste fast fest verdrahteter Wörter als eine sprachähnliche Struktur. Für den Benchmark sind kompakte Automaten interessanter, in denen Zustände über mehrere Pfade miteinander verbunden sind und die Sprache trotzdem nicht jedes beliebige Wort akzeptiert.

## Strictly Local Languages

Strictly Local Languages sind eine eingeschränkte Klasse regulärer Sprachen. Eine Sprache ist `k`-strictly-local, wenn die Gültigkeit eines Wortes durch erlaubte lokale Teilstrings der Länge `k` bestimmt wird, typischerweise inklusive Wortgrenzen. Vereinfacht: Ein Wort ist gültig, wenn alle seine lokalen Fenster erlaubt sind.

Für den Prototypen sind sie attraktiv, weil sie einfacher kontrollierbar sind als beliebige reguläre Sprachen. Man kann erlaubte `k`-Gramme sampeln und daraus direkt einen Automaten bauen, dessen Zustand im Kern aus den letzten `k-1` Symbolen besteht. Dadurch entstehen automatisch zusammenhängendere Strukturen als bei einer naiven Branch-Generierung einzelner Wörter.

Der Nachteil ist, dass Strictly Local Languages nicht alle regulären Muster ausdrücken. Sie modellieren lokale Constraints, aber keine beliebig langen globalen Abhängigkeiten. Für V1 ist das akzeptabel, weil die Sprache vor allem nicht natürlichsprachlich, deterministisch validierbar und kontrollierbar schwierig sein soll.

## Komplexitätsparameter

Für V1 sollten Automaten nicht nur nach Bauchgefühl generiert werden. Mindestens folgende Kennzahlen sollten gespeichert werden:

- Alphabetgröße.
- Wortlängenbereich.
- Anzahl Zustände im erzeugten Automaten.
- Anzahl Übergänge.
- Übergangsdichte relativ zu allen möglichen Übergängen.
- Anteil akzeptierter Strings pro Länge, soweit effizient berechenbar oder schätzbar.
- Anzahl erreichbarer und produktiver Zustände.
- Größe des minimierten DFA.

Diese Werte helfen zu erkennen, ob ein Automat trivial, zu dicht, zu dünn oder strukturell degeneriert ist.

## Offene Entscheidung

Für V1 gibt es zwei pragmatische Optionen. Die konservative Option ist eine kleine handdefinierte oder halbzufällig erzeugte Sprache, mit der Boardvalidierung und Prompting getestet werden. Die ambitioniertere Option ist ein Generator für Strictly Local Languages mit kontrollierter Alphabetgröße, `k`, erlaubten lokalen Fenstern und Akzeptanzdichte.

Eine externe Package-Entscheidung ist noch offen. Der erste robuste Schritt ist wahrscheinlich eine eigene kleine Implementierung für Strictly Local Languages, weil der benötigte Kern überschaubar ist und die Generatorparameter dann vollständig kontrolliert werden können.
