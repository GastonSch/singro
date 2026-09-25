from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator, Awaitable, Callable

LANGUAGE_NAMES = {
    "es": "Spanish",
    "en": "English",
    "pt": "Portuguese",
    "fr": "French",
    "de": "German",
    "it": "Italian",
}


def language_name(code: str) -> str:
    return LANGUAGE_NAMES.get(code.lower(), code)


@dataclass
class CaptionEvent:
    kind: str = "caption"  # caption | block | error
    lane: str = ""  # original | translation
    text: str = ""
    original: str = ""
    translation: str = ""
    final: bool = True
    source_language: str | None = None
    detail: str = ""


Emit = Callable[[CaptionEvent], Awaitable[None]]


class Engine(ABC):
    name = "base"

    def __init__(self, settings) -> None:  # noqa: ANN001
        self.settings = settings

    @abstractmethod
    async def run(
        self,
        audio: AsyncIterator[bytes],
        emit: Emit,
        *,
        session_id: str,
        source_language: str | None,
        target_language: str,
    ) -> None:
        ...

    async def aclose(self) -> None:
        return None


def glossary_lines(glossary: dict[str, str]) -> str:
    if not glossary:
        return ""
    lines = "\n".join(f'- "{src}" -> "{dst}"' for src, dst in glossary.items())
    return "\nGlossary (always use these exact renderings):\n" + lines


def interpreter_instruction(target_language: str, glossary: dict[str, str] | None = None) -> str:
    target = language_name(target_language)
    return (
        "You are the simultaneous interpretation engine of a live tech conference.\n"
        f"Translate every utterance into {target}.\n"
        "Rules:\n"
        f"- Output ONLY the {target} translation, with no preamble, labels or quotes.\n"
        "- Never answer questions, comment or summarize. Just interpret.\n"
        "- Keep technical terms and proper nouns accurate and natural.\n"
        f"- If the audio is already in {target}, repeat it verbatim.\n"
        "- Preserve the full meaning and sentence boundaries.\n"
        f"{glossary_lines(glossary or {})}"
    )
