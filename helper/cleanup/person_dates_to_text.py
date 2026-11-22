"""Store the birth and death dates of people as text and move the dates written in comments into them (issue #94).

A date is now one of
    YYYY-MM-DD    full date
    YYYY-MM       month and year
    YYYY          year
    YYYY-YYYY     range of years (no month or day)

1. The DATETIME columns person.birth_date and person.death_date become text columns in the form of
   helper.dates: YYYY-MM-DD, YYYY-MM, YYYY or YYYY-YYYY.
2. "Дата рождения: …" / "Дата смерти: …" in a comment is moved into the empty date field when it is a certain
   date, a decade ("1910-е" -> 1910-1919) or a range of years, and removed from the comment. Approximate or
   bounded dates ("около 1930", "после 1925", "до 1916", "1904 ?", "{уточнить}") and either-or years
   ("1853 / 1855") stay in the comment and the field stays empty. When only the year is certain and more is
   said ("1915, лето"), the year goes in the field and the comment is kept.

The script reads and writes the tables with plain SQL, so it does not depend on the state of the ORM model.
Running it again changes nothing.

    uv run python -m helper.cleanup.person_dates_to_text [--dry-run]


!!!! REMOVE IN MAIN

"""

import argparse
import re
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import Engine, Text, inspect, text
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.types import Date, DateTime

DATE_COLUMNS = ("birth_date", "death_date")
FIELD_OF_KIND = {"рождения": "birth_date", "смерти": "death_date"}

MONTHS = {
    **dict.fromkeys(("january", "jan"), 1),
    **dict.fromkeys(("february", "feb"), 2),
    **dict.fromkeys(("march", "mar"), 3),
    **dict.fromkeys(("april", "apr"), 4),
    "may": 5,
    **dict.fromkeys(("june", "jun"), 6),
    **dict.fromkeys(("july", "jul"), 7),
    **dict.fromkeys(("august", "aug"), 8),
    **dict.fromkeys(("september", "sep", "sept"), 9),
    **dict.fromkeys(("october", "oct"), 10),
    **dict.fromkeys(("november", "nov"), 11),
    **dict.fromkeys(("december", "dec"), 12),
    **dict.fromkeys(("январь", "января", "янв"), 1),
    **dict.fromkeys(("февраль", "февраля", "фев"), 2),
    **dict.fromkeys(("март", "марта", "мар"), 3),
    **dict.fromkeys(("апрель", "апреля", "апр"), 4),
    **dict.fromkeys(("май", "мая"), 5),
    **dict.fromkeys(("июнь", "июня", "июн"), 6),
    **dict.fromkeys(("июль", "июля", "июл"), 7),
    **dict.fromkeys(("август", "августа", "авг"), 8),
    **dict.fromkeys(("сентябрь", "сентября", "сен", "сент"), 9),
    **dict.fromkeys(("октябрь", "октября", "окт"), 10),
    **dict.fromkeys(("ноябрь", "ноября", "ноя", "нояб"), 11),
    **dict.fromkeys(("декабрь", "декабря", "дек"), 12),
}

# "Дата рождения: <value>" up to the next such label, the end of the line, a tag or the end of the comment
FRAGMENT = re.compile(r"Дата (рождения|смерти)\s*:\s*(.*?)(?=Дата (?:рождения|смерти)\s*:|[\r\n<]|$)", re.S)
APPROXIMATE = re.compile(r"около|ок\.|после|\bдо\b|уточнить|\[|\?|/")


@dataclass
class Move:
    """What to do with one fragment: `value` for the field (None: leave it all), whether to drop the fragment."""

    value: str | None
    remove_fragment: bool
    reason: str


def _date(year: str, month: str | int, day: str | int | None = None) -> str | None:
    """YYYY-MM or YYYY-MM-DD, or None if there is no such day."""
    try:
        if day is None:
            date(int(year), int(month), 1)
            return f"{int(year):04d}-{int(month):02d}"
        return date(int(year), int(month), int(day)).isoformat()
    except ValueError:
        return None


