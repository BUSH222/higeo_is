"""End-to-end tests of every route, meant to give the same results on SQLite, PostgreSQL and MySQL."""

import re

import pytest
from sqlalchemy.orm import Session

import main
from helper.db import initialise_database as db
from helper.login.passwords import check_password_hash, generate_password_hash
from tests.conftest import STAFF_EMAIL, STAFF_PASSWORD

SEEDED_PEOPLE = ["Ёлкин Пётр", "Вернадский Владимир Иванович", "Обручев Владимир Афанасьевич", "Ферсман Александр"]


def names(response):
    """The display names of a JSON search result."""
    return [row[2] for row in response.json()]


def saved_id(response):
    """The id of the object that /save redirects to."""
    assert response.status_code == 200, response.text
    return int(re.search(r"/view\?type=\w+&id=(\d+)", response.text).group(1))


# --- public pages ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "/",
        "/about",
        "/search",
        "/list?type=person",
        "/list?type=org",
        "/list?type=doc",
        "/list?type=field_of_study",
        "/list_custom?type=geography",
        "/list_custom?type=acad_full_members",
        "/list_custom?type=acad_professors",
        "/login",
        "/static/base.css",
    ],
)
def test_public_pages(client, url):
    assert client.get(url).status_code == 200


@pytest.mark.parametrize(
    "url",
    [
        "/view",
        "/view?type=person",
        "/view?type=person&id=abc",
        "/view?type=person&id=999999",
        "/view?type=bogus&id=1",
        "/list",
        "/list?type=bogus",
        "/list?type=person&sort=bogus",
        "/list_custom?type=bogus",
        "/search?type=bogus",
        "/set_language/de",
        "/nothing-here",
    ],
)
def test_not_found_is_an_html_page(client, url):
    response = client.get(url)
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("text/html")
    assert "404" in response.text


def test_person_documents_sorted_by_year(client, ids):
    page = client.get(f"/view?type=person&id={ids['Вернадский']}").text
    entries = ["1900 - Ящик", "1926 - Биосфера", "1940 - Яблоко", "Аннотация"]
    positions = [page.index(entry) for entry in entries]
    assert positions == sorted(positions)
    assert "- Аннотация" not in page


def test_view_pages(client, ids):
    person = client.get(f"/view?type=person&id={ids['Вернадский']}").text
    for expected in ["Вернадский Владимир Иванович", "12.03.1863", "Геологический институт", "Биосфера", "Геохимия"]:
        assert expected in person
    assert "Вернадский" in client.get(f"/view?type=org&id={ids['Геологический институт']}").text
    assert "Вернадский" in client.get(f"/view?type=org&id={ids['Московский университет']}").text  # alumni
    assert "Вернадский" in client.get(f"/view?type=doc&id={ids['Биосфера']}").text
    assert "Ферсман" in client.get(f"/view?type=field_of_study&id={ids['Геохимия']}").text
    geography = client.get("/view?type=geography&id=урал").text  # case-insensitive, Cyrillic
    assert all(surname in geography for surname in ["Вернадский", "Ферсман", "Обручев"])
    assert "Ёлкин" not in geography


def test_bibliography_paragraphs_are_not_nested_in_a_paragraph(client, ids):
    page = client.get(f"/view?type=person&id={ids['Вернадский']}").text
    assert re.search(r'<div class="[^"]*person-text[^"]*">\s*<p>Очерки геохимии\. 1927\.</p>\s*</div>', page)


def test_people_are_listed_in_code_point_order(client):
    page = client.get("/list?type=person").text
    positions = [page.index(name) for name in SEEDED_PEOPLE]
    assert positions == sorted(positions)


def test_geography_counts(client):
    page = client.get("/list_custom?type=geography").text
    assert "Урал - (3)" in page
    for place in ["Кольский полуостров", "Крым", "Сибирь"]:
        assert f"{place} - (1)" in page
    assert page.index("Урал - (3)") < page.index("Кольский полуостров - (1)") < page.index("Крым - (1)")
    assert "результат" not in page.split("</h6>", 1)[1]  # no word after the counts (the heading is separate)


