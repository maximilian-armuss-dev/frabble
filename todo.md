* config so umstellen, dass der filename ohne suffix bestimmt, was der uv generate command erwartet, wie die json im output folder heißt, und den config namen an sich selbst natürlich. "config_name" ist somit nicht mehr nötig in der yaml.
* ähnliche logik für die angegebene grammar in der generator config: einfach nur den namen / die ID nennen, ohne parent path oder suffix.
* files wie engine.py sind mittlerweile 400 Zeilen lang, man muss sich alle files mal anschauen und überlegen, ob man die sinnvoll aufteilen sollte oder nicht
* auch wenn ein witness nicht generiert werden kann sollte die .json bis zu diesem punkt geschrieben werden, damit man den trace zum debuggen anschauen kann

❯ uv run generate --config generator_3d
witnesses:  20%|███████████████▉                                                                  | 39/200 [00:01<00:05, 26.86witness/s]
generation failed: Generator produced 39 of 200 target witnesses.
All lengths in length_distribution were tried once for the current board state.
Failure summary by sampled length:
- length=3: templates_exhausted; anchors=40, templates=58, solver_attempts=58, statuses=no_solution:42, validator_failed:16
- length=4: templates_exhausted; anchors=40, templates=119, solver_attempts=119, statuses=no_solution:89, validator_failed:30
- length=5: templates_exhausted; anchors=40, templates=188, solver_attempts=188, statuses=no_solution:145, validator_failed:43
- length=6: templates_exhausted; anchors=40, templates=200, solver_attempts=200, statuses=no_solution:172, validator_failed:28
- length=7: templates_exhausted; anchors=40, templates=200, solver_attempts=200, statuses=no_solution:174, validator_failed:26
Suggestion: increase top_template_count/top_anchor_count, widen length_distribution, or relax the language/scoring constraints.

* 3d visualization animieren wie 2D wenn das geht. also neue worte blau legen und step by step sichtbar per slider machen

* thema tests: vielleicht sollten wir mehrere test directories für unterschiedliche teile des repos machen: bspw. einen für de-/serialization, einen für LLM stuff dry run, einen für board gen usw. und dann halt die test files im directory zwar kurz halten, aber trotzdem mehrere logisch zueinandergehörige tests in eine file packen. also eine gute balance zwischen file bloat (eine file pro test) und dem gegenteil finden, sodass die files nicht zu lang werden, die menge der files aber auch nicht explodiert.

* wär gut wenn man bei jedem generation step in der visualization auch das rack sehen kann