"""Word-start matching for the name search: the query may begin at any word of the name (issue #95).

Both sides are normalised the same way, so "Спорово-пыльцевая", "спорово пыльцевая" and "СПОРОВО-ПЫЛЬЦЕВАЯ"
are one query, and brackets, dots and hyphens are word boundaries: "мгу" finds "… университет (МГУ)".
"""

import re

SEPARATORS = re.compile(r"[\W_]+")  # everything that is not a letter or digit, in any script

EXACT_WORD = 0  # the query is a whole word of the name (or a run of whole words)
WORD_PREFIX = 1  # the query begins the word
NO_MATCH = 2


def normalize_words(text: str) -> list[str]:
    """Lower-case, treat ё as е, split on punctuation: "Спорово-пыльцевая (МГУ)" -> [спорово, пыльцевая, мгу]."""
    return [word for word in SEPARATORS.split(text.lower().replace("ё", "е")) if word]


def match_rank(name: str, query: str) -> int:
    """How the query matches the name: EXACT_WORD, WORD_PREFIX or NO_MATCH."""
    name_words, query_words = normalize_words(name), normalize_words(query)
    if not query_words or len(name_words) < len(query_words):
        return NO_MATCH
    best = NO_MATCH
    for start in range(len(name_words) - len(query_words) + 1):
        window = name_words[start : start + len(query_words)]
        if all(word.startswith(part) for word, part in zip(window, query_words, strict=True)):
            if all(word == part for word, part in zip(window, query_words, strict=True)):
                return EXACT_WORD
            best = WORD_PREFIX
    return best


def matches(name: str, query: str) -> bool:
    """Whether the query begins where a word of the name begins."""
    return match_rank(name, query) != NO_MATCH