def parse_fragment(value: str) -> Move:
    """Decide what the text after "Дата рождения:" becomes."""
    v = re.sub(r"\s+", " ", value).strip(" .,")
    v = re.sub(r"(?<=\d{4}) ?(г\.?|год)(?=[ ,.]|$)", "", v).strip(" .,")  # "1801 г.", "1788 год"
    head, _, tail = v.partition(",")
    head, tail = head.strip(" ."), tail.strip(" .")
    if not v or APPROXIMATE.search(head):
        return Move(None, False, "approximate, bounded, either-or or unknown")

    if m := re.fullmatch(r"(\d{3})0-е( года)?", v):  # decade
        return Move(f"{m[1]}0-{m[1]}9", True, "decade")
    if (m := re.fullmatch(r"(\d{4}) ?[-–] ?(\d{4})", v)) and int(m[1]) < int(m[2]):  # range
        return Move(f"{m[1]}-{m[2]}", True, "range")
    m = re.fullmatch(r"(\d{4})-(\d{1,2})(?:-(\d{1,2}))?-?", v)  # 1783-10, 1909-03-, 2003-3-12
    if m and (parsed := _date(m[1], m[2], m[3])):
        return Move(parsed, True, "numeric")
    m = re.fullmatch(r"(\d{4})\.(\d{1,2})\.(\d{1,2})", v)  # 1863.03.12
    if m and (parsed := _date(m[1], m[2], m[3])):
        return Move(parsed, True, "numeric year.month.day")
    m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", v)  # 12.03.1863
    if m and (parsed := _date(m[3], m[2], m[1])):
        return Move(parsed, True, "numeric day.month.year")
    m = re.fullmatch(r"(\d{1,2}) ([A-Za-zА-Яа-яЁё]+)\.? (\d{4})", v)  # 14 сентября 1863
    if m and (month := MONTHS.get(m[2].lower())) and (parsed := _date(m[3], month, m[1])):
        return Move(parsed, True, "day month year")
    m = re.fullmatch(r"([A-Za-zА-Яа-яЁё]+)\.? (\d{4})", v)  # сентябрь 1863
    if m and (month := MONTHS.get(m[1].lower())) and (parsed := _date(m[2], month)):
        return Move(parsed, True, "month year")
    m = re.fullmatch(r"(\d{4})[ ,.]+(\d{1,2}) ([A-Za-zА-Яа-яЁё]+)\.?", v)  # 1769,14 September
    if m and (month := MONTHS.get(m[3].lower())) and (parsed := _date(m[1], month, m[2])):
        return Move(parsed, True, "day month year")
    m = re.fullmatch(r"(\d{4})[ ,]+\(?([A-Za-zА-Яа-яЁё]+)\)?", v)  # 1980, ноябрь / 1824 (март)
    if m and (month := MONTHS.get(m[2].lower())) and (parsed := _date(m[1], month)):
        return Move(parsed, True, "month year")
    if re.fullmatch(r"\d{4}", v):
        return Move(v, True, "year")
    if re.fullmatch(r"\d{4}", head) and len(tail) <= 25:  # "1799, ?" / "1915, лето"
        if tail == "?":
            return Move(head, True, "year (rest unknown)")
        return Move(head, False, "year; the rest stays in the comment")
    return Move(None, False, "not recognised")


def _remove_fragment(comment: str, start: int, end: int) -> str | None:
    """The comment without comment[start:end]; None if only blanks and empty paragraphs or line breaks are left.

    Other tags count as content: a comment may be just an embedded photo.
    """
    rest = comment[:start] + comment[end:]
    return rest if re.sub(r"</?p\b[^>]*>|<br\s*/?>|&nbsp;|\s", "", rest, flags=re.IGNORECASE) else None


