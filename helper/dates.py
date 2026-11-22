"""The birth and death dates as text: the one canonical form shared by the database, the form and the pages.

A date is stored and typed as one of

    YYYY         1863
    YYYY-MM      1863-03
    YYYY-MM-DD   1863-03-12
    YYYY-YYYY    1910-1919   a range of years

Anything else — an approximate date ("около 1930"), a bounded one ("до 1916") or two alternative years
("1853 / 1855") — is not a date: it stays in the comment (issue #94).
"""

import re
from datetime import date

# The person columns that hold a date; /new and /edit render them with the date input.
DATE_FIELDS = ("birth_date", "death_date")
# The forms the administrator may type; the same expression is the HTML pattern of the form field.
INPUT_PATTERN = r"\d{4}(-\d{2}-\d{2}|-\d{2}|-\d{4})?"
EXAMPLES = "1863-03-12, 1863-03, 1863, 1910-1919"


class InvalidDate(ValueError):
    """The text is not one of the accepted date forms."""


def _is_a_real_date(year: int, month: int = 1, day: int = 1) -> bool:
    try:
        date(year, month, day)
    except ValueError:
        return False
    return True


def parse_date_text(value: str) -> str:
    """The canonical form of a typed or stored date; raise InvalidDate for anything else."""
    text = value.strip().replace("–", "-").replace("—", "-")  # en and em dashes from pasted text
    match = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if match:
        year, month, day = (int(part) for part in match.groups())
        if not _is_a_real_date(year, month, day):
            raise InvalidDate(value)
        return f"{year:04d}-{month:02d}-{day:02d}"
    match = re.fullmatch(r"(\d{4})-(\d{1,2})", text)
    if match:
        year, month = (int(part) for part in match.groups())
        if not _is_a_real_date(year, month):
            raise InvalidDate(value)
        return f"{year:04d}-{month:02d}"
    match = re.fullmatch(r"(\d{4})-(\d{4})", text)
    if match:
        first, second = (int(part) for part in match.groups())
        if first >= second:
            raise InvalidDate(value)  # a range runs from the earlier year to the later one
        return f"{first:04d}-{second:04d}"
    if re.fullmatch(r"\d{4}", text) and _is_a_real_date(int(text)):
        return text
    raise InvalidDate(value)


def display_date_text(value: str | None) -> str | None:
    """The date as a reader sees it: "12.03.1863", "03.1863", "1863" or "1910–1919"."""
    if value is None or value == "":
        return value
    try:
        parse_date_text(value)
    except InvalidDate:
        return value  # not in our form (a date still stored the old way); show it as it is
    parts = value.split("-")
    if len(parts) == 3:
        return f"{parts[2]}.{parts[1]}.{parts[0]}"
    if len(parts) == 2 and len(parts[1]) == 4:
        return f"{parts[0]}–{parts[1]}"
    if len(parts) == 2:
        return f"{parts[1]}.{parts[0]}"
    return value
