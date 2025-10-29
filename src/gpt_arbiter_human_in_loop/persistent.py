from __future__ import annotations

import json
import typing as tp
from contextlib import contextmanager

from pydantic import BaseModel, ConfigDict, field_serializer, field_validator

from .shared import ItemStatus

class ItemAnnotations(BaseModel):
    gpt_verdict: float | None
    status: ItemStatus.Base
    human_label_no_or_yes: int | None

    model_config = ConfigDict(
        frozen=True,
        arbitrary_types_allowed=True,
    )

    @field_serializer('status')
    def serialize_status(self, status: ItemStatus.Base) -> ItemStatus.Primitive:
        return status.serialize()

    @field_validator('status', mode='before')
    @classmethod
    def validate_status(cls, v: tp.Any) -> ItemStatus.Base:
        if isinstance(v, ItemStatus.Base):
            return v
        return ItemStatus.deserialize(v)

    @classmethod
    def Unvisited(cls) -> ItemAnnotations:
        return ItemAnnotations(
            gpt_verdict=None,
            status=ItemStatus.Unvisited(),
            human_label_no_or_yes=None,
        )

class Persistent:
    def __init__(self, /, path: str) -> None:
        self.path = path
        self.__data: dict[str, ItemAnnotations] = {}
    
    @contextmanager
    def Context(self) -> tp.Generator[dict[str, ItemAnnotations], None, None]:
        assert not self.__data
        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                raw: dict = json.load(f)
            for k, v in raw.items():
                self.__data[k] = ItemAnnotations.model_validate(v)
        except FileNotFoundError:
            pass
        try:
            yield self.__data
        finally:
            with open(self.path, 'w', encoding='utf-8') as f:
                json.dump(
                    {k: v.model_dump() for k, v in self.__data.items()},
                    f,
                    indent=2,
                )
    
    def get(self, id_: str) -> ItemAnnotations:
        return self.__data.get(id_, ItemAnnotations.Unvisited())
    
    def set(self, id_: str, ann: ItemAnnotations) -> None:
        self.__data[id_] = ann
