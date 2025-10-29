import typing as tp

from textual.reactive import reactive
from textual.app import RenderResult
from textual.widget import Widget

class StackedBar(Widget):
    data: reactive[tp.Sequence[str]] = reactive('')
    data_cursor: reactive[int] = reactive(0)

    def __init__(self, symbols: tp.Sequence[str], *args, **kw) -> None:
        '''
        `symbols` order matters: late-pooling.
        '''
        super().__init__(*args, **kw)

        self.symbols = tuple(symbols)
        for s in self.symbols:
            if len(s) != 1:
                print(f'Warning: StackedBar symbols should be single char. Ensure {s} is intended. (Markdown could mis-trigger this warning.)')
        
        self.data = ''
        self.data_cursor = 0
    
    def render(self) -> RenderResult:
        if self.data is None:
            return 'N/A'
        W, H = self.size
        S = W * H
        buf = []
        data_i = 0
        for bar_i in range(S):
            winner = -1
            is_cursor = False
            while data_i / len(self.data) < (bar_i + 1) / S:
                if data_i == self.data_cursor:
                    is_cursor = True
                datapoint = self.data[data_i]
                winner = max(winner, self.symbols.index(datapoint))
                data_i += 1
            if winner == -1:
                buf.append(' ')
            else:
                s = self.symbols[winner]
                if is_cursor:
                    s = f'[on white][black]{s}[/][/]'
                buf.append(s)
        return ''.join(buf)
