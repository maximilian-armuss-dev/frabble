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


class ChineseAlphabetSampler:
    """Draws single CJK ideographs without replacement, returned in sorted order."""

    # Common CJK Unified Ideographs block (U+4E00–U+9FFF), each a single character.
    _POOL_START = 0x4E00
    _POOL_END = 0x9FFF

    def sample(self, size: int, seed: int) -> tuple[Symbol, ...]:
        pool_size = self._POOL_END - self._POOL_START + 1
        if size < 1 or size > pool_size:
            raise ValueError(f"alphabet size must be between 1 and {pool_size}, got {size}")
        pool = [chr(self._POOL_START + i) for i in range(pool_size)]
        rng = random.Random(seed)
        return tuple(sorted(rng.sample(pool, size)))
