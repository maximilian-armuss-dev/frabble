# Local Slot CSP

The CSP is built for one word slot and never sees the complete board.

## Input

```python
language: StrictlyLocalLanguage
template: SlotTemplate
domains: list[set[Symbol]]
```

`domains[i]` describes the symbols allowed at word position `i`.

```text
length = 5
domains = [
  {A,B,C,D,E,F},
  {A},
  {A,B,C,D,E,F},
  {D},
  {A,B,C,D,E,F}
]
```

Positions `1` and `3` are fixed by overlaps with existing board cells.

## Constraint Extraction

Domains are built from the template and board:

- Free cell: the full alphabet.
- Anchor cell: `{anchor_symbol}`.
- Occupied crossing cell: `{existing_symbol}`.

V1 additionally requires:

- Length at least `3`.
- No forbidden snippets.
- No words of length `1` or `2`.

Cross-word constraints are inserted into domains before the CSP. An empty domain proves that no symbol at that position can make every orthogonal cross-word valid, so the template is rejected without a solver call. Non-empty extracted domains are stored on the template candidate and passed unchanged to the solver.

## OR-Tools Model

Each word position is an integer variable:

```python
x[i] in domain_ids[i]
```

The Strictly Local language is compiled into a DFA and attached with `AddAutomaton`:

```python
model.AddAutomaton(
    x,
    start_state,
    final_states,
    transitions,
)
```

The automaton is constant within a `SlotCSP` instance, so it is created lazily once and reused.

With a seeded generator RNG, each unfixed position receives a random symbol preference before solving. These preferences influence branching while the solver still seeks any valid assignment. Equal board, config, and seed remain reproducible.

The solver returns:

```python
list[Symbol] | None
```

`None` means no word satisfies both the language and positional constraints for this template.

## `k = 2`

V1 starts with `k = 2`. The DFA state is essentially the last symbol plus the start state. For the initial language, repeated transitions such as `A -> A` and `B -> B` are forbidden.

## `k = 3` and Mixed Width

`k = 3` is part of the target design. The DFA state stores a suffix of up to length `2`. Mixed-width forbidden snippets of length `2` and `3` can use the same compiler; the solver still sees only an automaton.
