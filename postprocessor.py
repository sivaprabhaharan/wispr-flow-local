"""Text post-processing: filler word removal + auto-punctuation."""

from config import FILLER_WORDS

_TERMINAL_PUNCT = frozenset(".!?:;…")


def remove_fillers(text: str) -> str:
    """Remove filler words/phrases from transcript text.

    Multi-word fillers (e.g. "you know") are checked as bigrams before
    single-token filler removal.
    """
    tokens = text.split()
    result: list[str] = []
    i = 0
    while i < len(tokens):
        # Check bigram first
        if i + 1 < len(tokens):
            bigram = f"{tokens[i].lower()} {tokens[i + 1].lower()}"
            if bigram in FILLER_WORDS:
                i += 2
                continue
        if tokens[i].lower() in FILLER_WORDS:
            i += 1
            continue
        result.append(tokens[i])
        i += 1
    return " ".join(result)


def add_terminal_punctuation(text: str) -> str:
    """Append a period if the text doesn't end with terminal punctuation."""
    stripped = text.rstrip()
    if not stripped:
        return text
    if stripped[-1] not in _TERMINAL_PUNCT:
        return stripped + "."
    return stripped


class PostProcessor:
    """Sequential text cleanup pipeline."""

    def process(self, raw: str) -> str:
        return add_terminal_punctuation(remove_fillers(raw))
