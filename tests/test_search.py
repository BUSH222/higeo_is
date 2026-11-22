"""Word-start matching for the name search (issue #95)."""

import pytest

from helper.search import EXACT_WORD, NO_MATCH, WORD_PREFIX, match_rank, normalize_words


@pytest.mark.parametrize(
    ("text", "words"),
    [
        ("Спорово-пыльцевая лаборатория МГУ", ["спорово", "пыльцевая", "лаборатория", "мгу"]),
        ("Московский государственный университет (МГУ)", ["московский", "государственный", "университет", "мгу"]),
        ("Институт им. В.И. Вернадского", ["институт", "им", "в", "и", "вернадского"]),
        ("Ёлкин", ["елкин"]),
        ("Ludwig-Maximilians-Universität München", ["ludwig", "maximilians", "universität", "münchen"]),
        ("", []),
        ("   ,;()  ", []),
    ],
)
def test_text_is_split_into_lower_case_words(text, words):
    assert normalize_words(text) == words


@pytest.mark.parametrize(
    ("name", "query"),
    [
        ("Спорово-пыльцевая лаборатория МГУ", "Спорово-пыльцевая"),
        ("Спорово-пыльцевая лаборатория МГУ", "спорово пыльцевая"),  # the same query, typed without the hyphen
        ("Московский государственный университет (МГУ)", "мгу"),
        ("Комиссия по геологической изученности СССР (КОГИ)", "ког"),  # a prefix of the word
        ("Институт физики Земли (ИФЗ) РАН", "институт физик"),
        ("Ёлкин Пётр", "елк"),
        ("Отчёт за 1912 год", "1912"),
        ("Институт геохимии им. М.В. Ломоносова", "м.в."),
    ],
)
def test_the_query_may_begin_at_any_word(name, query):
    assert match_rank(name, query) != NO_MATCH


@pytest.mark.parametrize(
    ("name", "query"),
    [
        ("Московский университет", "оссковский"),  # the middle of a word
        ("Институт физики Земли", "физики институт"),  # the words are in the other order
        ("Московский университет", "университета"),  # longer than the stored word
        ("United States Geological Survey", "usgs"),  # that word is not in the name
        ("", "мгу"),
        ("Московский университет", ""),
        ("Московский университет", "   "),
    ],
)
def test_other_queries_do_not_match(name, query):
    assert match_rank(name, query) == NO_MATCH


def test_a_whole_word_ranks_before_a_word_prefix():
    assert match_rank("Институт физики Земли", "институт") == EXACT_WORD
    assert match_rank("Институт физики Земли", "институт физики") == EXACT_WORD
    assert match_rank("Институтский переулок", "институт") == WORD_PREFIX
