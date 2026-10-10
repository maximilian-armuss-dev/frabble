# Repository polish

These tasks are intentionally deferred until the research workflow has stabilized. The goal is a clean, presentable repository without adding unnecessary process or restructuring code that is still changing.

## Results and paper

- [x] Replace stale config/model expectations with fixed test fixtures; check active config references separately.
- [ ] Back up the final result artifacts outside the repository before removing generated outputs from Git.
- [ ] Keep only small examples, fixtures, manifests, and checksums in the repository; ignore generated output directories consistently.
- [ ] Give the paper dataset a stable name such as `paper-v1` instead of names such as `final_merged` or `after-updates`.
- [ ] Move the selected paper runs and replacement-run mapping into a small config instead of hardcoding a timestamped path in the figure code.
- [ ] Provide one command that validates the selected artifacts and regenerates all paper figures.
- [ ] Publish the final result bundle in durable external storage for the paper release; a local Downloads backup is only an interim step.

## Repository presentation

- [ ] Remove editor, OS, notebook, Python cache, and LaTeX build artifacts before release.
- [ ] Normalize notebook kernels and decide consistently whether notebook outputs are retained.
- [x] Add a minimal lockfile-based CI check: pytest and Ruff on Python 3.11/3.12.
- [ ] Adopt broader formatting rules separately, without mixing a repository-wide reformat into submission cleanup.

## Maintainability

- [ ] Review names across modules, commands, configs, artifacts, and tests for consistency.
- [x] Separate provider and notebook-run tests from core tests.
- [ ] Consider further splits of the large core/evaluation test and plotting modules when those areas change.
- [ ] Add docstrings to public or non-obvious interfaces; avoid documenting self-explanatory helpers.
- [x] Review subsystem boundaries, remove unused private helpers/imports and the stub-only decomposition CLI, and preserve active APIs and artifact schemas.
- [ ] Later, consider renaming the installed package from `src` to `frabble` and separating core, provider, visualization, and development dependencies.

## Publication metadata

- [ ] Add code and data licenses.
- [ ] Add `CITATION.cff` with authors, paper reference, version, and DOI.
- [ ] Make the paper sources publicly accessible without relying on a private Overleaf submodule.
- [ ] Create a tagged paper release with the exact code revision, locked environment, artifact checksums, paper PDF, and archived result data.

