from __future__ import annotations

import numpy as np

from .models import Board


def build_demo_board() -> Board:
    cells = np.full((5, 5), None, dtype=object)
    cells[2, 1] = "A"
    return Board(cells=cells)
