from __future__ import annotations

from .language import StrictlyLocalLanguage


def enumerate_accepted_sequences(
    language: StrictlyLocalLanguage,
    length: int,
) -> tuple[tuple[str, ...], ...]:
    if length < language.min_word_length:
        return ()

    accepted: list[tuple[str, ...]] = []

    def visit(prefix: tuple[str, ...]) -> None:
        if len(prefix) == length:
            if language.accepts(prefix):
                accepted.append(prefix)
            return
        for symbol in language.alphabet:
            candidate = prefix + (symbol,)
            if _has_forbidden_suffix(language, candidate):
                continue
            visit(candidate)

    visit(())
    return tuple(sorted(accepted))


def _has_forbidden_suffix(
    language: StrictlyLocalLanguage,
    sequence: tuple[str, ...],
) -> bool:
    return any(
        len(snippet) <= len(sequence) and sequence[-len(snippet) :] == snippet
        for snippet in language.forbidden_snippets
    )

