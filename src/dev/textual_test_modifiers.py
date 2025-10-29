'''
should have just used `textual keys`
'''
from typing import Type
from textual.app import App, ComposeResult
from textual.driver import Driver
from textual.widgets import Button, Footer, Static

class MyButton(Button):
    BINDINGS = [
        # ("enter", "enter", "Enter the button"),
        ("ctrl+enter", "control", "Control the button"),
        ("shift+enter", "shift", "Shift the button"),
        ("alt+enter", "alt", "Alt the button"),
    ]

    def action_enter(self) -> None:
        self.label = "Entered!"
    def action_control(self) -> None:
        self.label = "Controlled!"
    def action_shift(self) -> None:
        self.label = "Shifted!"
    def action_alt(self) -> None:
        self.label = "Alted!"

class App_0(App):
    def compose(self) -> ComposeResult:
        yield MyButton("btn", id="btn")
        yield Footer()

class App_1(App):
    BINDINGS = [
        # ("enter", "enter", "Enter the button"),
        # ("ctrl+enter", "control", "Control the button"),
        # ("shift+enter", "shift", "Shift the button"),
        # ("alt+enter", "alt", "Alt the button"),
        ("ctrl+e", "control", "Control the button"),
        ("shift+e", "shift", "Shift the button"),
        ("alt+e", "alt", "Alt the button"),
    ]

    def __init__(self, *a, **kw) -> None:
        super().__init__(*a, **kw)

        self.static = Static("Hi", id="label")

    def compose(self) -> ComposeResult:
        yield self.static
        yield Footer()
    
    def action_enter(self) -> None:
        self.static.update("Entered!")
    def action_control(self) -> None:
        self.static.update("Controlled!")
    def action_shift(self) -> None:
        self.static.update("Shifted!")
    def action_alt(self) -> None:
        self.static.update("Alted!")

if __name__ == "__main__":
    App_1().run()
