from __future__ import annotations

from ortools.sat.python import cp_model

from ..domain.models import Symbol
from .language import StrictlyLocalLanguage


class SlotCSP:
    def __init__(self, language: StrictlyLocalLanguage) -> None:
        self.language = language
        self._automaton: (
            tuple[int, list[int], list[tuple[int, int, int]], dict[Symbol, int]] | None
        ) = None

    def solve(self, domains: list[set[Symbol]]) -> tuple[Symbol, ...] | None:
        if len(domains) < self.language.min_word_length:
            return None

        for domain in domains:
            if not domain:
                return None
            unknown = sorted(set(domain) - set(self.language.alphabet))
            if unknown:
                raise ValueError(f"Domain contains symbols outside the language alphabet: {unknown}")

        if self._automaton is None:
            self._automaton = self.language.ortools_automaton()
        start_state, final_states, transitions, symbol_ids = self._automaton
        id_symbols = {symbol_id: symbol for symbol, symbol_id in symbol_ids.items()}
        model = cp_model.CpModel()
        variables: list[cp_model.IntVar] = []

        for index, domain in enumerate(domains):
            domain_values = sorted(symbol_ids[symbol] for symbol in domain)
            variable = model.NewIntVarFromDomain(
                cp_model.Domain.FromValues(domain_values),
                f"x_{index}",
            )
            variables.append(variable)

        model.AddAutomaton(variables, start_state, final_states, transitions)
        model.AddDecisionStrategy(
            variables,
            cp_model.CHOOSE_FIRST,
            cp_model.SELECT_MIN_VALUE,
        )

        solver = cp_model.CpSolver()
        solver.parameters.search_branching = cp_model.FIXED_SEARCH
        solver.parameters.num_search_workers = 1
        status = solver.Solve(model)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return None
        return tuple(id_symbols[solver.Value(variable)] for variable in variables)
