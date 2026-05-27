# V1-Szenariogenerierung

V1 erzeugt ein einzelnes deterministisches Witness-Szenario aus einer YAML-Config. Der Generator arbeitet auf einem unbounded sparse Board; es gibt keine feste Boardbegrenzung, die ein Quadrat erzwingt.

Pro Witness-Schritt wird eine Wortlänge aus `length_distribution` gesampelt. Die V1-Config nutzt dafür eine inklusive Start-End-Range von `3` bis `7`. Eine Range mit `start = end = 7` ist degeneriert: sie sampelt formal zwar jedes Mal neu, produziert aber praktisch immer gleich breite Slots und kann zusammen mit der kompakten Scoring-Heuristik ein unnatürliches 5x5-Auffüllen erzeugen.

Die Anchor-Heuristik bevorzugt kompakte Kandidaten über Centroid-Distanz und freien Achsenraum, dient aber nur als billige Reihenfolge für nicht überlappende Anchor-Batches. Innerhalb eines Batches werden deterministische Wortverlängerungen auf der Legeachse und auf berührten Cross-Achsen sowie Templates mit leeren Cross-Domains vor dem Slot-CSP entfernt; die verbleibenden Templates erhalten zusätzlich einen Domain-Slack-Bonus. Liefert ein zentraler Batch keinen Move, öffnet der Generator den nächsten weiter außen liegenden Batch, ohne frühere Anchors erneut zu prüfen, solange das kumulative CSP-Budget noch nicht ausgeschöpft ist.
