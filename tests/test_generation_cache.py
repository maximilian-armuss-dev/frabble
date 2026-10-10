from __future__ import annotations

from dataclasses import replace
import gc
import unittest
from unittest.mock import patch
import weakref

from src.benchmark import optimality
from src.domain.board import Board
from src.domain.models import Move
from src.formal.language import StrictlyLocalLanguage
from reference_enumeration import _enumerate_slots as reference_slots


class GenerationCacheTests(unittest.TestCase):
    def setUp(self):
        self.language = StrictlyLocalLanguage(
            "cache-test", ("A", "B"), 2, (("A", "A"),), 2,
            (("A", 1), ("B", 3)),
        )

    def test_full_slots_and_moves_match_uncached_with_changing_inputs(self):
        for dimensions in (2, 5, 10):
            board = Board.empty(dimensions).place(
                Move((0,) * dimensions, 0, ("A", "B"))
            )
            for language in (self.language, replace(self.language, forbidden_snippets=())):
                for rack in (("A", "B"), ("B", "B", "A"), ("A",), ()):
                    for current in (
                        board, board.place(Move((0,) * dimensions, 1, ("A", "B")))
                    ):
                        with self.subTest(dimensions=dimensions, rack=rack, language=language):
                            scores = language.letter_score_map()
                            self.assertEqual(
                                optimality._enumerate_slots(current, language, rack, scores),
                                reference_slots(current, language, rack, scores),
                            )
                            actual = optimality.optimize_move(current, language, rack)
                            with patch.object(optimality, "_enumerate_slots", reference_slots):
                                expected = optimality.optimize_move(current, language, rack)
                            self.assertEqual(actual, expected)

    def test_cache_reuses_checks_and_dies_after_each_enumeration(self):
        board = Board.empty(5).place(Move((0,) * 5, 0, ("A", "B")))
        rack = ("A", "B", "B")
        scores = self.language.letter_score_map()
        original = optimality._cross_words_accept
        with patch.object(optimality, "_cross_words_accept", wraps=original) as cross:
            optimality._enumerate_slots(board, self.language, rack, scores)
            cached_calls = cross.call_count
        # The frozen reference has its own imported helper.
        with patch("reference_enumeration._cross_words_accept", wraps=original) as cross:
            reference_slots(board, self.language, rack, scores)
            self.assertLess(cached_calls, cross.call_count)

        references = []
        context_class = optimality._SlotValidationContext

        def create(*args):
            context = context_class(*args)
            references.append(weakref.ref(context))
            return context

        with patch.object(optimality, "_SlotValidationContext", side_effect=create):
            for _ in range(2):
                optimality._enumerate_slots(board, self.language, rack, scores)
            with patch.object(context_class, "accepts", side_effect=RuntimeError("check failed")):
                with self.assertRaisesRegex(RuntimeError, "check failed"):
                    optimality._enumerate_slots(board, self.language, rack, scores)
        gc.collect()
        self.assertEqual(len(references), 3)
        self.assertTrue(all(reference() is None for reference in references))


if __name__ == "__main__":
    unittest.main()