@pytest.fixture
def overlapping_regions():
    """People whose regions overlap as text, removed again afterwards since the database is shared."""
    areas = ["США, Канада", "Юг США", "сша, Ёмкость", "Емкость, Канада, Канада"]
    with Session(db.engine) as session:
        people = [db.Person(surname=f"Регионов{i}", name="Тест", area_of_study=area) for i, area in enumerate(areas)]
        session.add_all(people)
        session.commit()
        yield
        for person in people:
            session.delete(person)
        session.commit()


def geography_counts(client):
    """{region: count} as the geography list shows them."""
    page = client.get("/list_custom?type=geography").text
    return {place: int(count) for place, count in re.findall(r">\s*([^<>]+?) - \((\d+)\)\s*<", page)}


def people_on_region_page(client, place):
    return len(re.findall(r'href="/view\?type=person&id=\d+"', client.get(f"/view?type=geography&id={place}").text))


def test_geography_matches_whole_entries(client, overlapping_regions):
    counts = geography_counts(client)
    # "Юг США" is not counted under "США"; case and ё are ignored; a place listed twice counts the person once
    assert (counts["США"], counts["Юг США"], counts["Ёмкость"], counts["Канада"]) == (2, 1, 2, 2)
    assert people_on_region_page(client, "США") == 2
    assert people_on_region_page(client, "юг сша") == 1


def test_geography_list_counts_match_region_pages(client, overlapping_regions):
    counts = geography_counts(client)
    assert counts
    for place, count in counts.items():
        assert people_on_region_page(client, place) == count, place


def test_academic_degree_list(client):
    page = client.get("/list_custom?type=acad_full_members").text
    assert "Вернадский" in page and "Ферсман" in page and "Обручев" not in page


# --- search ---------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("type=person&fullName=вЕРН", ["Вернадский Владимир Иванович"]),
        ("type=person&fullName=ёЛК", ["Ёлкин Пётр"]),
        ("type=person&fullName=ЕЛК", ["Ёлкин Пётр"]),
        ("type=person&fullName=Елкин Петр", ["Ёлкин Пётр"]),
        ("type=person&fullName=Ёлкин Пётр", ["Ёлкин Пётр"]),
        ("type=person&fullName=ВЕРНАДСКИЙ владимир", ["Вернадский Владимир Иванович"]),
        ("type=person&fullName=вернадский владимир ИВАНОВИЧ", ["Вернадский Владимир Иванович"]),
        ("type=person&fullName=никто", []),
        ("type=person&firstName=влад", ["Вернадский Владимир Иванович", "Обручев Владимир Афанасьевич"]),
        ("type=person&firstName=влад&lastName=ОБР", ["Обручев Владимир Афанасьевич"]),
        ("type=person&patronymic=евген", ["Ферсман Александр Евгеньевич"]),
        ("type=person&birthYear=1863", ["Вернадский Владимир Иванович", "Обручев Владимир Афанасьевич"]),
        ("type=person&birthYear=1863&lastName=в", ["Вернадский Владимир Иванович"]),
        ("type=person&content=ГЕОХИМИИ", ["Вернадский Владимир Иванович"]),
        ("type=org&name=геол", ["Геологический институт"]),
        ("type=org&name=универ", ["Московский университет"]),  # a word inside the name, not its first word
        ("type=org", ["Геологический институт", "Московский университет"]),
        ("type=doc&name=БИО", ["Биосфера"]),
        ("type=field_of_study&name=гео", ["Геохимия"]),
    ],
)
def test_search_json(client, query, expected):
    response = client.get(f"/search?{query}")
    assert response.status_code == 200
    assert names(response) == expected