def plan_comment(comment: str | None, fields: dict[str, str | None]) -> tuple[dict, str | None, list[str]]:
    """The new field values, the new comment and a report line per fragment. `fields`: the current values."""
    new_fields, report = {}, []
    if not comment:
        return new_fields, comment, report
    new_comment = comment
    for match in reversed(list(FRAGMENT.finditer(comment))):  # from the end, so the offsets stay valid
        field = FIELD_OF_KIND[match[1]]
        move = parse_fragment(match[2])
        fragment = match[0].strip()
        if move.value is None:
            report.append(f"  left    {field}: {fragment!r} ({move.reason})")
            continue
        if fields.get(field) or field in new_fields:
            report.append(f"  CONFLICT {field} already set: {fragment!r} left in the comment")
            continue
        new_fields[field] = move.value
        if move.remove_fragment:
            new_comment = _remove_fragment(new_comment or "", match.start(), match.end())
        kept = "removed" if move.remove_fragment else "kept in the comment"
        report.append(f"  moved   {field} = {move.value}  <- {fragment!r} ({move.reason}; {kept})")
    return new_fields, new_comment, list(reversed(report))


def _as_text(value) -> str | None:
    """A stored DATETIME (datetime, or a string on SQLite) as YYYY-MM-DD."""
    if value is None:
        return None
    if isinstance(value, datetime | date):
        return value.strftime("%Y-%m-%d")
    return date.fromisoformat(str(value)[:10]).isoformat()


def date_columns_are_datetime(engine: Engine) -> bool:
    types = {column["name"]: column["type"] for column in inspect(engine).get_columns("person")}
    return any(isinstance(types[name], DateTime | Date) for name in DATE_COLUMNS)


def convert_columns(engine: Engine):
    """Turn the DATETIME date columns into text columns holding YYYY-MM-DD (add, copy, drop, rename)."""
    text_type = Text().with_variant(LONGTEXT(), "mysql").compile(dialect=engine.dialect)
    with engine.begin() as conn:
        rows = conn.execute(text("SELECT id, birth_date, death_date FROM person")).all()
        for column in DATE_COLUMNS:
            conn.execute(text(f"ALTER TABLE person ADD COLUMN {column}_text {text_type}"))
            values = [{"id": row.id, "value": _as_text(getattr(row, column))} for row in rows]
            if values:
                conn.execute(text(f"UPDATE person SET {column}_text = :value WHERE id = :id"), values)
            conn.execute(text(f"ALTER TABLE person DROP COLUMN {column}"))
            conn.execute(text(f"ALTER TABLE person RENAME COLUMN {column}_text TO {column}"))


def migrate(engine: Engine, dry_run: bool = False) -> list[str]:
    """Convert the columns (unless done already) and move the comment dates; return the report."""
    report = []
    needs_conversion = date_columns_are_datetime(engine)
    report.append("date columns: DATETIME -> text" if needs_conversion else "date columns: already text")
    if needs_conversion and not dry_run:
        convert_columns(engine)

    with engine.begin() as conn:
        rows = conn.execute(text("SELECT id, surname, birth_date, death_date, comment FROM person ORDER BY id")).all()
        moved = left = 0
        for row in rows:
            fields = {name: _as_text(getattr(row, name)) for name in DATE_COLUMNS}
            new_fields, new_comment, lines = plan_comment(row.comment, fields)
            if lines:
                report.append(f"{row.id} {row.surname.strip()}:")
                report.extend(lines)
            moved += len(new_fields)
            left += sum(1 for line in lines if not line.startswith("  moved"))
            if new_fields and not dry_run:
                assignments = ", ".join(f"{name} = :{name}" for name in new_fields)
                conn.execute(
                    text(f"UPDATE person SET {assignments}, comment = :comment WHERE id = :id"),
                    {**new_fields, "comment": new_comment, "id": row.id},
                )
        reversed_dates = [
            f"{row.id} {row.surname.strip()}: {_as_text(row.birth_date)} > {_as_text(row.death_date)}"
            for row in rows
            if row.birth_date and row.death_date and _as_text(row.death_date)[:4] < _as_text(row.birth_date)[:4]
        ]
    report.append(f"moved into the fields: {moved}; left in the comments: {left}")
    if reversed_dates:
        report.append("to check, death before birth (not changed): " + "; ".join(reversed_dates))
    return report


def main():
    from helper.db.initialise_database import engine  # here, so that the tests can pass their own engine

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="Show what would change without changing anything.")
    args = parser.parse_args()
    print("\n".join(migrate(engine, dry_run=args.dry_run)))
    if args.dry_run:
        print("Dry run: nothing changed.")


if __name__ == "__main__":
    main()
