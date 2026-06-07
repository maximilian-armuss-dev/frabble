# Language Model

The formal language is defined independently of the visible symbol representation. Internally it may use placeholders such as `A`, `B`, `C`, or abstract symbol IDs. A separate mapping step assigns these placeholders to concrete visible units.

## Placeholders and Mapping

V1 does not yet use tokenizer-aware mappings. Placeholders are displayed directly as simple letters. The visible alphabet may use `A` through `Z` while one language uses only a subset of six symbols.

Future mappings must be bidirectional. If placeholder `A` maps to the visible symbol `house`, the validator must map `house` back to `A` unambiguously. Multi-character symbols are therefore supported conceptually from the start: model output represents `sequence` as a list of symbols rather than a concatenated string.

## Strictly Local Languages

Strictly Local Languages are a restricted class of regular languages. A language is `k`-strictly-local when word validity is determined by local substrings of length at most `k`. The benchmark preferably describes the language through forbidden snippets.

A word is valid if it contains no forbidden snippet and satisfies the minimum length.

Example with alphabet `{A, B, C}`, `k = 3`, and forbidden snippets `{AAA, BCB}`:

- `ABCABC` is valid.
- `AAAB` is invalid because it contains `AAA`.
- `ABCB` is invalid because it contains `BCB`.

## Forbidden-Snippet Approach

This representation scales because language density can be controlled through the number and structure of forbidden snippets. More forbidden local patterns reduce the number of valid strings; fewer make the language denser.

V1 may use one fixed simple language. The target benchmark can sample forbidden snippets randomly.

## Adjacency Lists

For `k = 2`, a forbidden-snippet language can be represented equivalently as an adjacency list:

```text
A: B, C
B: A
C: A, B
```

After `A`, only `B` or `C` may follow; after `B`, only `A`; after `C`, `A` or `B`. `A B A C B` is valid, while `A A B` is not.

Adjacency lists remain a useful prompt representation for `k = 2` even when internal generation uses forbidden snippets.
