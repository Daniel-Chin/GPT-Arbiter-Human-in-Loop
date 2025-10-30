# from
# https://github.com/Textualize/textual/discussions/6197#discussioncomment-14826091

from textual.app import App, ComposeResult
from textual.widgets import Button, RadioButton, RadioSet

class ExampleApp(App):
    def compose(self) -> ComposeResult:
        yield RadioSet("Yes", "No")
        yield Button("Clear selection")

    def on_button_pressed(self) -> None:
        radioset = self.query_one(RadioSet)
        pressed_button = radioset.pressed_button
        if pressed_button is not None:
            with self.prevent(RadioButton.Changed):
                pressed_button.value = False
            radioset._pressed_button = None
            self.notify("Cleared selection")
        else:
            self.notify("No option selected", severity="warning")

if __name__ == "__main__":
    app = ExampleApp()
    app.run()