def test_search_matches_abbreviations_and_hyphenated_words(staff):
    created = {}
    for name in ["Московский государственный университет (МГУ)", "Спорово-пыльцевая лаборатория"]:
        response = staff.post(
            "/save?type=org",
            data={"name": name, "org_type": "Научные учреждения", "csrf_token": staff.csrf_token},
        )
        created[name] = saved_id(response)
    try:
        found = names(staff.get("/search", params={"type": "org", "name": "мгу"}))
        assert found == ["Московский государственный университет (МГУ)"]
        for query in ("Спорово-пыльцевая", "спорово пыльцевая", "пыльцев"):
            found = names(staff.get("/search", params={"type": "org", "name": query}))
            assert found == ["Спорово-пыльцевая лаборатория"]
    finally:
        for org_id in created.values():
            deleted = staff.post(f"/delete?type=org&id={org_id}", data={"csrf_token": staff.csrf_token})
            assert deleted.status_code == 200


def test_whole_words_are_listed_before_word_prefixes(staff):
    created = []
    for name in ("Институт геологии", "Институтский переулок"):
        response = staff.post(
            "/save?type=org",
            data={"name": name, "org_type": "Научные учреждения", "csrf_token": staff.csrf_token},
        )
        created.append(saved_id(response))
    try:
        found = names(staff.get("/search", params={"type": "org", "name": "институт"}))
        assert found == ["Геологический институт", "Институт геологии", "Институтский переулок"]
    finally:
        for org_id in created:
            deleted = staff.post(f"/delete?type=org&id={org_id}", data={"csrf_token": staff.csrf_token})
            assert deleted.status_code == 200


def test_search_in_english_uses_the_english_names(client):
    response = client.get("/search?type=person&fullName=VERN&lang=en")
    assert names(response) == ["Vernadsky Vladimir Ivanovich"]


def test_quicksearch_renders_a_page(client):
    page = client.get("/search?type=person&quicksearch=quicksearch&fullName=ферс")
    assert page.headers["content-type"].startswith("text/html")
    assert "Ферсман Александр Евгеньевич" in page.text and "Вернадский" not in page.text
    assert client.get("/search?type=person&quicksearch=quicksearch").headers["location"] == "/search"


def test_bad_birth_year_is_not_a_server_error(client):
    assert client.get("/search?type=person&birthYear=abc").status_code == 404


def test_home_page_title_and_about_link(client):
    page = client.get("/?lang=ru").text
    assert "<title>Информационная система «История геологии и горного дела» - HIGEO IS</title>" in page
    assert '<a href="/about">Подробнее об Информационной системе</a>' in page
    page = client.get("/?lang=en").text
    assert "<title>The Information System ‘History of Geology and Mining’ - HIGEO IS</title>" in page
    assert '<a href="/about">More about the Information System</a>' in page


# --- language -------------------------------------------------------------------------------------------------


def test_language_is_remembered_in_the_session(client):
    assert "О системе" in client.get("/").text
    assert "About the system" in client.get("/?lang=en").text
    assert "About the system" in client.get("/").text  # remembered
    response = client.get("/set_language/ru", headers={"referer": "/about"})
    assert (response.status_code, response.headers["location"]) == (302, "/about")
    assert "О системе" in client.get("/").text
    assert '<html lang="ru">' in client.get("/").text


def test_english_view_uses_english_labels(client, ids):
    page = client.get(f"/view?type=person&id={ids['Вернадский']}&lang=en").text
    assert "Vernadsky Vladimir Ivanovich" in page and "Birth date" in page


# --- login ----------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "/new?type=person",
        "/edit?type=person&id=1",
        "/new?type=field_of_study",
    ],
)
def test_staff_pages_redirect_anonymous_visitors_to_login(client, url):
    response = client.get(url)
    assert response.status_code == 302
    assert response.headers["location"].startswith("/login?next=%2F")


@pytest.mark.parametrize("url", ["/delete?type=person&id=1", "/delete?type=field_of_study&id=1"])
def test_delete_redirects_anonymous_visitors_to_login(client, url):
    response = client.post(url)
    assert response.status_code == 302
    assert response.headers["location"].startswith("/login?next=%2F")


def test_save_needs_login(client):
    response = client.post("/save?type=person", data={"surname": "Хакер", "name": "Аноним"})
    assert response.status_code == 302 and response.headers["location"].startswith("/login")
    with Session(db.engine) as session:
        assert session.query(db.Person).filter_by(surname="Хакер").count() == 0


