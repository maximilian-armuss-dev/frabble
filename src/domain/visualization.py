from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx

from .models import DFA


def build_dfa_graph(dfa: DFA) -> nx.DiGraph:
    graph = nx.DiGraph()
    for state in dfa.states:
        graph.add_node(
            state,
            accepting=state in dfa.accepting_states,
            start=state == dfa.start_state,
        )

    edge_labels: dict[tuple[str, str], list[str]] = {}
    for source, transitions in dfa.transitions.items():
        for symbol, target in transitions.items():
            graph.add_edge(source, target)
            edge_labels.setdefault((source, target), []).append(symbol)

    nx.set_edge_attributes(
        graph,
        {
            edge: ",".join(sorted(symbols))
            for edge, symbols in edge_labels.items()
        },
        "label",
    )
    return graph


def render_dfa_png(dfa: DFA, output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    graph = build_dfa_graph(dfa)
    positions = nx.spring_layout(graph, seed=11)
    node_colors = [
        "#b8e3c6" if graph.nodes[state]["accepting"] else "#e9edf5"
        for state in graph.nodes
    ]
    node_widths = [
        3.0 if graph.nodes[state]["start"] else 1.5
        for state in graph.nodes
    ]

    plt.figure(figsize=(9, 6))
    nx.draw_networkx_nodes(
        graph,
        positions,
        node_color=node_colors,
        edgecolors="#20242a",
        linewidths=node_widths,
        node_size=2400,
    )
    nx.draw_networkx_labels(graph, positions, font_size=10, font_weight="bold")
    nx.draw_networkx_edges(
        graph,
        positions,
        arrows=True,
        arrowstyle="-|>",
        arrowsize=18,
        connectionstyle="arc3,rad=0.12",
        width=1.4,
        edge_color="#555b66",
    )
    edge_labels = nx.get_edge_attributes(graph, "label")
    nx.draw_networkx_edge_labels(
        graph,
        positions,
        edge_labels=edge_labels,
        font_size=9,
        label_pos=0.45,
        rotate=False,
        bbox={"boxstyle": "round,pad=0.2", "facecolor": "white", "edgecolor": "none"},
    )

    plt.title("Strictly Local DFA", fontsize=14)
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(output, dpi=180)
    plt.close()
    return output
