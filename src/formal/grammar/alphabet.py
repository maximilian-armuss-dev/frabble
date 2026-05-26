from __future__ import annotations

import random
from typing import Protocol

from ...domain.models import Symbol


class AlphabetSampler(Protocol):
    def sample(self, size: int, seed: int) -> tuple[Symbol, ...]: ...


class LetterAlphabetSampler:
    """Draws letters from A–Z (or a–z) without replacement, returned in sorted order."""

    def __init__(self, case: str = "upper") -> None:
        if case not in ("upper", "lower"):
            raise ValueError(f"case must be 'upper' or 'lower', got {case!r}")
        self.case = case

    def sample(self, size: int, seed: int) -> tuple[Symbol, ...]:
        if size < 1 or size > 26:
            raise ValueError(f"alphabet size must be between 1 and 26, got {size}")
        start = ord("A") if self.case == "upper" else ord("a")
        pool = [chr(start + i) for i in range(26)]
        rng = random.Random(seed)
        return tuple(sorted(rng.sample(pool, size)))