def test_login_and_logout(client, ids):
    view_url = f"/view?type=person&id={ids['Вернадский']}"
    assert "/edit?" not in client.get(view_url).text

    bad = client.post("/login", data={"email": STAFF_EMAIL, "password": "wrong password"})
    assert bad.status_code == 401 and "Неверный email или пароль." in bad.text
    assert client.post("/login", data={"email": "nobody@example.com", "password": "x"}).status_code == 401

    login_page = client.get("/login?next=/new?type=org").text
    assert 'action="/login?next=/new%3Ftype%3Dorg"' in login_page
    good = client.post(
        "/login?next=/new%3Ftype%3Dorg", data={"email": STAFF_EMAIL.upper(), "password": STAFF_PASSWORD}
    )
    assert (good.status_code, good.headers["location"]) == (303, "/new?type=org")
    assert "/edit?" in client.get(view_url).text
    assert client.get("/new?type=org").status_code == 200

    assert client.get("/logout").headers["location"] == "/"
    assert client.get("/new?type=org").status_code == 302


@pytest.mark.parametrize("target", ["https://evil.example/", "//evil.example/", "evil"])
def test_login_only_redirects_within_the_site(client, target):
    response = client.post(f"/login?next={target}", data={"email": STAFF_EMAIL, "password": STAFF_PASSWORD})
    assert response.headers["location"] == "/search"


def test_password_hashes():
    assert check_password_hash(generate_password_hash("пароль123"), "пароль123")
    assert not check_password_hash(generate_password_hash("пароль123"), "пароль124")
    assert not check_password_hash("not a hash", "anything")
    # Hashes made by Werkzeug, which the application used before, still verify.
    werkzeug_scrypt = (
        "scrypt:32768:8:1$kiHFzy460fE37QfB$a6c81b04e6ecb0424fef49f92075a268b2e0e4884896b8f260ab3fd53e758ca8"
        "93792a811a634fe64a7b81ede5ec94402255a9c85e17e2d83d4609bcac7f05cc"
    )
    werkzeug_pbkdf2 = (
        "pbkdf2:sha256:1000$9Ja9bfbRv9SV79sE$74c237d937cdcec5d6677ad52e51c0adc5732402c39617e7d844fc20f09931a2"
    )
    for password_hash in (werkzeug_scrypt, werkzeug_pbkdf2):
        assert check_password_hash(password_hash, "correct horse battery")
        assert not check_password_hash(password_hash, "incorrect horse battery")


# --- creating, editing and deleting ---------------------------------------------------------------------------


def test_person_lifecycle(staff, ids):
    assert staff.get("/new?type=person").status_code == 200
    created = staff.post(
        "/save?type=person",
        data={
            "surname": "Карпинский",
            "name": "Александр",
            "patronymic": "",
            "birth_date": "1847-01-07",
            "area_of_study": "Урал",
            "biography": "<p>Первый выборный президент Академии наук.</p>",
            "connection": [
                f"org:{ids['Геологический институт']}:org",
                f"org:{ids['Московский университет']}:education",
                f"doc:{ids['Биосфера']}:doc",
                f"field_of_study:{ids['Геохимия']}:field_of_study",
            ],
            "csrf_token": staff.csrf_token,
        },
    )
    person_id = saved_id(created)
    page = staff.get(f"/view?type=person&id={person_id}").text
    for expected in ["Карпинский Александр", "07.01.1847", "Геологический институт", "Московский университет"]:
        assert expected in page
    assert "Биосфера" in page and "Геохимия" in page
    assert "Карпинский" in staff.get(f"/view?type=org&id={ids['Московский университет']}").text
    assert names(staff.get("/search?type=person&birthYear=1847")) == ["Карпинский Александр"]

    edit_page = staff.get(f"/edit?type=person&id={person_id}").text
    assert "Карпинский" in edit_page and f'value="org:{ids["Московский университет"]}:education"' in edit_page

    edited = staff.post(
        "/save?type=person",
        data={
            "id": str(person_id),
            "surname": "Карпинский",
            "name": "Александр",
            "patronymic": "Петрович",
            "birth_date": "",
            "connection": [f"org:{ids['Геологический институт']}:org"],
            "csrf_token": staff.csrf_token,
        },
    )
    assert saved_id(edited) == person_id
    page = staff.get(f"/view?type=person&id={person_id}").text
    assert "Карпинский Александр Петрович" in page and "07.01.1847" not in page
    assert "Геологический институт" in page and "Московский университет" not in page and "Биосфера" not in page

    delete_data = {"csrf_token": staff.csrf_token}
    assert staff.post(f"/delete?type=person&id={person_id}", data=delete_data).status_code == 200
    assert staff.get(f"/view?type=person&id={person_id}").status_code == 404
    assert staff.post(f"/delete?type=person&id={person_id}", data=delete_data).status_code == 404


