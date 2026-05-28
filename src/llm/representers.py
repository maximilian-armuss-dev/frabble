from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Protocol

from ..domain.board import Board
from ..domain.models import Symbol
from ..formal.language import StrictlyLocalLanguage


class LanguageRepresenter(Protocol):
    @property
    def name(self) -> str: ...

    def represent(self, language: StrictlyLocalLanguage) -> str: ...


class BoardRepresenter(Protocol):
    @property
    def name(self) -> str: ...

    def represent(self, board: Board) -> str: ...


class RackRepresenter(Protocol):
    @property
    def name(self) -> str: ...

    def represent(self, rack: tuple[Symbol, ...]) -> str: ...


class ForbiddenSnippetsLanguageRepresenter:
    @property
    def name(self) -> str:
        return "forbidden-snippets"

    def represent(self, language: StrictlyLocalLanguage) -> str:
        return language.describe()


class CoordinatesJsonBoardRepresenter:
    @property
    def name(self) -> str:
        return "coordinates-json"

    def represent(self, board: Board) -> str:
        data = {
            "dimensions": board.dimensions,
            "occupied": [
                {"coord": list(coord), "symbol": symbol}
                for coord, symbol in board.occupied_sorted()
            ],
        }
        return json.dumps(data, indent=2, ensure_ascii=False)


class SymbolJsonRackRepresenter:
    @property
    def name(self) -> str:
        return "symbol-json"

    def represent(self, rack: tuple[Symbol, ...]) -> str:
        return json.dumps(list(rack), ensure_ascii=False)


@dataclass(frozen=True)
class RepresenterConfig:
    language: LanguageRepresenter = field(default_factory=ForbiddenSnippetsLanguageRepresenter)
    board: BoardRepresenter = field(default_factory=CoordinatesJsonBoardRepresenter)
    rack: RackRepresenter = field(default_factory=SymbolJsonRackRepresenter)


LANGUAGE_REPRESENTERS: dict[str, LanguageRepresenter] = {
    r.name: r for r in [ForbiddenSnippetsLanguageRepresenter()]
}

BOARD_REPRESENTERS: dict[str, BoardRepresenter] = {
    r.name: r for r in [CoordinatesJsonBoardRepresenter()]
}

RACK_REPRESENTERS: dict[str, RackRepresenter] = {
    r.name: r for r in [SymbolJsonRackRepresenter()]
}
