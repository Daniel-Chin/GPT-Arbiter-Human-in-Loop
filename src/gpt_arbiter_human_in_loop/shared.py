from __future__ import annotations
from dataclasses import dataclass
from abc import ABC

from pydantic import BaseModel, ConfigDict
from textual.widget import Widget

NO_OR_YES = ('No', 'Yes')

Classifiee = str

class QAPair(BaseModel):
    question: Classifiee
    no_or_yes: int  # 0 for No, 1 for Yes
    explanation: str | None

    model_config = ConfigDict(
        frozen=True,
    )

    def render(self) -> str:
        s = f'''
Query:
{self.question}
Reference:
{NO_OR_YES[self.no_or_yes]}
'''.strip()
        if self.explanation is not None:
            s += f', because:\n{self.explanation}'
        return s

class PromptAndExamples(BaseModel):
    prompt: str
    examples: list[QAPair]

    model_config = ConfigDict(
        frozen=True,
    )

    def render(self, classifiee: Classifiee) -> str:
        return self.prompt.replace('{EXAMPLES}', '\n\n'.join(
            ex.render() for ex in self.examples
        )).replace('{CLASSIFIEE}', classifiee)
    
    def addExample(self, example: QAPair) -> PromptAndExamples:
        return PromptAndExamples(
            prompt=self.prompt,
            examples=[*self.examples, example],
        )

def titled(
    w: Widget, /, title: str, skip_bottom: bool = True,
    style = ('round', '#999'), padding = (0, 1),
):
    w.styles.border = style
    if skip_bottom:
        w.styles.border_bottom = None
    w.border_title = title
    w.styles.padding = padding
    return w

class ItemStatus(ABC):
    class Base(ABC):
        pass
    @dataclass(frozen=True)
    class Unvisited(Base):
        pass
    @dataclass(frozen=True)
    class Classified(Base):
        pass
    @dataclass(frozen=True)
    class Outdated(Base):
        value: int
