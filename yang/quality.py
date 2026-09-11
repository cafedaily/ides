"""Explicit aliases and corpus-driven function-word filtering, with original evidence."""
import re
import unicodedata
from collections import Counter
from .text import FUNC, ENT_HEAD_BAN, sentences

DEFAULT_ALIASES = {"llm": "大模型", "llms": "大模型", "large language model": "大模型",
                   "large language models": "大模型", "大语言模型": "大模型"}


def aliases(settings=None):
    supplied = (settings or {}).get("aliases", {})
    if not isinstance(supplied, dict) or len(supplied) > 256:
        raise ValueError("aliases must be an object with at most 256 entries")
    mapping = dict(DEFAULT_ALIASES)
    for source, target in supplied.items():
        if not isinstance(source, str) or not isinstance(target, str) or not 2 <= len(source.strip()) <= 48 or not 2 <= len(target.strip()) <= 48:
            raise ValueError("Alias names and canonical terms must contain 2..48 characters")
        mapping[source.strip().casefold()] = target.strip().casefold()
    resolved = {}
    for source, target in mapping.items():
        seen = {source}
        while target in mapping and mapping[target] != target:
            if target in seen:
                raise ValueError("Alias cycle")
            seen.add(target)
            target = mapping[target]
        resolved[source] = target
    return resolved


class Normalizer:
    def __init__(self, settings=None):
        self.mapping = aliases(settings)
        pieces = []
        for term in sorted(self.mapping, key=lambda x: (-len(x), x)):
            escaped = re.escape(term)
            pieces.append(r"(?<![A-Za-z0-9])" + escaped + r"(?![A-Za-z0-9])" if term.isascii() else escaped)
        self.pattern = re.compile("|".join(pieces), re.IGNORECASE)

    def text(self, value):
        value = unicodedata.normalize("NFKC", value or "")
        value = self.pattern.sub(lambda match: self.mapping[match.group().casefold()], value)
        return re.sub(r"每一(?=[步次天周年月个篇])", "每", value)

    def document(self, doc):
        return {**doc, "pieces": [{**piece, "text": self.text(piece["text"])} for piece in doc["pieces"]]}

    def evidence(self, doc, term):
        needle = term.casefold()
        for piece in doc["pieces"]:
            for sentence in sentences(piece["text"]):
                if needle in self.text(sentence).casefold():
                    return {"dim": piece["dim"], "text": sentence}
        return {"dim": "", "text": ""}


def stopwords(raw, settings=None):
    settings = settings or {}
    manual = settings.get("stopwords", [])
    if not isinstance(manual, list) or len(manual) > 1000 or not all(isinstance(x, str) for x in manual):
        raise ValueError("stopwords must be a string list")
    result = set(manual)
    if settings.get("adaptive", True) and len(raw) >= 8:
        counts = Counter(term for tf, _dims in raw.values() for term in tf)
        for term, count in counts.items():
            if len(term) == 2 and count >= len(raw) * 0.6 and term[0] in FUNC | ENT_HEAD_BAN and term[1] in FUNC:
                result.add(term)
    return result
