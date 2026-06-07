# V1 Prompt Format

The prompt is split into stable and scenario-specific content.

## System Prompt

The system prompt contains:

- the placement rules,
- the formal-language rule,
- the required output schema.

It may also include the forbidden snippets and one worked example.

## User Prompt

The user prompt contains:

- board dimensionality,
- occupied board cells,
- the rack,
- the instruction to produce one legal move.

## Board Representation

The board is represented as sparse JSON:

```json
{
  "dimensions": 2,
  "cells": [
    {"coordinate": [0, 0], "symbol": "A"},
    {"coordinate": [1, 0], "symbol": "B"}
  ]
}
```

Coordinates are integer vectors whose length equals the board dimensionality.

## Output Representation

The model must return JSON only:

```json
{
  "word": "ABC",
  "start": [0, 0],
  "direction": [1, 0]
}
```

`direction` must be a positive unit vector along exactly one axis. The evaluator derives all occupied coordinates from `start`, `direction`, and `word`.
