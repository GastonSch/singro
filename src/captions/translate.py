from __future__ import annotations

import functools
import logging

log = logging.getLogger(__name__)


class Translator:
    def translate(self, text: str, source: str, target: str) -> str:  # pragma: no cover
        raise NotImplementedError


class ArgosTranslator(Translator):
    """Offline neural MT via CTranslate2 (argostranslate), no torch required."""

    def __init__(self) -> None:
        import argostranslate.translate as argos

        self._argos = argos

    def translate(self, text: str, source: str, target: str) -> str:
        return self._argos.translate(text, source, target)


@functools.lru_cache(maxsize=1)
def get_translator() -> Translator | None:
    try:
        return ArgosTranslator()
    except Exception as exc:  # pragma: no cover - optional dependency
        log.warning("Traducción local no disponible (argostranslate): %s", exc)
        return None
