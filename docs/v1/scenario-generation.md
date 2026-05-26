# V1-Szenariogenerierung

V1 erzeugt ein einzelnes deterministisches Witness-Szenario aus einer YAML-Config. Der Generator arbeitet auf einem unbounded sparse Board; es gibt keine feste Boardbegrenzung, die ein Quadrat erzwingt.

Pro Witness-Schritt wird eine Wortlänge aus `length_distribution` gesampelt. Die V1-Config nutzt dafür eine inklusive Start-End-Range von `3` bis `7`. Eine Range mit `start = end = 7` ist degeneriert: sie sampelt formal zwar jedes Mal neu, produziert aber praktisch immer gleich breite Slots und kann zusammen mit der kompakten Scoring-Heuristik ein unnatürliches 5x5-Auffüllen erzeugen.

Die Anchor- und Template-Heuristik bevorzugt kompakte Kandidaten über Bounding-Box-Wachstum und Centroid-Distanz. Das ist absichtlich lokal und billig, aber kein Solvability-Beweis. Wenn der Validator einen Kandidaten als Wortverlängerung verwirft, versucht der Generator weitere Templates derselben gesampelten Länge und danach neue Suchversuche mit neu gesampelter Länge.
