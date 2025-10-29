import typing as tp

from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Sparkline, Static
from textual.containers import Container

class Histogram(Container):
    data: reactive[list[float]] = reactive([])
    axis_label: reactive[tuple[str, str]] = reactive(('', ''))
    
    def __init__(self, axis_label: tuple[str, str], *args, **kw) -> None:
        '''
        '''
        super().__init__(*args, **kw)

        self.sparkline = Sparkline()
        self.axisLabel = Static()

        self.axis_label = axis_label
    
    def compose(self) -> tp.Iterable[Widget]:
        yield self.sparkline
        yield self.axisLabel
    
    def watch_axis_label(self, _, new_axis_label: tuple[str, str]) -> None:
        W = self.size.width
        padding = W - len(new_axis_label[0]) - len(new_axis_label[1])
        self.axisLabel.update(
            new_axis_label[0] + ' ' * padding + new_axis_label[1], 
        )

    def watch_data(self, _, new_data: list[float]) -> None:
        if not new_data:
            self.sparkline.data = []
            return
        W = self.size.width
        if W == 0:  # during init
            return
        data_min = min(new_data)
        data_max = max(new_data)
        range_ = data_max - data_min
        bin_size = range_ / W
        sparkline_data = [0] * W
        for value in new_data:
            if range_ == 0:
                bin = W // 2
            else:
                bin = min(int((value - data_min) / bin_size), W - 1)
            sparkline_data[bin] += 1
        self.sparkline.data = sparkline_data
    
    def on_resize(self) -> None:
        self.watch_data(self.data, self.data)
        self.watch_axis_label(self.axis_label, self.axis_label)
