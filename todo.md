* config so umstellen, dass der filename ohne suffix bestimmt, was der uv generate command erwartet, wie die json im output folder heißt, und den config namen an sich selbst natürlich. "config_name" ist somit nicht mehr nötig in der yaml.

* ähnliche logik für die angegebene grammar in der generator config: einfach nur den namen / die ID nennen, ohne parent path oder suffix.

* files wie engine.py sind mittlerweile 400 Zeilen lang, man muss sich alle files mal anschauen und überlegen, ob man die sinnvoll aufteilen sollte oder nicht

* 3d visualization animieren wie 2D wenn das geht. also neue worte blau legen und step by step sichtbar per slider machen

* thema tests: vielleicht sollten wir mehrere test directories für unterschiedliche teile des repos machen: bspw. einen für de-/serialization, einen für LLM stuff dry run, einen für board gen usw. und dann halt die test files im directory zwar kurz halten, aber trotzdem mehrere logisch zueinandergehörige tests in eine file packen. also eine gute balance zwischen file bloat (eine file pro test) und dem gegenteil finden, sodass die files nicht zu lang werden, die menge der files aber auch nicht explodiert.

* wär gut wenn man bei jedem generation step in der visualization in den notebooks auch das rack sehen kann.

