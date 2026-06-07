# Complexity Axes

The target benchmark varies four largely independent dimensions of complexity.

## 1. Alphabet Class

The symbols shown to the model can represent units at different linguistic levels:

- **sub-token alphabets**, whose symbols tend to be parts of tokenizer tokens,
- **token-level alphabets**, whose symbols tend to correspond to complete tokens,
- **supra-token alphabets**, whose symbols tend to require multiple tokens.

Placeholder symbols can be mapped to these classes while the underlying formal language remains unchanged. This separates reasoning difficulty from the syntactic properties of the visible representation.

## 2. Board Dimensionality

Boards may have two, three, or more dimensions. Increasing dimensionality changes:

- the number of legal placement axes,
- the number of possible perpendicular cross-words,
- the spatial bookkeeping required from the model.

Higher-dimensional boards should retain the same local placement semantics as the two-dimensional case.

## 3. Board Complexity

Board complexity includes:

- board size or occupied bounding-box volume,
- occupancy density,
- number and length of existing words,
- rack size,
- number of usable anchors,
- number and tightness of cross-word constraints.

These parameters should be controlled separately where possible. A larger board is not necessarily harder if it contains only one unconstrained anchor.

## 4. Automaton Complexity

The formal language can be varied through parameters such as:

- forbidden-snippet width \(k\),
- number of forbidden snippets,
- number of automaton states,
- transition density,
- acceptance density,
- size of the minimal DFA,
- accepted word lengths and counts.

For \(k = 3\), forbidden snippets may have mixed widths up to three. This permits local constraints of different granularities within one language.

For a fixed automaton, growth in the number of accepted words by length can be analyzed through its transition matrix. The dominant Perron eigenvalue provides an asymptotic measure of language growth.

## Experimental Control

The axes should be varied independently enough to support causal comparisons. In particular:

- changing the alphabet representation should not change the abstract language,
- changing dimensionality should not silently change the language,
- changing board density should not automatically change rack size,
- changing automaton complexity should not require changing the prompt schema.
