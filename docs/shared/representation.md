# Representation

Coordinates are zero-based vectors `x = [x0, x1, ..., x_{d-1}]`. V1 uses `d = 2`; the same representation extends to higher dimensions.

Axes use the same indexing:

- `axis = 0` advances along `x0`.
- `axis = 1` advances along `x1`.
- In general, `axis = i` advances along `xi`.

Prompt, JSON, and internal indexing are all zero-based.

## Board

The board is represented as a sparse map or list of occupied coordinates. Each occupied cell contains exactly one symbol; empty cells are omitted.

A board configuration contains at least:

- `dimensions`: Number of dimensions.
- `shape`: Board extent on each coordinate axis.
- `occupied`: Occupied coordinate-symbol pairs.
- `rack`: Symbols available for the next move.

```json
{
  "dimensions": 2,
  "shape": [8, 8],
  "occupied": [
    {"coord": [2, 3], "symbol": "A"},
    {"coord": [3, 3], "symbol": "B"}
  ],
  "rack": ["A", "A", "C", "D"]
}
```

## Move Output

The model returns exactly one structured JSON object:

```json
{
  "start": [2, 3],
  "axis": 0,
  "sequence": ["A", "B", "C", "D"]
}
```

`sequence` is the complete word, including newly placed rack symbols and existing board symbols reused consistently. A list preserves boundaries for future multi-character symbols.

Pydantic models enforce structure, types, and normalization. Parsing errors are evaluated separately from rule and language failures. When a provider supports structured output through LiteLLM, the Pydantic schema is supplied directly; otherwise the response is parsed and validated afterward.
