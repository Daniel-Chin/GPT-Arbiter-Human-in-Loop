import json
import typing as tp
from contextlib import contextmanager

from pydantic import BaseModel, ConfigDict

from .shared import ItemStatus

class ItemAnnotations(BaseModel):
    gpt_verdict: float
    status: ItemStatus.Base
    human_label_no_or_yes: int | None

    model_config = ConfigDict(
        frozen=True,
    )

class Persistent:
    def __init__(self, /, path: str) -> None:
        self.path = path
        self.data: dict[str, ItemAnnotations] = {}
    
    @contextmanager
    def Context(self) -> tp.Generator[dict[str, ItemAnnotations], None, None]:
        assert not self.data
        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                raw: dict = json.load(f)
            for k, v in raw.items():
                self.data[k] = ItemAnnotations.model_validate(v)
        except FileNotFoundError:
            pass
        try:
            yield self.data
        finally:
            with open(self.path, 'w', encoding='utf-8') as f:
                json.dump(
                    {k: v.model_dump() for k, v in self.data.items()},
                    f,
                    indent=2,
                )
