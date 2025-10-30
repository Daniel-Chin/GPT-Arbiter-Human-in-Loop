import asyncio
import functools
import typing as tp
import time
import math
import threading
import subprocess
import shutil

from textual import on
from textual.pilot import Pilot
from textual.reactive import reactive
from textual.app import App, ComposeResult, ScreenStackError
from textual.binding import Binding
from textual.containers import Container, Horizontal, Grid, VerticalScroll
from textual.widgets import (
    Button, Footer, Header, Input, RadioButton, RadioSet, 
    Static, ContentSwitcher, Link, TabbedContent, TabPane,
)
import webbrowser

from .shared import PromptAndExamples, Classifiee, titled, ItemStatus, QAPair
from .stacked_bar_ascii import StackedBar
from .histogram_ascii import Histogram
from .arbiter_interface import ArbiterInterface
from .persistent import Persistent, ItemAnnotations

class LinkPrivate(Link):
    def action_open_link(self) -> None:
        if self.url:
            firefox_path = shutil.which('firefox')
            if firefox_path:
                subprocess.Popen([
                    firefox_path, '--private-window', self.url, 
                ])
            else:
                webbrowser.open(self.url)

class UI(App):
    CSS_PATH = "styles.tcss"
    BINDINGS = [
        Binding("y", "label_yes", "/"),
        Binding("n", "label_no", "."),
        Binding("e", "focus_explanation", "Explain."),
        Binding("ctrl+s", "submit", "Submit."),
        Binding("w", "ask_why", "Why?"),
        Binding("p", "toggle_pause", "(Un)Pause."),
        Binding("-", "throttle_down", "/"),
        Binding("+", "throttle_up", "Throttle."),
        Binding("t", "throttle_toggle", "Toggle Throttle."),
    ]

    throttle_active: reactive[bool] = reactive(True)
    throttle_qps: reactive[float] = reactive(10.0)

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
        interrogate_question: str = 'Explain briefly (1 - 3 sentences, usually 1 short sentence) why you made that decision.',
        interrogate_max_tokens: int = 60,
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
        self.interrogate_question = interrogate_question
        self.interrogate_max_tokens = interrogate_max_tokens

        self.throttle_active = True
        self.throttle_qps = initial_throttle_qps
        self.querying_id: str | None = None
        self.gpt_reasons: list[str] | None = None

        self.persistent = Persistent(rw_json_path)
        self.Context = self.persistent.Context
        self.cursor = 0
        self.last_gpt_time = 0.0
        self.arbitTask: asyncio.Task | None = None
        self.selectQueryTask: asyncio.Task | None = None
        self.selectQueryBarrier = threading.Lock()
        self.selectQueryBarrier.acquire()

        self.prompt_and_examples = PromptAndExamples.fromFile(
            prompt_and_examples_filename
        )

        self.title = "GPT Arbiter Human-in-Loop"
    
    def run(
        self, *, headless: bool = False, inline: bool = False, 
        inline_no_clear: bool = False, mouse: bool = True, 
        size: tuple[int, int] | None = None, 
        auto_pilot: tp.Callable[
            [Pilot[object]], tp.Coroutine[tp.Any, tp.Any, None]
        ] | None = None, loop: asyncio.AbstractEventLoop | None = None, 
    ) -> tp.Any | None:
        with self.Context():
            return super().run(
                headless=headless, inline=inline, 
                inline_no_clear=inline_no_clear, mouse=mouse, 
                size=size, auto_pilot=auto_pilot, loop=loop, 
            )

    def compose(self) -> ComposeResult:
        # Header
        yield Header(show_clock=False)
        
        with Grid(id="upper-pane"):
            yield titled(Static("GPT-5-mini", id="model-name"), 'Model')
            with titled(Horizontal(id='throttle-pane'), 'Throttle'):
                with ContentSwitcher(id="throttle-controls", initial="throttle-active"):
                    with Horizontal(id="throttle-active"):
                        yield Button("-", id="throttle-down-btn")
                        yield Static("10 / sec"  , classes='padding-h-1 auto-width', id="throttle-display")
                        yield Button("+", id="throttle-up-btn")
                    yield Static("Inactive.", classes='padding-h-1 auto-width', id="throttle-inactive")
                yield Button("Engage", id="throttle-toggle-btn")
            with titled(Container(id='progress-box'), 'Progress', skip_bottom=False):
                yield StackedBar('-0123456789', id='stacked-bar')
            yield titled(Static("$ 0.01", id="cost-display"), 'Cost', skip_bottom=False)
            with titled(RadioSet(id='on-off'), 'GPT Switch', skip_bottom=False):
                yield RadioButton("Pause", id="off-radio", value=True)
                yield RadioButton("Judge", id="on-radio")
            yield titled(Histogram(
                ('No', 'Yes'), id="decisions-histogram",
            ), 'Decisions and Confidence', skip_bottom=False)
        
        # Query section
        with ContentSwitcher(id="query-switcher", initial="query-empty"):
            yield Static('', id="query-empty")
            with Container(id="query-section"):
                yield Static("The GPT arbiter is entrusting you with the following decision!", id="greeter", classes='auto-width margin-h-1')
                yield LinkPrivate("[url]", id="query-url", classes='auto-width margin-h-1')
                with TabbedContent(id="query-tabs", initial="tab-classifiee"):
                    with TabPane("Classifiee", id="tab-classifiee"):
                        with VerticalScroll(classes="query-text-scroller"):
                            yield Static("", id='query-text-classifiee', classes="query-text")
                    with TabPane("With prompt", id="tab-with-prompt"):
                        with VerticalScroll(classes="query-text-scroller"):
                            yield Static("", id='query-with-prompt', classes="query-text")
                    with TabPane("With examples", id="tab-with-examples"):
                        with VerticalScroll(classes="query-text-scroller"):
                            yield Static("", id='query-with-examples', classes="query-text")
                
                # GPT responses
                with Horizontal(id="gpt-inspection"):
                    with Container(id="gpt-responses", classes='auto-width'):
                        yield Static('GPT said "No" (1%).', classes='auto-width', id="gpt-no-response")
                        yield Static('GPT said "Yes" (99%).', classes='auto-width', id="gpt-yes-response")
                    with ContentSwitcher(id="gpt-why-switcher", initial="ask-why-btn"):
                        yield Button("Ask GPT\nwhy", id="ask-why-btn")
                        with Container(id="gpt-why-response", classes='auto-width margin-h-1'):
                            yield Static("who knows", id="gpt-why-no",  classes='auto-width')
                            yield Static("who knows", id="gpt-why-yes", classes='auto-width')
        
                # Human input section
                with titled(Grid(id="human-input"), 'What do you think?', skip_bottom=False):
                    yield Button("Submit", id="submit-btn")
                    with RadioSet(id='yes-no'):
                        yield RadioButton("No", id="no-radio")
                        yield RadioButton("", id="undecided-radio", value=True)
                        yield RadioButton("Yes", id="yes-radio")
                    yield Input(placeholder="(Optional) Explain...", id="explanation-input")

        yield Footer(compact=True)
    
    def action_label_yes(self) -> None:
        b = self.query_one('#yes-radio', RadioButton)
        b.value = True
        self.onYesNoChanged()
    
    def action_label_no(self) -> None:
        b = self.query_one('#no-radio', RadioButton)
        b.value = True
        self.onYesNoChanged()
    
    @on(RadioSet.Changed, '#yes-no')
    def onYesNoChanged(self) -> None:
        yesNo: RadioSet = self.query_one('#yes-no', RadioSet)
        pressed_index = yesNo.pressed_index
        bSubmit: Button = self.query_one('#submit-btn', Button)
        bSubmit.disabled = (
            pressed_index == 1
        )
        bSubmit.focus()
        self.query_one('#explanation-input', Input).visible = (
            pressed_index != 1
        )
        for radioButton in yesNo._nodes:
            assert isinstance(radioButton, RadioButton)
            radioButton.styles.color = (
                '#0f0' if yesNo._pressed_button is radioButton 
                else 'white'
            )
            radioButton.notify_style_update()

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
        if label == 1:
            return
        label //= 2
        self.persistent.labelOne(self.querying_id, label)
        explainInput: Input = self.query_one('#explanation-input', Input)
        explanation = explainInput.value.strip() or None
        self.prompt_and_examples = self.prompt_and_examples.addExampleSyncingFile(
            QAPair(
                question = self.idToClassifiee(self.querying_id),
                no_or_yes = label,
                explanation = explanation,
            ),
        )

        self.querying_id = None
        self.gpt_reasons = None
        bUndecided = self.query_one('#undecided-radio', RadioButton)
        bUndecided.toggle()
        explainInput.value = ''
        self.myUpdate()
        self.maybeStartSelectQuery()
    
    def maybeStartSelectQuery(self) -> None:
        assert self.selectQueryTask is None
        assert self.querying_id is None
        self.selectQueryTask = asyncio.create_task(
            asyncio.to_thread(self.selectQuery), 
        )
        self.selectQueryBarrier.release()
    
    def selectQuery(self) -> None:
        self.selectQueryBarrier.acquire()
        try:
            def score(id_: str) -> float:
                anno = self.persistent.get(id_)
                if anno.human_label_no_or_yes is not None:
                    return -1.0
                match anno.status:
                    case ItemStatus.Unvisited():
                        return -1.0
                    case _:
                        k = anno.status.staleness
                p = anno.gpt_verdict
                assert p is not None
                H2 = -p * math.log2(p) - (1 - p) * math.log2(
                    1 - p
                ) if 0.0 < p < 1.0 else 0.0
                return H2 * (1 - 1 / self.Lambda) ** k
            
            best_id = max(self.all_ids, key=score)
            # self.log(f'{score(best_id) = }')
            if score(best_id) <= 0.0:
                return
            self.querying_id = best_id
            self.myUpdate()
        finally:
            self.selectQueryTask = None
    
    @on(Button.Pressed, '#ask-why-btn')
    async def action_ask_why(self) -> None:
        if self.querying_id is None:
            return
        if self.gpt_reasons is not None:
            return
        switcher: ContentSwitcher = self.query_one('#gpt-why-switcher', ContentSwitcher)
        switcher.current = 'gpt-why-response'
        sWhyNo:  Static = self.query_one('#gpt-why-no',  Static)
        sWhyYes: Static = self.query_one('#gpt-why-yes', Static)
        sWhyNo .update('')
        sWhyYes.update('')
        querying_id = self.querying_id
        statics = (sWhyNo, sWhyYes)
        def append(index_: int, chunk: str) -> None:
            if self.querying_id != querying_id:
                return
            if self.gpt_reasons is None:
                self.gpt_reasons = ['', '']
            self.gpt_reasons[index_] += chunk.replace('\n', ' ')
            statics[index_].update(self.gpt_reasons[index_])
        
        await self.arbiter.interrogate(
            model=self.model_name, 
            prompt=self.prompt_and_examples.render(
                self.idToClassifiee(querying_id),
            ),
            callbackNo =functools.partial(append, 0),
            callbackYes=functools.partial(append, 1),
            max_tokens=self.interrogate_max_tokens,
            question=self.interrogate_question,
        )
    
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
                self.myUpdate()
    
    def arbitNext(self) -> bool:
        assert self.arbitTask is None
        initial_cursor = self.cursor
        while True:
            id_ = self.all_ids[self.cursor]
            annotations = self.persistent.get(id_)
            if annotations.human_label_no_or_yes is not None:
                self.persistent.set(id_, ItemAnnotations(
                    gpt_verdict=float(annotations.human_label_no_or_yes),
                    status=ItemStatus.Classified(),
                    human_label_no_or_yes=annotations.human_label_no_or_yes,
                ))
            if annotations.status != ItemStatus.Classified():
                break
            self.cursor += 1
            self.cursor %= len(self.all_ids)
            if self.cursor == initial_cursor:
                self.onAllFinished()
                return False
        self.arbitTask = asyncio.create_task(self.arbit(
            id_,
            birthline = (
                self.last_gpt_time + 1.0 / self.throttle_qps
                if self.throttle_active else 0.0
            ),
        ))
        return True

    async def arbit(self, id_: str, birthline: float) -> None:
        try:
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
        except asyncio.CancelledError:
            return
        self.persistent.set(id_, ItemAnnotations(
            gpt_verdict=result,
            status=ItemStatus.Classified(),
            human_label_no_or_yes=None,
        ))
        self.cursor += 1
        self.cursor %= len(self.all_ids)
        self.arbitTask = None
        self.myUpdate()
        if self.query_one('#off-radio', RadioButton).value:
            return
        self.arbitNext()
        if self.selectQueryTask is None and self.querying_id is None:
            self.maybeStartSelectQuery()
    
    def onAllFinished(self) -> None:
        self.exit(message='All items have been classified.')
    
    def modifyThrottle(self, delta: float) -> None:
        self.throttle_qps *= math.exp(delta * .5)
    
    @on(Button.Pressed, '#throttle-down-btn')
    def action_throttle_down(self) -> None:
        self.modifyThrottle(-1.0)
    
    @on(Button.Pressed, '#throttle-up-btn')
    def action_throttle_up(self) -> None:
        self.modifyThrottle(+1.0)
    
    @on(Button.Pressed, '#throttle-toggle-btn')
    def action_throttle_toggle(self) -> None:
        self.throttle_active = not self.throttle_active
    
    def watch_throttle_active(self, _, __) -> None:
        self.updateThrottleDisplay()
    
    def watch_throttle_qps(self, _, __) -> None:
        self.updateThrottleDisplay()
    
    def updateThrottleDisplay(self) -> None:
        try:
            self.screen
        except ScreenStackError:
            return
        switcher: ContentSwitcher = self.query_one('#throttle-controls', ContentSwitcher)
        switcher.current = (
            'throttle-active' if self.throttle_active else 
            'throttle-inactive'
        )
        display: Static = self.query_one('#throttle-display', Static)
        text = (
            f'{round(self.throttle_qps)} / sec' if self.throttle_qps >= 1.0 else
            f'1 / {round(1 / self.throttle_qps)} sec'
        )
        display.update(text, layout=True)
        button: Button = self.query_one('#throttle-toggle-btn', Button)
        button.label = (
            'Disengage' if self.throttle_active else 
            'Engage'
        )
    
    def on_mount(self) -> None:
        self.maybeStartSelectQuery()
        self.updateThrottleDisplay()
        self.myUpdate()
        onOff: RadioSet = self.query_one('#on-off', RadioSet)
        onOff.focus()
    
    def myUpdate(self) -> None:
        self.onYesNoChanged()
        switcherQuery: ContentSwitcher = self.query_one('#query-switcher', ContentSwitcher)
        switcherQuery.current = (
            'query-empty' if self.querying_id is None else 
            'query-section'
        )
        if self.querying_id is not None:
            sQueryURL: Link = self.query_one('#query-url', Link)
            url = 'youtu.be/' + self.querying_id
            sQueryURL.update(url)
            sQueryURL.url = 'https://' + url
            classifiee = self.idToClassifiee(self.querying_id)

            sQueryTextClassifiee: Static = self.query_one(
                '#query-text-classifiee', Static, 
            )
            sQueryTextClassifiee.update(classifiee)
            sQueryWithPrompt: Static = self.query_one(
                '#query-with-prompt', Static, 
            )
            sQueryWithPrompt.update(
                self.prompt_and_examples.render(
                    classifiee, omit_examples=True, 
                )
            )
            sQueryWithExamples: Static = self.query_one(
                '#query-with-examples', Static, 
            )
            sQueryWithExamples.update(
                self.prompt_and_examples.render(
                    classifiee, omit_examples=False, 
                )
            )

            anno = self.persistent.get(self.querying_id)
            assert anno.gpt_verdict is not None
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
        sCost: Static = self.query_one('#cost-display', Static)
        sCost.update(f'$ {self.arbiter.getRunningCost():.2f}')
        stackedBar: StackedBar = self.query_one('#stacked-bar', StackedBar)
        stackedBar.data = ''.join(
            self.persistent.get(id_).status.getSymbol()
            for id_ in self.all_ids
        )
        stackedBar.data_cursor = self.cursor
        histogram: Histogram = self.query_one('#decisions-histogram', Histogram)
        new_data = []
        for id_ in self.all_ids:
            anno = self.persistent.get(id_)
            if anno.status == ItemStatus.Unvisited():
                continue
            if anno.human_label_no_or_yes is not None:
                continue
            p = anno.gpt_verdict
            assert p is not None
            new_data.append(p)
        histogram.data = new_data
        cProgressBox: Container = self.query_one('#progress-box', Container)
        total = len(self.all_ids)
        classified = sum(
            1 for id_ in self.all_ids
            if self.persistent.get(id_).status == ItemStatus.Classified()
        )
        cProgressBox.border_subtitle = f'{classified} / {total}'
    
    def exit(self, result=None, return_code=None, message=None) -> None:
        if self.arbitTask is not None:
            self.arbitTask.cancel()
        return super().exit(result, return_code, message)
