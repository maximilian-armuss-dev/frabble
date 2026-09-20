# Repository polish

These tasks are intentionally deferred until the research workflow has stabilized. The goal is a clean, presentable repository without adding unnecessary process or restructuring code that is still changing.

## Results and paper

- [ ] Remove tests for configs that no longer exist and update stale expectations.
- [ ] Back up the final result artifacts outside the repository before removing generated outputs from Git.
- [ ] Keep only small examples, fixtures, manifests, and checksums in the repository; ignore generated output directories consistently.
- [ ] Give the paper dataset a stable name such as `paper-v1` instead of names such as `final_merged` or `after-updates`.
- [ ] Move the selected paper runs and replacement-run mapping into a small config instead of hardcoding a timestamped path in the figure code.
- [ ] Provide one command that validates the selected artifacts and regenerates all paper figures.
- [ ] Publish the final result bundle in durable external storage for the paper release; a local Downloads backup is only an interim step.

## Repository presentation

- [ ] Remove editor, OS, notebook, Python cache, and LaTeX build artifacts before release.
- [ ] Normalize notebook kernels and decide consistently whether notebook outputs are retained.
- [ ] Add a small automated check that installs from the lockfile, runs the tests, and checks formatting and common code issues.
- [ ] Keep this automation minimal at first: tests plus Ruff are sufficient.

## Maintainability

- [ ] Review names across modules, commands, configs, artifacts, and tests for consistency.
- [ ] Split the largest source and test files where they contain multiple responsibilities.
- [ ] Add docstrings to public or non-obvious interfaces; avoid documenting self-explanatory helpers.
- [ ] Perform a focused maintainability review before making broader structural changes.
- [ ] Later, consider renaming the installed package from `src` to `frabble` and separating core, provider, visualization, and development dependencies.

## Publication metadata

- [ ] Add code and data licenses.
- [ ] Add `CITATION.cff` with authors, paper reference, version, and DOI.
- [ ] Make the paper sources publicly accessible without relying on a private Overleaf submodule.
- [ ] Create a tagged paper release with the exact code revision, locked environment, artifact checksums, paper PDF, and archived result data.