def test_partial_dates_and_ranges_are_accepted_and_shown(staff):
    partial = staff.post(
        "/save?type=person",
        data={"surname": "Страхов", "name": "Николай", "birth_date": "1860-3", "csrf_token": staff.csrf_token},
    )
    assert "03.1860" in staff.get(f"/view?type=person&id={saved_id(partial)}").text

    ranged = staff.post(
        "/save?type=person",
        data={"surname": "Павлов", "name": "Алексей", "birth_date": "1910–1919", "csrf_token": staff.csrf_token},
    )
    ranged_id = saved_id(ranged)
    assert "1910–1919" in staff.get(f"/view?type=person&id={ranged_id}").text
    assert names(staff.get("/search?type=person&birthYear=1910")) == ["Павлов Алексей"]
    with Session(db.engine) as session:
        person = session.get(db.Person, ranged_id)
        assert person is not None and person.birth_date == "1910-1919"  # stored with a plain hyphen

    for person_id in (saved_id(partial), ranged_id):  # the other tests count the seeded people
        deleted = staff.post(f"/delete?type=person&id={person_id}", data={"csrf_token": staff.csrf_token})
        assert deleted.status_code == 200


def test_the_date_field_shows_its_format(staff):
    page = staff.get("/new?type=person").text
    assert 'class="form-control date-input"' in page
    assert r'pattern="\d{4}(-\d{2}-\d{2}|-\d{2}|-\d{4})?"' in page
    assert "ГГГГ-ММ-ДД, ГГГГ-ММ, ГГГГ или ГГГГ-ГГГГ" in page  # the format, shown next to the field
    assert "1863-03-12" not in page  # no made-up example date in the form


def test_organization_with_members_and_alumni_can_be_deleted(staff, ids):
    created = staff.post(
        "/save?type=org",
        data={
            "name": "Горный институт",
            "org_type": "Высшие учебные заведения",
            "connection": [f"person:{ids['Обручев']}:alumni", f"person:{ids['Ферсман']}:person"],
            "csrf_token": staff.csrf_token,
        },
    )
    org_id = saved_id(created)
    page = staff.get(f"/view?type=org&id={org_id}").text
    assert "Обручев" in page and "Ферсман" in page
    assert "Горный институт" in staff.get(f"/view?type=person&id={ids['Обручев']}").text
    assert staff.get(f"/edit?type=org&id={org_id}").status_code == 200

    assert staff.post(f"/delete?type=org&id={org_id}", data={"csrf_token": staff.csrf_token}).status_code == 200
    assert staff.get(f"/view?type=org&id={org_id}").status_code == 404
    assert "Горный институт" not in staff.get(f"/view?type=person&id={ids['Обручев']}").text


