# Drafted by GPT-5
from datetime import timedelta
from time import time

from textual.app import App, ComposeResult
from textual.widgets import Static
from textual.reactive import reactive

class Stopwatch(App):
    elapsed = reactive(timedelta())  # reactive state variable

    def compose(self) -> ComposeResult:
        yield Static("0.0s", id="display")

    def on_mount(self):
        self.start_time = time()
        self.set_interval(0.1, self.updateElapsed)  # update every 0.1s (~10 FPS)

    def updateElapsed(self):
        self.elapsed = timedelta(seconds=time() - self.start_time)

    def watch_elapsed(self, elapsed: timedelta):
        self.query_one("#display", Static).update(f"{elapsed.total_seconds():.1f}s")

if __name__ == "__main__":
    Stopwatch().run()
