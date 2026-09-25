from __future__ import annotations

import itertools
import unittest

from src.benchmark.optimality import optimize_move
from src.benchmark.scoring import score_move
from src.domain.board import Board
from src.domain.models import Move
from src.formal.language import StrictlyLocalLanguage
from src.formal.validation import validate_move


class OptimalityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.language = StrictlyLocalLanguage(
            language_id="tiny",
            alphabet=("A", "B"),
            k=2,
            forbidden_snippets=(("A", "A"),),
            min_word_length=2,
            letter_scores=(("A", 1), ("B", 3)),
        )
        self.board = Board.empty(2).place(Move((0, 0), 0, ("A", "B")))
        self.rack = ("A", "B")

    def _brute_force(self, board: Board) -> int:
        best = 0
        seen: set[Move] = set()
        for anchor in board.cells:
            for axis in range(board.dimensions):
                for length in range(self.language.min_word_length, len(board.cells) + len(self.rack) + 1):
                    for index in range(length):
                        start = tuple(value - (index if dim == axis else 0) for dim, value in enumerate(anchor))
                        for sequence in itertools.product(self.language.alphabet, repeat=length):
                            move = Move(start, axis, sequence)
                            if move in seen:
                                continue
                            seen.add(move)
                            if validate_move(board, self.language, self.rack, move).ok:
                                best = max(best, score_move(board, move, self.language.letter_score_map()))
        return best

    def test_exact_score_matches_independent_exhaustive_enumeration(self) -> None:
        crossed_board = self.board.place(Move((0, 0), 1, ("A", "B")))
        for board in (self.board, crossed_board):
            with self.subTest(segments=len(board.segments)):
                result = optimize_move(board, self.language, self.rack)
                self.assertEqual(result.status, "optimal")
                self.assertEqual(result.score, self._brute_force(board))
                self.assertEqual(result.upper_bound, result.score)
                self.assertIsNotNone(result.move)
                self.assertTrue(validate_move(board, self.language, self.rack, result.move).ok)

    def test_interrupted_search_retains_safe_upper_bound(self) -> None:
        result = optimize_move(self.board, self.language, self.rack, time_limit_seconds=1e-12)
        self.assertEqual(result.status, "bounded")
        self.assertLessEqual(self._brute_force(self.board), result.upper_bound)

    def test_no_move_with_empty_rack(self) -> None:
        result = optimize_move(self.board, self.language, ())
        self.assertEqual(result.status, "no_move")
        self.assertIsNone(result.score)

    def test_empty_board_uses_periodic_premium_representatives(self) -> None:
        board = Board.empty(2)
        result = optimize_move(board, self.language, self.rack)
        brute = max(
            score_move(board, move, self.language.letter_score_map())
            for x in range(20)
            for y in range(20)
            for axis in range(2)
            for sequence in itertools.product(self.language.alphabet, repeat=2)
            for move in (Move((x, y), axis, sequence),)
            if validate_move(board, self.language, self.rack, move).ok
        )
        self.assertEqual(result.status, "optimal")
        self.assertEqual(result.score, brute)

    def test_invalid_incumbent_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Incumbent move is invalid"):
            optimize_move(self.board, self.language, self.rack, incumbent=Move((9, 9), 1, ("A", "B")))


if __name__ == "__main__":
    unittest.main()
