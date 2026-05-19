# Board visualization

This folder contains interactive Plotly visualizations for sparse multidimensional Scrabble boards.

- `board_figures.py`: reusable helpers for loading scenarios, plotting 2D/3D boards, and animating scenario transitions.
- `board_visualization.ipynb`: a short notebook that loads `outputs/generator_v1.json` and displays the interactive figures.

The 2D view uses a Plotly heatmap so adjacent coordinates render as adjacent Scrabble-like tiles. Axes, gridlines, and titles are hidden by default; hover details remain available for inspection.

## Typical use

```python
from visualization.board_figures import (
    animate_scenario_2d,
    load_scenario_json,
    plot_board_2d,
    scenario_boards_and_placements,
)

scenario = load_scenario_json("outputs/generator_v1.json")
boards, placements = scenario_boards_and_placements(scenario)

plot_board_2d(boards[-1], highlight_coords=placements[-1])
animate_scenario_2d(scenario)
```
