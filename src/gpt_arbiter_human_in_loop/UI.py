import asyncio
import json
import typing as tp
import time
import math

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Grid
from textual.widgets import (
    Button, Footer, Header, Input, RadioButton, RadioSet, Static, 
)

from .shared import PromptAndExamples, Classifiee, titled, ItemStatus, QAPair
from .stacked_bar_ascii import StackedBar
from .histogram_ascii import Histogram
from .arbiter_interface import ArbiterInterface
from .persistent import Persistent, ItemAnnotations

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
        rw_json_path: str,
        model_name: str = 'gpt-5-nano',
        initial_throttle_qps: float = 10.0, # queries per second
    ) -> None:
        super().__init__()

        self.arbiter = arbiter
        self.prompt_and_examples_filename = prompt_and_examples_filename
        self.all_ids = all_ids
        self.idToClassifiee = idToClassifiee
        self.model_name = model_name

        self.throttle_active = True
        self.throttle_qps = initial_throttle_qps
        self.is_paused = False

        self.persistent = Persistent(rw_json_path)
        self.Context = self.persistent.Context
        self.cursor = 0
        self.last_gpt_time = 0.0
        self.arbitTask: asyncio.Task | None = None

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
                yield StackedBar('-0123456789', id='stacked-bar')
            with titled(RadioSet(id='on-off'), 'GPT Switch', skip_bottom=False):
                yield RadioButton("Judge", id="on-radio")
                yield RadioButton("Pause", id="off-radio", value=True)
            yield titled(Histogram(
                ('No', 'Yes'), id="decisions-histogram",
            ), 'Decisions and Confidence', skip_bottom=False)
        
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
    
    def action_label_yes(self) -> None:
        b = self.query_one('#yes-radio', RadioButton)
        b.value = True
    
    def action_label_no(self) -> None:
        b = self.query_one('#no-radio', RadioButton)
        b.value = True

    def action_focus_explanation(self) -> None:
        e = self.query_one('#explanation-input', Input)
        e.focus()
    
    @on(Input.Submitted, '#explanation-input')
    def focus_submit(self) -> None:
        b = self.query_one('#submit-btn', Button)
        b.focus()

    @on(Button.Pressed, '#submit-btn')
    def action_submit(self) -> None:
        ...
    
    @on(Button.Pressed, '#ask-why-btn')
    async def action_ask_why(self) -> None:
        b = self.query_one('#ask-why-btn', Button)
        b.disabled = True
        ...
    
    def action_toggle_pause(self) -> None:
        bOff = self.query_one('#off-radio', RadioButton)
        bOn  = self.query_one( '#on-radio', RadioButton)
        if bOff.value:
            bOn.value = True
        else:
            bOff.value = True
    
    @on(RadioSet.Changed, '#on-off')
    def on_toggle_gpt_switch(self) -> None:
        self.is_paused = self.query_one('#off-radio', RadioButton).value
        if not self.is_paused:
            if self.arbitTask is None:
                self.arbitNext()
    
    def arbitNext(self) -> bool:
        assert self.arbitTask is None
        initial_cursor = self.cursor
        while True:
            id_ = self.all_ids[self.cursor]
            try:
                annotations = self.persistent.data[id_]
            except KeyError:
                break
            else:
                if annotations.human_label_no_or_yes is not None:
                    self.persistent.data[id_] = ItemAnnotations(
                        gpt_verdict=float(annotations.human_label_no_or_yes),
                        status=ItemStatus.Classified(),
                        human_label_no_or_yes=annotations.human_label_no_or_yes,
                    )
                if annotations.status != ItemStatus.Classified():
                    break
            self.cursor += 1
            self.cursor %= len(self.all_ids)
            if self.cursor == initial_cursor:
                self.onAllFinished()
                return False
        self.arbitTask = asyncio.create_task(self.arbit(
            id_,
            birthline = self.last_gpt_time + 1.0 / self.throttle_qps,
        ))
        return True

    async def arbit(self, id_: str, birthline: float) -> None:
        dt = birthline - time.time()
        if dt > 0.0:
            await asyncio.sleep(dt)
        self.last_gpt_time = time.time()
        result = await self.arbiter.judge(
            model=self.model_name, 
            prompt=self.prompt_and_examples.render(
                self.idToClassifiee(id_),
            ),
            max_tokens=1,
        )
        self.persistent.data[id_] = ItemAnnotations(
            gpt_verdict=result,
            status=ItemStatus.Classified(),
            human_label_no_or_yes=None,
        )
        self.cursor += 1
        self.cursor %= len(self.all_ids)
        self.arbitTask = None
        if self.is_paused:
            return
        self.arbitNext()
    
    def onAllFinished(self) -> None:
        ...
    
    def modifyThrottle(self, delta: float) -> None:
        self.throttle_qps *= math.exp(delta * .5)
    
    @on(Button.Pressed, '#throttle-down-btn')
    def action_throttle_down(self) -> None:
        self.modifyThrottle(-1.0)
    
    @on(Button.Pressed, '#throttle-up-btn')
    def action_throttle_up(self) -> None:
        self.modifyThrottle(+1.0)
    
    def action_throttle_toggle(self) -> None:
        self.throttle_active = not self.throttle_active
