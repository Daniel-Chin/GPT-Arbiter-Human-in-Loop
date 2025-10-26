import asyncio
import json
import typing as tp

from textual.app import App, ComposeResult
from textual.widgets import Footer, Header

from shared import PromptAndExamples, Classifiee, QAPair
from arbiter_interface import ArbiterInterface
from arbiter_gpt import ArbiterGPT
from arbiter_dummy import ArbiterDummy

class UI(App):
    BINDINGS = [
        ...,
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
        yield Header()
        yield Footer()

if __name__ == "__main__":
    app = UI(
        arbiter=ArbiterDummy(),
    )
    app.run()
