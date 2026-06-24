from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx

from src.domain.visualization import build_dfa_graph
from src.formal.grammar.serialization import load_grammar


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GRAMMAR_PATH = PROJECT_ROOT / "outputs/grammars/presentation_toy_grammar.json"
OUTPUT_PATH = PROJECT_ROOT / "outputs/figures/presentation_toy_grammar_dfa.png"


def main() -> None:
    grammar, _, _ = load_grammar(GRAMMAR_PATH)
    dfa = grammar.to_dfa()
    graph = build_dfa_graph(dfa)

    state_labels = {
        "p0:": "q₀",
        "p1:A": "qₐ",
        "p1:B": "qᵦ",
        "r:B": "qₐᵦ",
        "dead": "⊥",
    }
    if set(graph.nodes) != set(state_labels):
        raise ValueError(f"Unexpected DFA states: {sorted(graph.nodes)}")

    positions = {
        "p0:": (0.0, 0.0),
        "p1:A": (0.82, 0.45),
        "p1:B": (0.82, -0.45),
        "r:B": (1.64, 0.45),
        "dead": (1.64, -0.45),
    }

    figure, axis = plt.subplots(figsize=(5.2, 2.8))
    node_colors = [
        "#b8e3c6" if state in dfa.accepting_states else
        "#f3c5c5" if state == "dead" else
        "#e9edf5"
        for state in graph.nodes
    ]
    nx.draw_networkx_nodes(
        graph,
        positions,
        node_color=node_colors,
        edgecolors="#20242a",
        linewidths=1.8,
        node_size=1500,
        ax=axis,
    )
    nx.draw_networkx_nodes(
        graph,
        positions,
        nodelist=list(dfa.accepting_states),
        node_color="none",
        edgecolors="#20242a",
        linewidths=1.4,
        node_size=1240,
        ax=axis,
    )
    nx.draw_networkx_labels(
        graph,
        positions,
        labels=state_labels,
        font_size=15,
        font_weight="bold",
        ax=axis,
    )
    nx.draw_networkx_edges(
        graph,
        positions,
        arrows=True,
        arrowstyle="-|>",
        arrowsize=18,
        connectionstyle="arc3,rad=0.0",
        width=1.5,
        edge_color="#555b66",
        node_size=1500,
        ax=axis,
    )
    nx.draw_networkx_edge_labels(
        graph,
        positions,
        edge_labels=nx.get_edge_attributes(graph, "label"),
        font_size=11,
        label_pos=0.5,
        rotate=False,
        bbox={
            "boxstyle": "round,pad=0.15",
            "facecolor": "white",
            "edgecolor": "none",
            "alpha": 0.9,
        },
        ax=axis,
    )

    axis.annotate(
        "",
        xy=(-0.20, 0.0),
        xytext=(-0.52, 0.0),
        arrowprops={"arrowstyle": "-|>", "color": "#20242a", "lw": 1.8},
    )
    axis.set_xlim(-0.6, 2.02)
    axis.set_ylim(-0.82, 0.82)
    axis.axis("off")
    figure.tight_layout(pad=0.2)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(OUTPUT_PATH, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(figure)
    print(OUTPUT_PATH)


if __name__ == "__main__":
    main()
