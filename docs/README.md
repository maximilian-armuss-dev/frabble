# Knowledge Base

This directory contains the project's technical and conceptual documentation.

## Structure

- [`shared/`](shared/) describes concepts shared by all benchmark versions:
  - the formal language model,
  - board and move representations,
  - validation rules.
- [`v1/`](v1/) documents the deliberately small first implementation:
  - scope,
  - language,
  - prompt format,
  - scenario generation.
- [`target/`](target/) describes the intended full benchmark:
  - complexity axes,
  - experimental conditions,
  - puzzle generation,
  - possible decomposition and future work.
- [`evaluation/`](evaluation/) documents the evaluation framework:
  - architecture,
  - configuration,
  - asynchronous execution,
  - lifecycle and artifacts,
  - evaluation-case interfaces.
- [`implementation/`](implementation/) explains implementation details of the generator:
  - data structures,
  - generator algorithm,
  - slot CSP,
  - anchor scoring,
  - backoff and budget handling.

The repository root [`README.md`](../README.md) remains the entry point for installation and usage.
