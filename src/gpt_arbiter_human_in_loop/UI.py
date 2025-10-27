import asyncio
import json
import typing as tp

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Grid
from textual.widget import Widget
from textual.widgets import (
    Button, Footer, Header, Input, RadioButton, RadioSet, 
    Static, Switch, LoadingIndicator, Sparkline, 
)

from .shared import PromptAndExamples, Classifiee, titled
from .arbiter_interface import ArbiterInterface
from .arbiter_gpt import ArbiterGPT
from .arbiter_dummy import ArbiterDummy

class Histogram(Static):
    """ASCII histogram widget for displaying decisions and confidence."""
    
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.data = []  # Will store histogram data
    
    def render(self) -> str:
        # TODO: Implement ASCII histogram rendering
        # Example: [610010029]
        #          No      Yes
        return "[610010029]\nNo      Yes"
    
    def update_data(self, data) -> None:
        """Update histogram data and refresh display."""
        self.data = data
        self.refresh()

class StackedBar(Static):
    """100% stacked bar widget for database coverage."""
    
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.coverage_data = {}  # Will store coverage statistics
    
    def render(self) -> str:
        # TODO: Implement stacked bar rendering
        # Example: [44332100-----------]
        return "[44332100-----------]"
    
    def update_coverage(self, coverage_data) -> None:
        """Update coverage data and refresh display."""
        self.coverage_data = coverage_data
        self.refresh()

class UI(App):
    CSS_PATH = "styles.tcss"
    BINDINGS = [
        Binding("y", "label_yes", "/"),
        Binding("n", "label_no", "."),
        Binding("e", "focus_explanation", "Explain."),
        Binding("ctrl+enter", "submit", "Submit."),
        Binding("w", "ask_why", "Why?"),
        Binding("p", "toggle_pause", "(Un)Pause."),
        Binding("-", "throttle_down", "/"),
        Binding("+", "throttle_up", "Throttle."),
        Binding("t", "throttle_toggle", "Toggle Throttle."),
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

        self.title = "GPT Arbiter Human-in-Loop"

    def readPromptAndExamples(self) -> PromptAndExamples:
        with open(self.prompt_and_examples_filename, 'r') as f:
            j = json.load(f)
            return PromptAndExamples.model_validate(j)
    
    def compose(self) -> ComposeResult:
        # Header
        yield Header(show_clock=False)
        
        with Grid(id="upper-pane"):
            yield titled(Static("$ 0.01", id="cost-display"), 'Cost')
            with titled(Horizontal(id='throttle-pane'), 'Throttle'):
                yield Button("-", id="throttle-down-btn")
                yield Static("10 / sec"  , classes='padding-h-1 auto-width', id="throttle-display")
                yield Button("+", id="throttle-up-btn")
                yield Button("Engage", id="throttle-toggle-btn")
            yield titled(Static("GPT-5-mini", id="model-name"), 'Model')
            with titled(Container(id='progress-box'), 'Progress', skip_bottom=False):
                yield Static("lol")
            with titled(RadioSet(id='on-off'), '', skip_bottom=False):
                yield RadioButton("Judge", id="on-radio")
                yield RadioButton("Pause", id="off-radio", value=True)
            yield titled(Histogram(id="decisions-histogram"), 'Decisions and Confidence', skip_bottom=False)
        
        # Query section
        with Container(id="query-section"):
            yield Static("The GPT arbiter is entrusting you with the following decision!", id="greeter", classes='auto-width margin-h-1')
            yield Static("ID: ...", id="query-id", classes='auto-width margin-h-1')
            yield Static("", id="query-question", classes='auto-width margin-h-1')
            
            # GPT responses
            with Horizontal(id="gpt-inspection"):
                with Container(id="gpt-responses", classes='auto-width margin-h-1'):
                    yield Static('GPT said "No" (1%).', classes='auto-width', id="gpt-no-response")
                    yield Static('GPT said "Yes" (99%).', classes='auto-width', id="gpt-yes-response")
                yield Button("Ask GPT\nwhy", id="ask-why-btn")
            
        # Human input section
        with titled(Grid(id="human-input"), 'What do you think?', skip_bottom=False):
            yield Button("Submit", id="submit-btn")
            with RadioSet(id='yes-no'):
                yield RadioButton("No", id="no-radio")
                yield RadioButton("Yes", id="yes-radio")
            yield Input(placeholder="(Optional) Explain...", id="explanation-input")

        yield Footer(compact=True)
