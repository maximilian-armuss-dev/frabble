from __future__ import annotations

from collections import Counter
from itertools import product
from typing import Iterable

from ..benchmark.scoring import score_word
from ..domain.models import Board, DFA, Move, ValidationResult


def validate_move(
    board: Board,
    dfa: DFA,
    rack: tuple[str, ...],
    token_scores: dict[str, int],
    move: Move,
) -> ValidationResult:
    if not move.tokens:
        return ValidationResult(False, 0, "parse", "Token sequence must not be empty.")
    if any(token not in dfa.alphabet for token in move.tokens):
        return ValidationResult(
            False, 0, "alphabet", "Token sequence contains unknown tokens."
        )
    if len(move.start) != board.dimensions:
        return ValidationResult(
            False,
            0,
            "spatial",
            f"Start vector must have {board.dimensions} coordinates.",
        )
    if move.axis < 0 or move.axis >= board.dimensions:
        return ValidationResult(False, 0, "spatial", "Axis is outside board dimensions.")
    if not board.contains(move.start):
        return ValidationResult(False, 0, "spatial", "Move starts outside the board.")

    end = tuple(
        value + (len(move.tokens) - 1 if dim == move.axis else 0)
        for dim, value in enumerate(move.start)
    )
    if not board.contains(end):
        return ValidationResult(False, 0, "spatial", "Word does not fit on the board.")

    needed = Counter()
    touches_existing = False
    placed_new_token = False
    for offset, token in enumerate(move.tokens):
        coordinate = tuple(
            value + (offset if dim == move.axis else 0)
            for dim, value in enumerate(move.start)
        )
        current = board.at(coordinate)
        if current is None:
            needed[token] += 1
            placed_new_token = True
            continue
        if current != token:
            return ValidationResult(
                False,
                0,
                "overlap",
                f"Board has {current} at {coordinate}, but move needs {token}.",
            )
        touches_existing = True

    if not placed_new_token:
        return ValidationResult(False, 0, "structural", "Move places no new token.")
    if board.has_tiles() and not touches_existing:
        return ValidationResult(
            False,
            0,
            "structural",
            "Move must overlap at least one existing token.",
        )
    rack_counts = Counter(rack)
    missing = needed - rack_counts
    if missing:
        return ValidationResult(
            False,
            0,
            "rack",
            f"Rack does not contain the needed tokens: {dict(missing)}.",
        )
    if not dfa.accepts(move.tokens):
        return ValidationResult(
            False,
            0,
            "language",
            "The submitted word is not accepted by the DFA.",
        )
    return ValidationResult(True, score_word(move.tokens, token_scores), None, "valid")


def enumerate_legal_moves(
    board: Board,
    dfa: DFA,
    rack: tuple[str, ...],
    token_scores: dict[str, int],
    accepted_words: Iterable[str],
) -> tuple[Move, ...]:
    legal_moves: list[Move] = []
    for word in accepted_words:
        for axis in range(board.dimensions):
            for start in product(*(range(size) for size in board.shape)):
                move = Move(start=tuple(start), axis=axis, tokens=word)
                result = validate_move(board, dfa, rack, token_scores, move)
                if result.ok:
                    legal_moves.append(move)
    return tuple(legal_moves)