def test_document_with_an_uploaded_file(staff, ids, tmp_path, monkeypatch):
    monkeypatch.setattr(main, "BASE_DIR", tmp_path)
    created = staff.post(
        "/save?type=doc",
        data={
            "name": "Геохимия России",
            "doc_type": "книга",
            "connection": [f"person:{ids['Ферсман']}:person"],
            "csrf_token": staff.csrf_token,
        },
        files={"file": ("../../evil name.pdf", b"%PDF-1.4 test", "application/pdf")},
    )
    doc_id = saved_id(created)
    with Session(db.engine) as session:
        stored = session.get(db.Document, doc_id).file
    assert stored.startswith("static/uploads/[") and stored.endswith("]evil name.pdf")
    assert (tmp_path / stored).read_bytes() == b"%PDF-1.4 test"
    assert [path.name for path in tmp_path.iterdir()] == ["static"]  # nothing escaped the upload folder
    assert "Ферсман" in staff.get(f"/view?type=doc&id={doc_id}").text

    # Saving again without choosing a file keeps the stored one.
    edited = staff.post(
        "/save?type=doc",
        data={
            "id": str(doc_id),
            "name": "Геохимия России",
            "doc_type": "книга",
            "year": "1922",
            "csrf_token": staff.csrf_token,
        },
        files={"file": ("", b"", "application/octet-stream")},
    )
    assert saved_id(edited) == doc_id
    with Session(db.engine) as session:
        document = session.get(db.Document, doc_id)
        assert (document.file, document.year) == (stored, "1922")

    assert staff.post(f"/delete?type=doc&id={doc_id}", data={"csrf_token": staff.csrf_token}).status_code == 200
    assert not (tmp_path / stored).exists()  # the deleted document's file is removed from disk


def test_replacing_an_uploaded_file_deletes_the_old_one(staff, ids, tmp_path, monkeypatch):
    monkeypatch.setattr(main, "BASE_DIR", tmp_path)
    created = staff.post(
        "/save?type=doc",
        data={"name": "Геохимия России", "doc_type": "книга", "csrf_token": staff.csrf_token},
        files={"file": ("first.pdf", b"first version", "application/pdf")},
    )
    doc_id = saved_id(created)
    with Session(db.engine) as session:
        first_path = session.get(db.Document, doc_id).file
    assert (tmp_path / first_path).exists()

    edited = staff.post(
        "/save?type=doc",
        data={"id": str(doc_id), "name": "Геохимия России", "doc_type": "книга", "csrf_token": staff.csrf_token},
        files={"file": ("second.pdf", b"second version", "application/pdf")},
    )
    assert saved_id(edited) == doc_id
    with Session(db.engine) as session:
        second_path = session.get(db.Document, doc_id).file
    assert second_path != first_path
    assert not (tmp_path / first_path).exists()  # the replaced file is removed from disk
    assert (tmp_path / second_path).read_bytes() == b"second version"


def test_save_rejects_bad_input(staff):
    assert staff.post("/save?type=bogus", data={"name": "x"}).status_code == 404
    assert (
        staff.post(
            "/save?type=person", data={"id": "999999", "surname": "x", "name": "y", "csrf_token": staff.csrf_token}
        ).status_code
        == 404
    )
    bad_date = staff.post(
        "/save?type=person",
        data={"surname": "x", "name": "y", "birth_date": "вчера", "csrf_token": staff.csrf_token},
    )
    assert bad_date.status_code == 422
    assert "неверный формат" in bad_date.text and "Дата рождения" in bad_date.text
    assert staff.get("/new").status_code == 501
    assert staff.get("/edit?type=person").status_code == 501
    assert staff.get("/edit?type=person&id=999999").status_code == 404


# --- person count ---------------------------------------------------------------------------------------------


def test_count_persons_is_cached_per_day(client, monkeypatch):
    monkeypatch.setattr(main, "_person_count_cache", None)
    count = client.get("/count_persons").json()["count"]
    assert count == len(SEEDED_PEOPLE)

    with Session(db.engine) as session:
        extra = db.Person(surname="Кэш", name="Тест")
        session.add(extra)
        session.commit()
        try:
            assert client.get("/count_persons").json()["count"] == count  # still cached
            monkeypatch.setattr(main, "_person_count_cache", (main.date.min, count))  # a day passes
            assert client.get("/count_persons").json()["count"] == count + 1
        finally:
            session.delete(extra)
            session.commit()


def test_about_shows_person_count(client, monkeypatch):
    monkeypatch.setattr(main, "_person_count_cache", None)
    assert f"В системе {len(SEEDED_PEOPLE)} персоналий" in client.get("/about?lang=ru").text
    assert "1700" not in client.get("/about?lang=en").text


