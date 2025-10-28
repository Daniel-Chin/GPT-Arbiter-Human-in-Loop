import asyncio
import json
import typing as tp
import time
import math

from textual import on
from textual.reactive import reactive
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Grid
from textual.widgets import (
    Button, Footer, Header, Input, RadioButton, RadioSet, 
    Static, ContentSwitcher, 
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

    # throttle_active: reactive[bool] = reactive(True)
    # throttle_qps: reactive[float] = reactive(10.0)

    def __init__(
        self, 
        arbiter: ArbiterInterface,
        prompt_and_examples_filename: str,
        all_ids: tp.Sequence[str],
        idToClassifiee: tp.Callable[[str], Classifiee],
        rw_json_path: str,
        Lambda: float, 
        model_name: str = 'gpt-5-nano',
        initial_throttle_qps: float = 10.0, # queries per second
    ) -> None:
        '''
        `Lambda`: data diversity hyperparam.  
        Its inverse, `1 / Lambda`, equals the probability that 
        two independently drawn data points are significantly 
        related.  
        '''
        super().__init__()

        self.arbiter = arbiter
        self.prompt_and_examples_filename = prompt_and_examples_filename
        self.all_ids = all_ids
        self.idToClassifiee = idToClassifiee
        self.Lambda = Lambda
        self.model_name = model_name

        self.throttle_active = True
        self.throttle_qps = initial_throttle_qps
        self.querying_id: str | None = None
        self.gpt_reasons: tuple[str, str] | None = None

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

    def writePromptAndExamples(self) -> None:
        with open(self.prompt_and_examples_filename, 'w') as f:
            json.dump(
                self.prompt_and_examples.model_dump(),
                f,
                indent=2,
            )
    
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
        with ContentSwitcher(id="query-switcher", initial="query-empty"):
            yield Static('', id="query-empty")
            with Container(id="query-section"):
                yield Static("The GPT arbiter is entrusting you with the following decision!", id="greeter", classes='auto-width margin-h-1')
                yield Static("ID: ...", id="query-id", classes='auto-width margin-h-1')
                yield Static("", id="query-question", classes='auto-width margin-h-1')
                
                # GPT responses
                with Horizontal(id="gpt-inspection"):
                    with Container(id="gpt-responses", classes='auto-width margin-h-1'):
                        yield Static('GPT said "No" (1%).', classes='auto-width', id="gpt-no-response")
                        yield Static('GPT said "Yes" (99%).', classes='auto-width', id="gpt-yes-response")
                    with ContentSwitcher(id="gpt-why-switcher", initial="ask-why-btn"):
                        yield Button("Ask GPT\nwhy", id="ask-why-btn")
                        with Container(id="gpt-why-response", classes='auto-width margin-h-1'):
                            yield Static("...", id="gpt-why-no",  classes='auto-width')
                            yield Static("...", id="gpt-why-yes", classes='auto-width')
        
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
        self.myUpdate()
    
    def action_label_no(self) -> None:
        b = self.query_one('#no-radio', RadioButton)
        b.value = True
        self.myUpdate()

    def action_focus_explanation(self) -> None:
        e = self.query_one('#explanation-input', Input)
        e.focus()
    
    @on(Input.Submitted, '#explanation-input')
    def focus_submit(self) -> None:
        b = self.query_one('#submit-btn', Button)
        b.focus()

    @on(Button.Pressed, '#submit-btn')
    def action_submit(self) -> None:
        if self.querying_id is None:
            return
        yesNo: RadioSet = self.query_one('#yes-no', RadioSet)
        label = yesNo.pressed_index
        if label == -1:
            return
        explainInput: Input = self.query_one('#explanation-input', Input)
        explanation = explainInput.value.strip() or None
        old = self.persistent.data[self.querying_id]
        self.persistent.data[self.querying_id] = ItemAnnotations(
            gpt_verdict=old.gpt_verdict,
            status=ItemStatus.Classified(),
            human_label_no_or_yes=label,
        )
        self.prompt_and_examples = self.prompt_and_examples.addExample(
            QAPair(
                question = self.idToClassifiee(self.querying_id),
                no_or_yes = label,
                explanation = explanation,
            )
        )
        self.writePromptAndExamples()
        self.querying_id = None
        self.gpt_reasons = None
        bYes = self.query_one('#yes-radio', RadioButton)
        bNo  = self.query_one('#no-radio',  RadioButton)
        bYes.value = False
        bNo.value  = False
        explainInput.value = ''
        self.myUpdate()
        asyncio.create_task(asyncio.to_thread(self.nextQuery))
    
    def nextQuery(self) -> None:
        def score(id_: str) -> float:
            anno = self.persistent.data[id_]
            if anno.human_label_no_or_yes is not None:
                return -1.0
            match anno.status:
                case ItemStatus.Unvisited():
                    return -1.0
                case ItemStatus.Classified():
                    k = 0
                case ItemStatus.Outdated(value=k):
                    pass
                case _:
                    raise ValueError(f'Unknown ItemStatus: {anno.status}')
            p = anno.gpt_verdict
            H2 = -p * math.log2(p) - (1 - p) * math.log2(
                1 - p
            ) if 0.0 < p < 1.0 else 0.0
            return H2 * (1 - 1 / self.Lambda) ** k
        
        best_id = max(self.all_ids, key=score)
        if score(best_id) <= 0.0:
            time.sleep(1.0)
            return self.nextQuery()
        self.querying_id = best_id
    
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
        if self.query_one('#on-radio', RadioButton).value:
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
        self.myUpdate()
        if self.query_one('#off-radio', RadioButton).value:
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
    
    def on_mount(self) -> None:
        self.myUpdate()
    
    def myUpdate(self) -> None:
        yesNo: RadioSet = self.query_one('#yes-no', RadioSet)
        self.query_one('#submit-btn', Button).disabled = (
            yesNo.pressed_index == -1
        )
        switcherQuery: ContentSwitcher = self.query_one('#query-switcher', ContentSwitcher)
        switcherQuery.current = (
            'query-empty' if self.querying_id is None else 
            'query-section'
        )
        if self.querying_id is not None:
            sQueryID: Static = self.query_one('#query-id', Static)
            sQueryID.update(f'ID: {self.querying_id}')
            classifiee = self.idToClassifiee(self.querying_id)
            sQueryQuestion: Static = self.query_one('#query-question', Static)
            sQueryQuestion.update(self.prompt_and_examples.render(
                classifiee, omit_examples=True, 
            ))
            anno = self.persistent.data[self.querying_id]
            sNo:  Static = self.query_one('#gpt-no-response',  Static)
            sYes: Static = self.query_one('#gpt-yes-response', Static)
            sNo.update(
                f'GPT said "No" ({1 - anno.gpt_verdict:.1%}).'
            )
            sYes.update(
                f'GPT said "Yes" ({anno.gpt_verdict:.1%}).'
            )
        switcherWhy: ContentSwitcher = self.query_one('#gpt-why-switcher', ContentSwitcher)
        switcherWhy.current = (
            'ask-why-btn' if self.gpt_reasons is None else 
            'gpt-why-response'
        )
        if self.gpt_reasons is not None:
            sWhyNo:  Static = self.query_one('#gpt-why-no',  Static)
            sWhyYes: Static = self.query_one('#gpt-why-yes', Static)
            sWhyNo.update(self.gpt_reasons[0])
            sWhyYes.update(self.gpt_reasons[1])
        # todo: two graphs
        sCost: Static = self.query_one('#cost-display', Static)
        sCost.update(f'$ {self.arbiter.getRunningCost():.2f}')
