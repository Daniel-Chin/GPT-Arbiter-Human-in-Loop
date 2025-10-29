from __future__ import annotations
from dataclasses import dataclass
from abc import ABC, abstractmethod

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

    def render(
        self, classifiee: Classifiee, omit_examples: bool = False, 
    ) -> str:
        p = self.prompt.replace('{CLASSIFIEE}', classifiee)
        if not omit_examples:
            p = p.replace('{EXAMPLES}', '\n\n'.join(
                ex.render() for ex in self.examples
            ))
        return p
    
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

class ItemStatus:
    Primitive = tuple[str, dict]

    class Base(ABC):
        @abstractmethod
        def getSymbol(self) -> str:
            raise NotImplementedError()
        
        def serialize(self) -> ItemStatus.Primitive:
            raise NotImplementedError()
    
    @dataclass(frozen=True)
    class Unvisited(Base):
        def getSymbol(self) -> str:
            return '-'
        
        def serialize(self) -> ItemStatus.Primitive:
            return ('Unvisited', {})
    
    @dataclass(frozen=True)
    class Classified(Base):
        def getSymbol(self) -> str:
            return '0'

        def serialize(self) -> ItemStatus.Primitive:
            return ('Classified', {})
    
    @dataclass(frozen=True)
    class Outdated(Base):
        value: int
        def getSymbol(self) -> str:
            if self.value < 10:
                return str(self.value)
            return '+'
        
        def serialize(self) -> ItemStatus.Primitive:
            return ('Outdated', {'value': self.value})
    
    @classmethod
    def deserialize(cls, prim: ItemStatus.Primitive) -> ItemStatus.Base:
        tag, data = prim
        match tag:
            case 'Unvisited':
                return ItemStatus.Unvisited()
            case 'Classified':
                return ItemStatus.Classified()
            case 'Outdated':
                return ItemStatus.Outdated(**data)
            case _:
                raise ValueError(f'Unknown ItemStatus tag: {tag}')
