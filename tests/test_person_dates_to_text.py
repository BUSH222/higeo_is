"""Moving the dates out of the comments and turning the date columns into text (issue #94)."""

import pytest
from sqlalchemy import create_engine, inspect, text

from helper.cleanup.person_dates_to_text import migrate, parse_fragment, plan_comment


@pytest.mark.parametrize(
    ("fragment", "stored"),
    [
        ("1863", "1863"),
        ("1863-3", "1863-03"),
        ("1863-03-12", "1863-03-12"),
        ("1863.03.12", "1863-03-12"),
        ("12.03.1863", "1863-03-12"),
        ("14 сентября 1863", "1863-09-14"),
        ("14 сентября 1863 г.", "1863-09-14"),
        ("сентябрь 1863", "1863-09"),
        ("1824 (март)", "1824-03"),
        ("1910-е", "1910-1919"),
        ("1910–1919", "1910-1919"),
    ],
)
def test_comment_dates_become_the_stored_form_and_are_removed(fragment, stored):
    move = parse_fragment(fragment)
    assert (move.value, move.remove_fragment) == (stored, True)


def test_a_certain_year_keeps_the_rest_of_the_comment():
    move = parse_fragment("1915, лето")
    assert (move.value, move.remove_fragment) == ("1915", False)


@pytest.mark.parametrize(
    "fragment",
    ["около 1930", "после 1925", "до 1916", "1853 / 1855", "1904 ?", "{уточнить}"],
)
def test_approximate_and_alternative_dates_stay_in_the_comment(fragment):
    move = parse_fragment(fragment)
    assert move.value is None and not move.remove_fragment


def test_the_date_label_and_date_are_taken_out_of_the_comment():
    fields, comment, _ = plan_comment("<p>Дата рождения: 12.03.1863</p>", {"birth_date": None})
    assert fields == {"birth_date": "1863-03-12"}
    assert comment is None  # nothing but the date was in the comment


def test_an_occupied_field_is_not_overwritten():
    fields, comment, report = plan_comment("Дата смерти: 1945", {"death_date": "1945-01-06"})
    assert fields == {}
    assert comment is not None and "Дата смерти: 1945" in comment
    assert any("CONFLICT" in line for line in report)


def test_migrate_converts_the_columns_and_moves_the_dates(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'dates.sqlite3'}")
    columns = "id INTEGER PRIMARY KEY, surname TEXT, birth_date DATETIME, death_date DATETIME, comment TEXT"
    with engine.begin() as conn:
        conn.execute(text(f"CREATE TABLE person ({columns})"))
        conn.execute(
            text(
                "INSERT INTO person VALUES "
                "(1, 'Вернадский', '1863-03-12 00:00:00', NULL, '<p>Дата смерти: 6 января 1945</p>')"
            )
        )
        conn.execute(text("INSERT INTO person VALUES (2, 'Ферсман', NULL, NULL, '<p>Дата рождения: около 1883</p>')"))

    report = migrate(engine)

    assert {column["name"] for column in inspect(engine).get_columns("person")} >= {"birth_date", "death_date"}
    with engine.begin() as conn:
        rows = conn.execute(text("SELECT id, birth_date, death_date, comment FROM person ORDER BY id")).all()
    assert rows[0].birth_date == "1863-03-12"
    assert rows[0].death_date == "1945-01-06"
    assert not rows[0].comment
    assert rows[1].birth_date is None
    assert "около 1883" in rows[1].comment
    assert any("left " in line for line in report)
    assert migrate(engine)[0] == "date columns: already text"  # running it again changes nothing
