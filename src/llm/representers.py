from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Protocol

from ..domain.board import Board
from ..domain.models import Symbol
from ..formal.language import StrictlyLocalLanguage


class LanguageRepresenter(Protocol):
    def represent(self, language: StrictlyLocalLanguage) -> str: ...


class BoardRepresenter(Protocol):
    def represent(self, board: Board) -> str: ...


class RackRepresenter(Protocol):
    def represent(self, rack: tuple[Symbol, ...]) -> str: ...


class DefaultLanguageRepresenter:
    def represent(self, language: StrictlyLocalLanguage) -> str:
        return language.describe()


class DefaultBoardRepresenter:
    def represent(self, board: Board) -> str:
        data = {
            "dimensions": board.dimensions,
            "occupied": [
                {"coord": list(coord), "symbol": symbol}
                for coord, symbol in board.occupied_sorted()
            ],
        }
        return json.dumps(data, indent=2, ensure_ascii=False)


class DefaultRackRepresenter:
    def represent(self, rack: tuple[Symbol, ...]) -> str:
        return json.dumps(list(rack), ensure_ascii=False)


@dataclass(frozen=True)
class RepresenterConfig:
    language: LanguageRepresenter = field(default_factory=DefaultLanguageRepresenter)
    board: BoardRepresenter = field(default_factory=DefaultBoardRepresenter)
    rack: RackRepresenter = field(default_factory=DefaultRackRepresenter)
