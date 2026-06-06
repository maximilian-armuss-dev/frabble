from __future__ import annotations

import hashlib
import random

from .config import NumericAxis, NumericRange


def derive_seed(root_seed: int, *parts: object) -> int:
    payload = "|".join([str(root_seed), *(str(part) for part in parts)])
    digest = hashlib.sha256(payload.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") & 0x7FFFFFFF


def sample_axis(
    value: NumericAxis,
    *,
    seed: int,
    integer: bool,
) -> int | float:
    if not isinstance(value, NumericRange):
        return int(value) if integer else float(value)
    if value.min == value.max:
        sampled = value.min
    else:
        rng = random.Random(seed)
        midpoint = (value.min + value.max) / 2
        standard_deviation = (value.max - value.min) / 6
        for _ in range(1000):
            sampled = rng.gauss(midpoint, standard_deviation)
            if value.min <= sampled <= value.max:
                break
        else:
            sampled = min(max(midpoint, value.min), value.max)
    if integer:
        return min(max(round(sampled), round(value.min)), round(value.max))
    return min(max(float(sampled), value.min), value.max)
