"""The one canonical form of the birth and death dates (issue #94)."""

import pytest

from helper.dates import InvalidDate, display_date_text, parse_date_text


@pytest.mark.parametrize(
    ("typed", "stored"),
    [
        ("1863", "1863"),
        (" 1863 ", "1863"),
        ("1863-03", "1863-03"),
        ("1863-3", "1863-03"),
        ("1863-03-12", "1863-03-12"),
        ("1863-3-1", "1863-03-01"),
        ("1910-1919", "1910-1919"),
        ("1910–1919", "1910-1919"),  # an en dash pasted from a word processor
    ],
)
def test_dates_are_stored_in_one_form(typed, stored):
    assert parse_date_text(typed) == stored


@pytest.mark.parametrize(
    "typed",
    [
        "",
        "вчера",
        "2000 и 2023",  # two years are not a range
        "2000, 2023",
        "2000/2023",
        "около 1930",
        "после 1925",
        "до 1916",
        "1853 / 1855",
        "1904 ?",
        "1910-е",  # a decade is written as a range by the migration, not by hand
        "1919-1910",  # a range runs from the earlier year to the later one
        "1863-13",  # no such month
        "1863-02-30",  # no such day
        "12.03.1863",  # the stored form is YYYY-MM-DD; 12.03.1863 is what the reader sees
    ],
)
def test_other_text_is_not_a_date(typed):
    with pytest.raises(InvalidDate):
        parse_date_text(typed)


@pytest.mark.parametrize(
    ("stored", "shown"),
    [
        ("1863-03-12", "12.03.1863"),
        ("1863-03", "03.1863"),
        ("1863", "1863"),
        ("1910-1919", "1910–1919"),
        (None, None),
        ("", ""),
    ],
)
def test_dates_are_shown_for_readers(stored, shown):
    assert display_date_text(stored) == shown


def test_a_date_still_stored_the_old_way_is_shown_as_it_is():
    """Before the migration the column holds a datetime; the page must not garble it."""
    assert display_date_text("1863-03-12 00:00:00") == "1863-03-12 00:00:00"
