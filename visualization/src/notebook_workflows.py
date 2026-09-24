"""Short notebook actions around the existing evaluation and plotting helpers."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape

from IPython.display import HTML, display
from openrouter import errors as openrouter_errors

from . import evaluation_figures as figures
from .case_playground import (
    PreparedCasePlayground,
    PreparedCaseRecord,
    load_saved_case_attempt,
    prepare_selected_case,
    run_prepared_case,
)
from .case_selection_widget import CasePickerSelection, OverviewFilterSelection
from .evaluation_figures import EvaluationAttemptContext
from .board_3d import display_grounded_3d


def _prompt_details(system_prompt: str, user_prompt: str) -> HTML:
    return HTML(
        "<details style='margin:10px 0; max-width:920px'>"
        "<summary style='cursor:pointer'>View prompt</summary>"
        "<div style='margin-top:10px'><b>System</b>"
        "<pre style='white-space:pre-wrap;max-height:360px;overflow:auto'>"
        f"{escape(system_prompt)}</pre><b>User</b>"
        "<pre style='white-space:pre-wrap;max-height:360px;overflow:auto'>"
        f"{escape(user_prompt)}</pre></div></details>"
    )


@dataclass
class ModelPlaygroundSession:
    picker: CasePickerSelection
    case: PreparedCaseRecord
    mode: str
    prepared: PreparedCasePlayground | None = None
    context: EvaluationAttemptContext | None = None

    async def send(self) -> None:
        """Send exactly one request in fresh mode after checking the previewed case."""
        if self.mode == "saved":
            print("Saved mode: no model request sent.")
            return
        if self.context is not None:
            print("Response already available. Run step 2 again to start a new request.")
            return
        if self.picker.selected_case() != self.case:
            raise ValueError("The puzzle selection changed. Run step 2 again.")
        if self.prepared is None:
            raise RuntimeError("Prepare the case in step 2 first.")
        try:
            self.context = await run_prepared_case(self.prepared)
        except openrouter_errors.UnauthorizedResponseError:
            raise RuntimeError(
                "OpenRouter rejected OPENROUTER_API_KEY (HTTP 401). "
                "Set a valid key in the repository .env file or your environment, "
                "restart the notebook kernel, then rerun from step 1. "
                "No model response was created."
            ) from None
        print("New response saved and evaluated.")

    def show_answer(self) -> None:
        if self.context is None:
            raise RuntimeError("Run step 3 to get a new response.")
        display(figures.display_attempt_response(self.context))
        display(figures.display_attempt_summary(self.context))
        display(
            _prompt_details(
                str(self.context.attempt.get("system_prompt", "")),
                str(self.context.attempt.get("user_prompt", "")),
            )
        )
        self._show_move("parsed")

    def show_witness(self) -> None:
        if self.context is None:
            raise RuntimeError("Load or generate a response first.")
        self._show_move("ground_truth")

    def _show_move(self, source: figures.MoveSource) -> None:
        assert self.context is not None
        for figure in figures.plot_attempt_move(self.context, move_source=source):
            if self.context.board.dimensions == 3:
                display_grounded_3d(figure)
            else:
                display(figure)


def open_model_playground(
    picker: CasePickerSelection | None,
    mode: str,
    model_name: str,
    reasoning_effort: str,
) -> ModelPlaygroundSession:
    """Load a saved answer or preview one fresh model request."""
    if picker is None:
        raise RuntimeError("Run the puzzle selection cell first.")
    if mode not in ("saved", "fresh"):
        raise ValueError("MODE must be 'saved' or 'fresh'.")
    case = picker.selected_case()
    session = ModelPlaygroundSession(picker=picker, case=case, mode=mode)
    if mode == "saved":
        session.context = load_saved_case_attempt(case, model_name)
        display(HTML("<span>Saved response loaded.</span>"))
    else:
        session.prepared = prepare_selected_case(case, model_name, reasoning_effort)
        display(
            HTML(
                f"<span>Prompt bereit: {case.dimensions}D · "
                f"{case.visible_sequences} Sequences · Round {case.sampling_round} · "
                f"{escape(model_name)} · {escape(reasoning_effort)}</span>"
            )
        )
        display(
            _prompt_details(
                session.prepared.system_prompt, session.prepared.user_prompt
            )
        )
    return session


def load_overview_selection(
    filters: OverviewFilterSelection | None,
) -> dict[str, object]:
    """Rebuild the aggregate from the checked axes of one completed run."""
    if filters is None:
        raise RuntimeError("Run the filter selection cell first.")
    _, aggregate, attempt_count = filters.aggregate()
    display(
        HTML(
            f"<span>Loaded {attempt_count} attempts from run #{filters.run.value} "
            "for the overview.</span>"
        )
    )
    return aggregate
