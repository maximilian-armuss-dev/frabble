from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Literal

from openai import OpenAI


Direction = Literal["H", "V"]


@dataclass(frozen=True)
class DFA:
    alphabet: tuple[str, ...]
    states: tuple[str, ...]
    start_state: str
    accepting_states: frozenset[str]
    transitions: dict[str, dict[str, str]]
    grammar_hint: str

    def accepts(self, word: str) -> bool:
        state = self.start_state
        for token in word:
            if token not in self.alphabet:
                return False
            state = self.transitions[state][token]
        return state in self.accepting_states

    def describe(self) -> str:
        lines = [
            f"Alphabet: {{{', '.join(self.alphabet)}}}",
            f"Start state: {self.start_state}",
            f"Accepting states: {{{', '.join(sorted(self.accepting_states))}}}",
            f"Informal grammar: {self.grammar_hint}",
            "Transition table:",
        ]
        for state in self.states:
            transitions = ", ".join(
                f"{token}->{self.transitions[state][token]}" for token in self.alphabet
            )
            lines.append(f"- {state}: {transitions}")
        return "\n".join(lines)


@dataclass(frozen=True)
class Board:
    cells: tuple[tuple[str | None, ...], ...]

    @property
    def rows(self) -> int:
        return len(self.cells)

    @property
    def cols(self) -> int:
        return len(self.cells[0])

    def at(self, row: int, col: int) -> str | None:
        return self.cells[row][col]

    def has_tiles(self) -> bool:
        return any(cell is not None for row in self.cells for cell in row)

    def render(self) -> str:
        header = "    " + " ".join(str(col) for col in range(self.cols))
        lines = [header]
        for row_idx, row in enumerate(self.cells):
            rendered = " ".join(cell if cell is not None else "." for cell in row)
            lines.append(f"{row_idx}:  {rendered}")
        return "\n".join(lines)


@dataclass(frozen=True)
class Move:
    row: int
    col: int
    direction: Direction
    word: str


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    score: int
    failure_type: str | None = None
    message: str = ""


@dataclass(frozen=True)
class Scenario:
    dfa: DFA
    board: Board
    rack: tuple[str, ...]
    token_scores: dict[str, int]
    accepted_words: tuple[str, ...]
    legal_moves: tuple[Move, ...]

    @property
    def optimal_move(self) -> Move:
        return max(
            self.legal_moves,
            key=lambda move: score_word(move.word, self.token_scores),
        )

    @property
    def optimal_score(self) -> int:
        return score_word(self.optimal_move.word, self.token_scores)


def build_demo_dfa() -> DFA:
    """Language: one or more A, then exactly one B, then zero or more A, then C."""
    alphabet = ("A", "B", "C")
    states = ("q0", "q_before_b", "q_after_b", "q_accept", "q_dead")
    transitions = {
        "q0": {"A": "q_before_b", "B": "q_dead", "C": "q_dead"},
        "q_before_b": {"A": "q_before_b", "B": "q_after_b", "C": "q_dead"},
        "q_after_b": {"A": "q_after_b", "B": "q_dead", "C": "q_accept"},
        "q_accept": {"A": "q_dead", "B": "q_dead", "C": "q_dead"},
        "q_dead": {"A": "q_dead", "B": "q_dead", "C": "q_dead"},
    }
    return DFA(
        alphabet=alphabet,
        states=states,
        start_state="q0",
        accepting_states=frozenset({"q_accept"}),
        transitions=transitions,
        grammar_hint="A word is valid iff it matches A+ B A* C.",
    )


def enumerate_accepted_words(dfa: DFA, max_length: int) -> tuple[str, ...]:
    words: list[str] = []

    def visit(prefix: str) -> None:
        if prefix and dfa.accepts(prefix):
            words.append(prefix)
        if len(prefix) == max_length:
            return
        for token in dfa.alphabet:
            visit(prefix + token)

    visit("")
    return tuple(sorted(words, key=lambda word: (len(word), word)))


