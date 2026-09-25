"""Short notebook actions around the existing evaluation and plotting helpers."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape

from IPython.display import HTML, display
from openrouter import errors as openrouter_errors

from src.benchmark.scoring import score_move

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
from .board_3d import display_grounded_3d, grounded_3d_markup


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
        self._show_move_comparison()
        display(figures.display_attempt_response(self.context))
        display(figures.display_attempt_summary(self.context))
        display(
            _prompt_details(
                str(self.context.attempt.get("system_prompt", "")),
                str(self.context.attempt.get("user_prompt", "")),
            )
        )

    def _show_move_comparison(self) -> None:
        assert self.context is not None
        context = self.context
        evaluation = context.attempt.get("evaluation", {})
        parsed_score = evaluation.get("letter_score_total")
        if parsed_score is None:
            parsed_label = "—"
            parsed_note = "No scored move"
        elif evaluation.get("overall"):
            parsed_label = str(parsed_score)
            parsed_note = "Valid move"
        else:
            parsed_label = str(parsed_score)
            parsed_note = "Invalid move"

        reference_is_optimal = getattr(context, "reference_is_optimal", True)
        reference_score = context.attempt.get("optimal_score")
        if reference_score is None:
            reference_score = score_move(
                context.board,
                context.reference_move,
                context.language.letter_score_map(),
            )
        reference_title = "Optimal move" if reference_is_optimal else "Saved reference move"
        reference_note = "Certified maximum" if reference_is_optimal else "Not certified optimal"

        parsed_panel = (
            _move_score_card("Parsed move", parsed_label, parsed_note)
            + self._comparison_figure("parsed")
        )
        reference_panel = (
            _move_score_card(reference_title, str(reference_score), reference_note)
            + self._comparison_figure("optimal")
        )
        display(HTML(
            "<div style='display:grid;grid-template-columns:repeat(2,minmax(0,1fr));"
            "gap:16px;width:100%;max-width:1200px;align-items:start'>"
            f"<div style='min-width:0;overflow-x:auto'>{parsed_panel}</div>"
            f"<div style='min-width:0;overflow-x:auto'>{reference_panel}</div>"
            "</div>"
        ))

    def _comparison_figure(self, source: figures.MoveSource) -> str:
        assert self.context is not None
        if self.context.board.dimensions > 4:
            return "<p>Board plots are available up to 4D.</p>"
        # In 4D the general plotting helper returns three axis slices. The
        # comparison uses one slice per move so scores and boards stay paired.
        plots = figures.plot_attempt_move(self.context, move_source=source)
        if not plots:
            return "<p>No board plot available.</p>"
        figure = plots[0]
        if self.context.board.dimensions == 3:
            return grounded_3d_markup(figure)
        return figure.to_html(
            include_plotlyjs="cdn",
            full_html=False,
            config={"displaylogo": False, "responsive": True},
        )

    def show_optimal_move(self) -> None:
        if self.context is None:
            raise RuntimeError("Load or generate a response first.")
        if not getattr(self.context, "reference_is_optimal", True):
            print("Historical case: the saved move is not certified optimal.")
        self._show_move("optimal")

    def _show_move(self, source: figures.MoveSource) -> None:
        assert self.context is not None
        if self.context.board.dimensions > 4:
            display(HTML("<p>Board plots are available up to 4D.</p>"))
            return
        for figure in figures.plot_attempt_move(self.context, move_source=source):
            if self.context.board.dimensions == 3:
                display_grounded_3d(figure)
            else:
                display(figure)


def _move_score_card(title: str, score: str, note: str) -> str:
    return (
        "<div style='font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;"
        "border:1px solid #d0d7de;border-radius:8px;padding:12px 14px;"
        "margin:0 0 10px;background:#f6f8fa;color:#1f2937'>"
        f"<div style='font-size:13px;font-weight:700'>{escape(title)}</div>"
        f"<div style='font-size:25px;font-weight:750;line-height:1.25'>{escape(score)}"
        " <span style='font-size:13px;font-weight:500'>points</span></div>"
        f"<div style='font-size:12px;color:#6b7280'>{escape(note)}</div>"
        "</div>"
    )


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
