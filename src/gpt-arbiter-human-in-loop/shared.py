from __future__ import annotations

from pydantic import BaseModel, ConfigDict

NO_OR_YES = ('No', 'Yes')

Classifiee = str

class QAPair(BaseModel):
    question: Classifiee
    no_or_yes: int  # 0 for No, 1 for Yes
    explanation: str | None

    model_config = ConfigDict(
        frozen=True,
    )

class PromptAndExamples(BaseModel):
    prompt: str
    examples: list[QAPair]

    model_config = ConfigDict(
        frozen=True,
    )

    def addExample(self, example: QAPair) -> PromptAndExamples:
        return PromptAndExamples(
            prompt=self.prompt,
            examples=[*self.examples, example],
        )
