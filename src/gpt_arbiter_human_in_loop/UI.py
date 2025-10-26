import asyncio
import json
import typing as tp

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Input, RadioButton, RadioSet, Static, Switch

from shared import PromptAndExamples, Classifiee, QAPair
from arbiter_interface import ArbiterInterface
from arbiter_gpt import ArbiterGPT
from arbiter_dummy import ArbiterDummy

class UI(App):
    """Textual TUI shell for the GPT Arbiter human-in-loop flow."""

    CSS = """
    Screen {
        layout: vertical;
        background: $surface;
    }

    #main {
        layout: vertical;
        padding: 1 2;
        gap: 1;
    }

    .title {
        text-style: bold;
        letter-spacing: 1;
    }

    .strip {
        padding: 0 1;
        border: tall $primary;
        height: auto;
    }

    .strip Horizontal {
        align: center middle;
        gap: 1;
    }

    .label {
        color: $text 50%;
    }

    .divider {
        width: 1;
        height: 100%;
        background: $text 60%;
        opacity: 0.4;
    }

    .histogram {
        font-family: monospace;
    }

    .section-card {
        border: tall $secondary;
        padding: 1 2;
        gap: 1;
    }

    .section-title {
        text-style: bold;
    }

    .question {
        height: auto;
        border: round $boost;
        padding: 1;
    }

    .explanation-input {
        width: 100%;
    }

    #decision-controls {
        align: left top;
        gap: 1;
    }
    """

    BINDINGS = [
        Binding("y", "label_yes", "Yes"),
        Binding("n", "label_no", "No"),
        Binding("e", "focus_explanation", "Focus Explanation"),
        Binding("ctrl+enter", "submit", "Submit"),
        Binding("w", "ask_why", "Ask Why"),
        Binding("p", "toggle_pause", "Pause/Resume"),
        Binding("-", "throttle_down", "Throttle -"),
        Binding("+", "throttle_up", "Throttle +"),
    ]

    def __init__(
        self, 
        arbiter: ArbiterInterface,
        prompt_and_examples_filename: str,
        all_ids: tp.Sequence[str],
        idToClassifiee: tp.Callable[[str], Classifiee],
        initial_throttle_qps: float = 10.0, # queries per second
    ) -> None:
        super().__init__()

        self.arbiter = arbiter
        self.prompt_and_examples_filename = prompt_and_examples_filename
        self.all_ids = all_ids
        self.idToClassifiee = idToClassifiee

        self.throttle_qps = initial_throttle_qps
        self.is_paused = False

        self.prompt_and_examples = self.readPromptAndExamples()

    def readPromptAndExamples(self) -> PromptAndExamples:
        with open(self.prompt_and_examples_filename, 'r') as f:
            j = json.load(f)
            return PromptAndExamples.model_validate(j)
    
    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header(show_clock=False)

        main = Vertical(id="main")
        main.mount(Static("GPT Arbiter Human-in-Loop", classes="title"))
        main.mount(self._build_model_strip())
        main.mount(self._build_status_strip())
        main.mount(self._build_decision_histogram())
        main.mount(self._build_query_card())
        yield main

        yield Footer()

    # --- Layout builders -------------------------------------------------

    def _build_model_strip(self) -> Vertical:
        strip = Vertical(classes="strip")
        row = Horizontal()
        row.mount(Static("Model:", classes="label"))
        row.mount(Static("", id="model-name"))
        row.mount(self._divider())
        row.mount(Static("Cost:", classes="label"))
        row.mount(Static("", id="cost-indicator"))
        row.mount(self._divider())
        row.mount(Button("-", id="throttle-down"))
        row.mount(Static("", id="throttle-display"))
        row.mount(Button("+", id="throttle-up"))
        strip.mount(row)
        return strip

    def _build_status_strip(self) -> Vertical:
        strip = Vertical(classes="strip")
        row = Horizontal()
        row.mount(Static("Paused", classes="label"))
        row.mount(Switch(id="status-toggle"))
        row.mount(Static("Judging", classes="label"))
        row.mount(self._divider())
        row.mount(Static(" / ", id="progress-indicator"))
        row.mount(self._divider())
        row.mount(Static("Coverage:", classes="label"))
        row.mount(Static("[]", id="coverage-hist", classes="histogram"))
        strip.mount(row)
        return strip

    def _divider(self) -> Static:
        return Static("", classes="divider")

    def _build_decision_histogram(self) -> Vertical:
        section = Vertical(classes="section-card")
        section.mount(Static("Decisions and Confidence", classes="section-title"))
        # section.mount(Static("[610010029]", id="decision-histogram", classes="histogram"))
        # section.mount(Static("No      Yes", classes="histogram"))
        return section

    def _build_query_card(self) -> Vertical:
        card = Vertical(classes="section-card")
        card.mount(Static("Query Human", classes="section-title"))
        card.mount(Static("ID: ", id="query-id"))
        card.mount(Static("", id="question", classes="question"))

        gpt_reasoning = Vertical()
        gpt_reasoning.mount(Static("GPT said \"No\" (99%) because \"...\"", id="gpt-no"))
        gpt_reasoning.mount(Static("And \"Yes\" (1%) because \"...\"", id="gpt-yes"))
        gpt_reasoning.mount(Button("Ask GPT why", id="ask-why-button"))
        card.mount(gpt_reasoning)

        decision_area = Vertical()
        decision_area.mount(Static("What do you think?", classes="section-title"))
        radio = RadioSet(id="decision-controls")
        radio.mount(RadioButton("Yes", id="decision-yes"))
        radio.mount(RadioButton("No", id="decision-no"))
        radio.mount(RadioButton("Skip", id="decision-skip"))
        decision_area.mount(radio)
        decision_area.mount(Input(placeholder="Explanation (optional)", id="explanation-input", classes="explanation-input"))
        decision_area.mount(Button("Submit", id="submit-button", variant="primary"))
        card.mount(decision_area)

        return card

    def action_label_yes(self) -> None:  # pragma: no cover - placeholder
        """Handle the `y` binding. Logic is supplied by the caller."""

    def action_label_no(self) -> None:  # pragma: no cover - placeholder
        """Handle the `n` binding. Logic is supplied by the caller."""

    def action_focus_explanation(self) -> None:  # pragma: no cover - placeholder
        """Focus the explanation input. Implementation deferred."""

    def action_submit(self) -> None:  # pragma: no cover - placeholder
        """Submit the human decision. Implementation deferred."""

    def action_ask_why(self) -> None:  # pragma: no cover - placeholder
        """Trigger Ask-GPT-why flow. Implementation deferred."""

    def action_toggle_pause(self) -> None:  # pragma: no cover - placeholder
        """Toggle between judging and paused states."""

    def action_throttle_down(self) -> None:  # pragma: no cover - placeholder
        """Decrease the throttle. Implementation deferred."""

    def action_throttle_up(self) -> None:  # pragma: no cover - placeholder
        """Increase the throttle. Implementation deferred."""
