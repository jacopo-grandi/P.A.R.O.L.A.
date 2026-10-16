"""Clean-layer data model: every clean sentence points back to the verbatim words it comes from.

Only the format is fixed here; producing clean transcripts is Phase 6.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from parola.schema.transcript import SCHEMA_VERSION, Transcript


class WordRef(BaseModel):
    segment: int = Field(ge=0)
    word: int = Field(ge=0)


class CleanSentence(BaseModel):
    text: str
    source: list[WordRef] = Field(min_length=1)


class CleanTranscript(BaseModel):
    schema_version: str = SCHEMA_VERSION
    verbatim_file: str
    sentences: list[CleanSentence] = Field(default_factory=list)

    def check_refs(self, verbatim: Transcript) -> list[str]:
        """Return a message for every reference that does not exist in ``verbatim``."""
        problems = []
        for i, sentence in enumerate(self.sentences):
            for ref in sentence.source:
                if ref.segment >= len(verbatim.segments) or ref.word >= len(
                    verbatim.segments[ref.segment].words
                ):
                    problems.append(f"sentence {i}: no word {ref.word} in segment {ref.segment}")
        return problems
