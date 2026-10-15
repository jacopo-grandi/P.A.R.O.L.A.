"""ASR systems compared in the baseline (docs/PLAN.md, Phase 2).

A system is a backend plus decoding choices: model, forced or detected language, initial
prompt. Variants of the PLAN: forced language vs automatic detection, with and without an
initial prompt rich in disfluencies.
"""

from __future__ import annotations

from dataclasses import dataclass

from ilat.asr import DEFAULT_MODEL, ASRBackend, MLXWhisperBackend
from ilat.asr.mlx_whisper_backend import SEED

LARGE_V3 = "mlx-community/whisper-large-v3-mlx"

# Whisper imitates the style of the prompt: these show fillers, repetitions and a false
# start, written as docs/conventions.md wants them.
DISFLUENCY_PROMPTS = {
    "it": "Ehm, allora, eh, cioè... sì, sì, il, il progetto, ehm, lo fa- lo facciamo, eh, domani.",
    "en": "Um, so, uh, I mean... yeah, yeah, the, the project, um, we'll ha- we'll do it, uh, "
    "tomorrow.",
}


@dataclass(frozen=True)
class System:
    name: str
    description: str
    model: str = DEFAULT_MODEL
    force_language: bool = False
    prompt: bool = False

    def backend(self, lang: str, seed: int = SEED) -> ASRBackend:
        prompt = DISFLUENCY_PROMPTS.get(lang) if self.prompt else None
        return MLXWhisperBackend(self.model, initial_prompt=prompt, seed=seed)

    def language(self, lang: str) -> str | None:
        """Language passed to the backend for a file whose manifest language is ``lang``."""
        return lang if self.force_language and lang in ("it", "en") else None


SYSTEMS = {
    s.name: s
    for s in [
        System("turbo", "large-v3-turbo, language detected"),
        System("turbo-lang", "large-v3-turbo, language forced", force_language=True),
        System("turbo-prompt", "large-v3-turbo, language detected, disfluency prompt",
               prompt=True),
        System("turbo-lang-prompt", "large-v3-turbo, language forced, disfluency prompt",
               force_language=True, prompt=True),
        System("large-v3-lang", "large-v3, language forced", model=LARGE_V3,
               force_language=True),
    ]
}  # fmt: skip
