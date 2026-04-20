import unittest

from llm_scrabble_bench.prototype import (
    Move,
    build_demo_dfa,
    generate_scenario,
    parse_move,
    validate_move,
)


class PrototypeTests(unittest.TestCase):
    def test_demo_dfa_accepts_expected_language(self):
        dfa = build_demo_dfa()

        self.assertTrue(dfa.accepts("ABC"))
        self.assertTrue(dfa.accepts("AABC"))
        self.assertTrue(dfa.accepts("ABAAC"))
        self.assertFalse(dfa.accepts("AC"))
        self.assertFalse(dfa.accepts("ABBC"))
        self.assertFalse(dfa.accepts("ABCA"))

    def test_scenario_has_legal_optimal_move(self):
        scenario = generate_scenario(seed=7)

        self.assertGreater(len(scenario.legal_moves), 0)
        result = validate_move(
            scenario.board,
            scenario.dfa,
            scenario.rack,
            scenario.token_scores,
            scenario.optimal_move,
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.score, scenario.optimal_score)

    def test_validator_rejects_rack_failure(self):
        scenario = generate_scenario(seed=7)
        move = Move(row=2, col=0, direction="H", word="AAABC")

        result = validate_move(
            scenario.board,
            scenario.dfa,
            rack=("B", "C"),
            token_scores=scenario.token_scores,
            move=move,
        )

        self.assertFalse(result.ok)
        self.assertEqual(result.failure_type, "rack")

    def test_parse_move_accepts_json_object(self):
        move = parse_move('{"row": 2, "col": 1, "direction": "h", "word": "abc"}')

        self.assertEqual(move, Move(row=2, col=1, direction="H", word="ABC"))


if __name__ == "__main__":
    unittest.main()
