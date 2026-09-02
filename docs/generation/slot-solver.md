# Local Slot Solver

The slot solver answers one narrow question: given a straight slot and the symbols allowed at each position, does that slot contain an accepted sequence? Board selection, rack construction, heuristic ranking, and final move legality remain outside its scope.

## Position domains

Each slot position receives a symbol domain. Free positions begin with the grammar alphabet, existing cells become single fixed symbols, and perpendicular context may reduce a free position to symbols that keep every potential cross-word valid.

```text
position:  0       1       2       3       4
domain:   {A..H}  {C}    {A,D}    {F}    {A..H}
```

If any domain becomes empty, the template is known to be impossible and never reaches the solver. Domain extraction belongs to [`src/generator/engine.py`](../../src/generator/engine.py); slot geometry and search objects live in [`src/domain/models.py`](../../src/domain/models.py).

## Automaton constraint

The concrete Strictly Local language is compiled into an automaton. The solver creates one finite-domain variable per position and constrains their complete sequence with OR-Tools' automaton constraint. This applies the language rule without enumerating every accepted word first.

The language supplies the automaton in [`src/formal/language.py`](../../src/formal/language.py), and the CP-SAT adapter lives in [`src/formal/slot_csp.py`](../../src/formal/slot_csp.py).

## Result boundary

The solver needs only one feasible assignment. Seeded symbol preferences vary the chosen solution while preserving reproducibility; it does not optimize move score or inspect other board slots.

A `None` result proves only that this template's current domains contain no accepted sequence. A returned sequence is converted into a move, receives a derived rack, and still passes through the full validator. This separation keeps constructive search aligned with the same semantics used for model submissions.

The surrounding search and its bounded failure meaning are described in [Candidate Search](search.md); final legality is described in [Move Validation](../foundations/move-validation.md).