def test_print_person_omits_biography_and_bibliography(client, ids):
    with Session(db.engine) as session:
        person = session.get(db.Person, ids["Ферсман"])
        person.biography = "СЕКРЕТНАЯ БИОГРАФИЯ"
        person.bibliography = "СЕКРЕТНАЯ БИБЛИОГРАФИЯ"
        person.comment = "Важный комментарий"
        session.commit()
    response = client.get(f"/print?type=person&id={ids['Ферсман']}")
    assert response.status_code == 200
    assert "Ферсман" in response.text
    assert "Важный комментарий" in response.text
    assert "СЕКРЕТНАЯ" not in response.text
    assert "bootstrap" not in response.text


@pytest.mark.parametrize(
    "url", ["/print", "/print?type=org&id=1", "/print?type=person&id=999999", "/print?type=person"]
)
def test_print_rejects_bad_requests(client, url):
    assert client.get(url).status_code == 404


def test_field_of_study_comment(staff, client, ids):
    field_id = ids["Геохимия"]
    url = f"/view?type=field_of_study&id={field_id}"
    assert "Комментарий" not in client.get(url).text
    form = {"id": str(field_id), "name": "Геохимия", "csrf_token": staff.csrf_token}
    saved = staff.post("/save?type=field_of_study", data={**form, "comment": "Заметка"})
    assert saved_id(saved) == field_id
    assert "Заметка" in client.get(url).text
    staff.post("/save?type=field_of_study", data={**form, "comment": ""})
    assert "Комментарий" not in client.get(url).text


NEW_LINKS = ["/new?type=person", "/new?type=org", "/new?type=doc", "/new?type=field_of_study"]


@pytest.mark.parametrize("url", ["/", "/about", "/search", "/list?type=person"])
def test_admin_menu_is_in_the_navbar_for_staff_only(staff, url):
    page = staff.get(url).text
    assert 'id="adminMenu"' in page and "Администрирование" in page
    for link in [*NEW_LINKS, "/logout"]:  # once each: in the menu, no longer also as buttons on the search page
        assert page.count(f'href="{link}"') == 1 and f'class="dropdown-item" href="{link}"' in page
    staff.cookies.clear()  # log out
    anonymous = staff.get(url).text
    assert 'id="adminMenu"' not in anonymous
    assert not any(link in anonymous for link in [*NEW_LINKS, "/logout"])


def test_field_of_study_save_needs_login(client):
    assert client.post("/save?type=field_of_study", data={"name": "X"}).status_code in (302, 303, 307)


def test_field_of_study_new_and_delete(staff, client, ids):
    form = staff.get("/new?type=field_of_study")
    assert form.status_code == 200 and 'name="name"' in form.text and 'name="comment"' in form.text
    assert "/new?type=field_of_study" in staff.get("/search").text
    field_id = saved_id(
        staff.post(
            "/save?type=field_of_study",
            data={"name": "Тестовая область", "comment": "temp", "csrf_token": staff.csrf_token},
        )
    )
    assert "Тестовая область" in client.get(f"/view?type=field_of_study&id={field_id}").text
    person_id = saved_id(
        staff.post(
            "/save?type=person",
            data={
                "surname": "Удаляемый",
                "name": "Тест",
                "connection": [f"field_of_study:{field_id}:field_of_study"],
                "csrf_token": staff.csrf_token,
            },
        )
    )
    assert "Тестовая область" in client.get(f"/view?type=person&id={person_id}").text
    delete_data = {"csrf_token": staff.csrf_token}
    assert staff.post(f"/delete?type=field_of_study&id={field_id}", data=delete_data).status_code == 200
    assert client.get(f"/view?type=field_of_study&id={field_id}").status_code == 404
    page = client.get(f"/view?type=person&id={person_id}")
    assert page.status_code == 200 and "Тестовая область" not in page.text
    assert staff.post(f"/delete?type=person&id={person_id}", data=delete_data).status_code == 200