def token_frequencies(words: Iterable[str]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for word in words:
        counts.update(word)
    return counts


def token_scores_from_frequencies(
    frequencies: Counter[str], alphabet: Iterable[str]
) -> dict[str, int]:
    total = sum(frequencies.values())
    if total == 0:
        return {token: 1 for token in alphabet}
    scores: dict[str, int] = {}
    for token in alphabet:
        probability = frequencies[token] / total
        scores[token] = max(1, round(-math.log2(probability) * 2))
    return scores


def sample_rack(
    alphabet: tuple[str, ...],
    frequencies: Counter[str],
    rack_size: int,
    rng: random.Random,
) -> tuple[str, ...]:
    weights = [max(1, frequencies[token]) for token in alphabet]
    return tuple(sorted(rng.choices(alphabet, weights=weights, k=rack_size)))


def score_word(word: str, token_scores: dict[str, int]) -> int:
    return sum(token_scores[token] for token in word)


def build_demo_board() -> Board:
    rows, cols = 5, 5
    mutable: list[list[str | None]] = [[None for _ in range(cols)] for _ in range(rows)]
    mutable[2][1] = "A"
    return Board(tuple(tuple(row) for row in mutable))


def validate_move(
    board: Board,
    dfa: DFA,
    rack: tuple[str, ...],
    token_scores: dict[str, int],
    move: Move,
) -> ValidationResult:
    if move.direction not in ("H", "V"):
        return ValidationResult(False, 0, "parse", "Direction must be H or V.")
    if not move.word:
        return ValidationResult(False, 0, "parse", "Word must not be empty.")
    if any(token not in dfa.alphabet for token in move.word):
        return ValidationResult(False, 0, "alphabet", "Word contains unknown tokens.")
    if move.row < 0 or move.col < 0:
        return ValidationResult(False, 0, "spatial", "Move starts outside the board.")

    delta_row = 0 if move.direction == "H" else 1
    delta_col = 1 if move.direction == "H" else 0
    end_row = move.row + delta_row * (len(move.word) - 1)
    end_col = move.col + delta_col * (len(move.word) - 1)
    if end_row >= board.rows or end_col >= board.cols:
        return ValidationResult(False, 0, "spatial", "Word does not fit on the board.")

    needed = Counter()
    touches_existing = False
    placed_new_token = False
    for offset, token in enumerate(move.word):
        row = move.row + delta_row * offset
        col = move.col + delta_col * offset
        current = board.at(row, col)
        if current is None:
            needed[token] += 1
            placed_new_token = True
            continue
        if current != token:
            return ValidationResult(
                False,
                0,
                "overlap",
                f"Board has {current} at ({row}, {col}), but move needs {token}.",
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
    if not dfa.accepts(move.word):
        return ValidationResult(
            False,
            0,
            "language",
            "The submitted word is not accepted by the DFA.",
        )
    return ValidationResult(True, score_word(move.word, token_scores), None, "valid")


def enumerate_legal_moves(
    board: Board,
    dfa: DFA,
    rack: tuple[str, ...],
    token_scores: dict[str, int],
    accepted_words: Iterable[str],
) -> tuple[Move, ...]:
    legal_moves: list[Move] = []
    for word in accepted_words:
        for direction in ("H", "V"):
            for row in range(board.rows):
                for col in range(board.cols):
                    move = Move(row=row, col=col, direction=direction, word=word)
                    result = validate_move(board, dfa, rack, token_scores, move)
                    if result.ok:
                        legal_moves.append(move)
    return tuple(legal_moves)


def generate_scenario(seed: int = 7, rack_size: int = 4) -> Scenario:
    rng = random.Random(seed)
    dfa = build_demo_dfa()
    board = build_demo_board()
    accepted_words = enumerate_accepted_words(dfa, max_length=board.cols)
    frequencies = token_frequencies(accepted_words)
    token_scores = token_scores_from_frequencies(frequencies, dfa.alphabet)

    for _ in range(500):
        rack = sample_rack(dfa.alphabet, frequencies, rack_size, rng)
        legal_moves = enumerate_legal_moves(board, dfa, rack, token_scores, accepted_words)
        if legal_moves:
            return Scenario(
                dfa=dfa,
                board=board,
                rack=rack,
                token_scores=token_scores,
                accepted_words=accepted_words,
                legal_moves=legal_moves,
            )

    rack = ("A", "A", "B", "C")
    legal_moves = enumerate_legal_moves(board, dfa, rack, token_scores, accepted_words)
    return Scenario(
        dfa=dfa,
        board=board,
        rack=rack,
        token_scores=token_scores,
        accepted_words=accepted_words,
        legal_moves=legal_moves,
    )


def build_prompt(scenario: Scenario) -> tuple[str, str]:
    score_lines = "\n".join(
        f"- {token}: {score}" for token, score in sorted(scenario.token_scores.items())
    )
    system_prompt = (
        "You are playing a formal-language Scrabble benchmark. "
        "You must solve the task without tools. Return only valid JSON."
    )
    user_prompt = f"""Your task is to place exactly one contiguous word on the board.

Coordinates are zero-based. Direction "H" means left-to-right. Direction "V" means top-to-bottom.
The move must stay inside the board, overlap at least one existing board token, and use only the rack tokens for newly placed cells.
The full submitted word must be accepted by the formal language.
Maximize the word score. The score is the sum of token scores over the full submitted word.

Formal language:
{scenario.dfa.describe()}

Board:
{scenario.board.render()}

Rack multiset:
{list(scenario.rack)}

Token scores:
{score_lines}

Return exactly this JSON shape and nothing else:
{{"row": 2, "col": 1, "direction": "H", "word": "ABC"}}
"""
    return system_prompt, user_prompt


def parse_move(raw_text: str) -> Move:
    text = raw_text.strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise ValueError("Model output did not contain a JSON object.") from None
        payload = json.loads(match.group(0))

    direction = str(payload["direction"]).upper()
    if direction not in ("H", "V"):
        raise ValueError("direction must be H or V")
    return Move(
        row=int(payload["row"]),
        col=int(payload["col"]),
        direction=direction,  # type: ignore[arg-type]
        word=str(payload["word"]).strip().upper(),
    )


def call_openai(system_prompt: str, user_prompt: str) -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    model = os.environ.get("OPENAI_MODEL")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for --call-model.")
    if not model:
        raise RuntimeError("OPENAI_MODEL is required for --call-model.")

    client_kwargs = {"api_key": api_key}
    base_url = os.environ.get("OPENAI_BASE_URL")
    if base_url:
        client_kwargs["base_url"] = base_url
    client = OpenAI(**client_kwargs)

    request = {
        "model": model,
        "input": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    reasoning_effort = os.environ.get("OPENAI_REASONING_EFFORT")
    if reasoning_effort:
        request["reasoning"] = {"effort": reasoning_effort}

    response = client.responses.create(**request)
    output_text = getattr(response, "output_text", None)
    if output_text:
        return output_text

    data = response.model_dump()
    chunks: list[str] = []
    for item in data.get("output", []):
        for content in item.get("content", []):
            text = content.get("text")
            if text:
                chunks.append(text)
    if not chunks:
        raise RuntimeError("OpenAI response did not contain output text.")
    return "\n".join(chunks)


def print_scenario_summary(scenario: Scenario) -> None:
    print("Board:")
    print(scenario.board.render())
    print()
    print(f"Rack: {list(scenario.rack)}")
    print(f"Token scores: {scenario.token_scores}")
    print(f"Accepted words up to board width: {list(scenario.accepted_words)}")
    print(f"Number of legal moves: {len(scenario.legal_moves)}")
    print(
        "Optimal move: "
        f"{scenario.optimal_move} with score {scenario.optimal_score}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--call-model", action="store_true")
    parser.add_argument("--show-prompt", action="store_true")
    args = parser.parse_args()

    scenario = generate_scenario(seed=args.seed)
    system_prompt, user_prompt = build_prompt(scenario)

    print_scenario_summary(scenario)
    if args.show_prompt:
        print("\n--- SYSTEM PROMPT ---")
        print(system_prompt)
        print("\n--- USER PROMPT ---")
        print(user_prompt)

    if args.dry_run and not args.call_model:
        return
    if not args.call_model:
        print("\nNo model call requested. Use --call-model to query OpenAI.")
        return

    raw_output = call_openai(system_prompt, user_prompt)
    print("\n--- MODEL OUTPUT ---")
    print(raw_output)
    move = parse_move(raw_output)
    result = validate_move(
        scenario.board,
        scenario.dfa,
        scenario.rack,
        scenario.token_scores,
        move,
    )
    print("\n--- VALIDATION ---")
    print(json.dumps(result.__dict__, indent=2, ensure_ascii=False))
    if result.ok:
        normalized = result.score / scenario.optimal_score
        print(f"normalized_score: {normalized:.3f}")


if __name__ == "__main__":
    main()

