from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class LLMCallResult:
    content: str
    usage: Mapping[str, object]
    metadata: Mapping[str, object]
