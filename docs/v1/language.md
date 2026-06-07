# V1 Language

V1 uses one deliberately simple strictly local language.

## Alphabet

\[
\Sigma = \{A, B, C, D, E, F\}
\]

## Rule

A sequence is valid if:

- it has length at least three,
- no symbol is immediately repeated.

Equivalently, the forbidden length-two snippets are:

```text
AA BB CC DD EE FF
```

## Examples

Valid:

```text
ABC
ABACA
FEDCBA
```

Invalid:

```text
AB
ABBC
FAA
```

This language is intentionally easy to explain and validate. Its purpose is to test the end-to-end benchmark pipeline before introducing more complex automata.
