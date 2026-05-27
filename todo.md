* Aktuell haben wir leider noch das Problem, dass der CSP Solver immer das erste gültige Wort, welches die Constraints erfüllt, zurückgibt und dadurch ähneln sich die generierten Worte enorm. Die einzige Varianz, die ich beobachten konnte, ist die Länge, weil die ja statisch gesampelt wird. Aber häufig wird in diesen simplen Sprachen, die wir benutzen zum Generieren, dann immer nur eine Sequenz von 5 As oder abwechselnd AMAM und so weiter generiert, verstehst du? Kann man das irgendwie im Solver randomisen, dass er entweder halt einen random Startpunkt hat und dann quasi von dieser random Sequenz die erste Lösung nimmt, somit dass man mehr Randomization drin hat? Oder gibt es irgendeinen anderen Möglichkeit, um sicherzustellen, dass nicht immer diese ähnlichen Sequenzen generiert werden?

* config so umstellen, dass der filename ohne suffix bestimmt, was der uv generate command erwartet, wie die json im output folder heißt, und den config namen an sich selbst natürlich. "config_name" ist somit nicht mehr nötig in der yaml.

* ähnliche logik für die angegebene grammar in der generator config: einfach nur den namen / die ID nennen, ohne parent path oder suffix.

* files wie engine.py sind mittlerweile 400 Zeilen lang, man muss sich alle files mal anschauen und überlegen, ob man die sinnvoll aufteilen sollte oder nicht

* auch wenn ein witness nicht generiert werden kann sollte die .json bis zu diesem punkt geschrieben werden, damit man den trace zum debuggen anschauen kann

* 3d visualization animieren wie 2D wenn das geht. also neue worte blau legen und step by step sichtbar per slider machen

* thema tests: vielleicht sollten wir mehrere test directories für unterschiedliche teile des repos machen: bspw. einen für de-/serialization, einen für LLM stuff dry run, einen für board gen usw. und dann halt die test files im directory zwar kurz halten, aber trotzdem mehrere logisch zueinandergehörige tests in eine file packen. also eine gute balance zwischen file bloat (eine file pro test) und dem gegenteil finden, sodass die files nicht zu lang werden, die menge der files aber auch nicht explodiert.

* wär gut wenn man bei jedem generation step in der visualization in den notebooks auch das rack sehen kann.

