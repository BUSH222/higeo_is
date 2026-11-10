import os
import re
import shutil
import threading
from collections import Counter
from datetime import date, datetime
from http import HTTPStatus
from pathlib import Path
from typing import NoReturn

from dateutil.parser import parse
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import and_, extract, func, inspect, select
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from helper import CONNECTION_TYPE_MAPPING, FILE_FIELDS, MULTIPLE_CHOICE_FIELDS, SECRET_KEY, TITLE_CONVERTER_NEW_EDIT
from helper.cleanup.htmlcleaner import clean_html
from helper.db.initialise_database import (
    Document,
    DocumentAuthorship,
    FieldOfStudy,
    Organization,
    OrganizationMembership,
    Person,
    PersonEducation,
    PersonFieldOfStudy,
    byte_order,
    engine,
)
from helper.i18n import LANGUAGES, LocaleMiddleware, get_locale
from helper.i18n import gettext as _
from helper.login.auth import LoginRequired, require_login
from helper.login.login import router as login_router
from helper.templating import render

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = "static/uploads"  # relative to the project, and stored in the database in this form
MAX_CONTENT_LENGTH = 32 * 1024 * 1024

# The pages are HTML for people, so the generated API documentation is switched off.


def fold_text(value: str) -> str:
    """Lower-case a search string and treat ё as е, so "Елкин" finds "Ёлкин"."""
    return value.lower().replace("ё", "е")


def fold(column):
    """The SQL counterpart of fold_text, for comparing a column against a folded search string."""
    return func.replace(func.lower(column), "ё", "е")


app = FastAPI(title="HIGEO IS", docs_url=None, redoc_url=None, openapi_url=None)
# The middleware added last runs first: the session must be loaded before the locale is chosen.
app.add_middleware(LocaleMiddleware)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, same_site="lax", max_age=None)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.include_router(login_router)


@app.exception_handler(LoginRequired)
def redirect_to_login(request: Request, exc: LoginRequired):
    return RedirectResponse(exc.login_url, status_code=302)


@app.exception_handler(StarletteHTTPException)
def http_error(request: Request, exc: StarletteHTTPException):
    """Answer errors with a small HTML page rather than with JSON."""
    try:
        phrase = HTTPStatus(exc.status_code).phrase
    except ValueError:
        phrase = "Error"
    body = f"<!doctype html>\n<title>{exc.status_code} {phrase}</title>\n<h1>{exc.status_code} {phrase}</h1>\n"
    return HTMLResponse(body, status_code=exc.status_code, headers=exc.headers)


def abort(status_code: int) -> NoReturn:
    raise HTTPException(status_code)


def to_int(value) -> int:
    """Convert an id from the query string or a form, answering 404 if it is not a number."""
    try:
        return int(value)
    except TypeError, ValueError:
        abort(404)


@app.get("/set_language/{lang_code}")
def set_language(request: Request, lang_code: str):
    if lang_code not in LANGUAGES:
        abort(404)
    request.session["lang"] = lang_code
    return RedirectResponse(request.headers.get("referer") or "/", status_code=302)


@app.get("/")
def index(request: Request):
    """
    Renders the 'Index' page.

    This route handles the display of the 'Index' page, which provides an overview of the
    information system. The page includes a brief description of the system's purpose and
    its main functionalities.

    Returns:
    - Renders the 'index.html' template.
    """
    return render(request, "index.html")


_person_count_cache: tuple[date, int] | None = None
_person_count_lock = threading.Lock()


def get_person_count() -> int:
    """The number of persons, counted in the database at most once per day and kept in memory."""
    global _person_count_cache
    today = date.today()
    with _person_count_lock:
        if _person_count_cache is None or _person_count_cache[0] != today:
            with Session(engine) as session:
                _person_count_cache = (today, session.execute(select(func.count(Person.id))).scalar_one())
        return _person_count_cache[1]


@app.get("/count_persons")
def count_persons():
    """Returns the number of persons in the system as JSON, e.g. {"count": 1734}. Cached for a day."""
    return {"count": get_person_count()}


@app.get("/about")
def about(request: Request):
    """
    Renders the 'About' page.

    This route handles the display of the 'About' page, which provides information about the
    information system. The page includes details about the  system's purpose, instructions for searching,
    publications about the system, and information about the software development and content support.

    Returns:
    - Renders the 'about.html' template.
    """
    return render(request, "about.html", person_count=f"{get_person_count()}")


def enrich_person_data(data: dict) -> dict:
    """Render the photo as an <img> and derive birth/death dates from the comments when they are missing."""
    # Photo rendering: handle localized key
    photo_key = "Photo" if get_locale() == "en" else "Фотография"
    if photo_key in data:
        photo_src = data[photo_key]
        alt_text = _(photo_key)
        data[photo_key] = f'<img src="{photo_src}" alt="{alt_text}" />'
    # Insert derived birth date from comments if missing (comments text is Russian; regex remains RU)
    comments_key = "Comments" if get_locale() == "en" else "Комментарии"
    fio_key = "Full name" if get_locale() == "en" else "Фамилия Имя Отчество"
    birth_key = "Birth date" if get_locale() == "en" else "Дата рождения"
    birth_place_key = "Birth place" if get_locale() == "en" else "Место рождения"
    death_key = "Death date" if get_locale() == "en" else "Дата смерти"

    if birth_key not in data and comments_key in data and data[comments_key]:
        match = re.search(r"Дата рождения:\s*([^\.\n]+)", data[comments_key])
        if match:
            birth_value = "<i>" + match.group(1).strip() + "</i>"
            if fio_key in data:
                items = list(data.items())
                idx = next(i for i, (k, _) in enumerate(items) if k == fio_key)
                items.insert(idx + 1, (birth_key, birth_value))
                data = dict(items)
            else:
                items = [(birth_key, birth_value), *list(data.items())]
                data = dict(items)
    if death_key not in data and comments_key in data and data[comments_key]:
        match = re.search(r"Дата смерти:\s*([^\.\n]+)", data[comments_key])
        if match:
            death_value = "<i>" + match.group(1).strip() + "</i>"
            keys_priority = [birth_place_key, birth_key, fio_key]
            items = list(data.items())
            insert_idx = 0
            for key in keys_priority:
                try:
                    idx = next(i for i, (k, _) in enumerate(items) if k == key)
                    insert_idx = idx + 1
                    break
                except StopIteration:
                    continue
            items.insert(insert_idx, (death_key, death_value))
            data = dict(items)
    return data


@app.get("/view")
def view(request: Request):
    """
    Universal view for organization, person, and document.

    This route handles the display of detailed information for an organization, person, or document
    based on the query parameters provided in the request. It expects 'type' and 'id' parameters
    in the request arguments.

    Query Parameters:
    - type (str): The type of object to view ('org', 'person', 'doc').
    - id (int): The ID of the object to view.

    Returns:
    - Renders the 'view.html' template with the data and page context if the object is found.
    - Aborts with a 404 status code if the 'type' is not one of the expected values or if the 'id' is missing.
    """
    if request.query_params.get("type") not in [
        "org",
        "person",
        "doc",
        "field_of_study",
        "geography",
    ] or not request.query_params.get("id"):
        abort(404)

    if request.query_params.get("type") == "geography":
        place = request.query_params.get("id")
        stmt = (
            select(Person)
            .filter(fold(Person.area_of_study).contains(fold_text(place), autoescape=True))
            .order_by(Person.surname, Person.name)
        )
        with Session(engine) as session:
            people = session.execute(stmt).scalars().all()
        # Localize keys for geography view
        if get_locale() == "en":
            data = {
                "Geographic region": place,
                "Related researchers": [
                    [
                        "person",
                        person.id,
                        (
                            f"{person.surname_en or person.surname} "
                            f"{person.name_en or person.name} "
                            f"{person.patronymic_en or person.patronymic or ''}"
                        ),
                    ]
                    for person in people
                ],
            }
            parameters = {"single": [], "multiple": ["Related researchers"]}
        else:
            data = {
                "Географический регион": place,
                "Связанные исследователи": [
                    ["person", person.id, f"{person.surname} {person.name} {person.patronymic or ''}"]
                    for person in people
                ],
            }
            parameters = {"single": [], "multiple": ["Связанные исследователи"]}

        page = {
            "heading": _("Географический регион: %(place)s", place=place),
            "title": _("Geographic region: %(place)s", place=place),
            "id": place,
            "type": "geography",
        }

        return render(request, "view.html", data=data, page=page, parameters=parameters)

    viewtype_to_object = {"org": Organization, "person": Person, "doc": Document, "field_of_study": FieldOfStudy}
    # Localize which keys are considered single vs multiple for layout
    if get_locale() == "en":
        parameters = {
            "single": ["Biography", "Bibliography"],
            "multiple": ["Related persons", "Related researchers", "Alumni"],
        }
    else:
        parameters = {
            "single": ["Биография", "Библиография"],
            "multiple": ["Связанные персоналии", "Связанные исследователи", "Выпускники"],
        }
    viewtype = request.query_params.get("type")
    viewid = to_int(request.query_params.get("id"))
    obj = viewtype_to_object[viewtype]
    stmt = select(obj).where(obj.id == viewid)
    with Session(engine) as session:
        obj_instance = session.execute(stmt).scalar_one_or_none()
        if obj_instance is None:
            abort(404)
        # Use localized value dictionaries
        data = obj_instance.values_en() if get_locale() == "en" else obj_instance.values_ru()
    # Localized heading labels
    heading_map = {
        "org": _("Организация"),
        "person": _("Персоналия"),
        "doc": _("Документ"),
        "field_of_study": _("Область знаний"),
    }
    page = {
        "heading": heading_map[viewtype],
        "title": _("View %(name)s", name=obj.__name__.lower()),
        "id": viewid,
        "type": viewtype,
    }
    data = enrich_person_data(data)
    return render(request, "view.html", data=data, page=page, parameters=parameters)


@app.get("/print")
def print_person(request: Request):
    """Plain, unstyled printable version of a person page (no biography or bibliography)."""
    viewid = to_int(request.query_params.get("id"))
    if request.query_params.get("type") != "person" or not viewid:
        abort(404)
    with Session(engine) as session:
        person = session.execute(select(Person).where(Person.id == viewid)).scalar_one_or_none()
        if person is None:
            abort(404)
        data = person.values_en() if get_locale() == "en" else person.values_ru()
    skipped = ("Biography", "Bibliography") if get_locale() == "en" else ("Биография", "Библиография")
    for key in skipped:
        data.pop(key, None)
    data = enrich_person_data(data)
    photo_key = "Photo" if get_locale() == "en" else "Фотография"
    photo = data.pop(photo_key, None)
    return render(request, "print.html", data=data, photo=photo, title=_("Персоналия"))


@app.get("/search")
def search(request: Request):
    page = {"heading": _("Поиск"), "title": _("Search")}
    # Choose localized name columns for person searches
    use_en = str(get_locale()) == "en"
    first_col = Person.name_en if use_en else Person.name
    last_col = Person.surname_en if use_en else Person.surname
    patr_col = Person.patronymic_en if use_en else Person.patronymic
    if len(request.query_params) == 0 or not request.query_params.get("type"):
        return render(request, "search.html", page=page)

    # Quicksearch: /search?type=person&quicksearch=quicksearch&fullName=...
    if request.query_params.get("quicksearch") and request.query_params.get("type") == "person":
        query = request.query_params.get("fullName")
        where_stmt = []
        if query is None:
            return RedirectResponse("/search", status_code=302)
        else:
            parts = query.split()
            if len(parts) == 1:
                where_stmt.append(fold(last_col).startswith(fold_text(parts[0])))
            elif len(parts) == 2:
                where_stmt.append((fold(last_col) == fold_text(parts[0])) & (fold(first_col) == fold_text(parts[1])))
            elif len(parts) == 3:
                where_stmt.append(
                    (fold(last_col) == fold_text(parts[0]))
                    & (fold(first_col) == fold_text(parts[1]))
                    & (fold(patr_col) == fold_text(parts[2]))
                )

        final_where = and_(*where_stmt) if where_stmt else True
        stmt = (
            select(Person.id, last_col, first_col, patr_col)
            .where(final_where)
            .order_by(byte_order(last_col), byte_order(first_col))
        )

        results = []
        with Session(engine) as session:
            for row in session.execute(stmt):
                # row: (id, surname, name, patronymic)
                display = " ".join(filter(None, (row[1], row[2], row[3])))
                results.append(["person", row[0], display])
        return render(request, "search.html", page=page, results=results)

    # Content search (bibliography substring) — return compact JSON
    elif request.query_params.get("content"):
        content = request.query_params.get("content")
        stmt = (
            select(Person.id, Person.surname, Person.name, Person.patronymic)
            .where(fold(Person.bibliography).contains(fold_text(content), autoescape=True))
            .order_by(byte_order(Person.surname), byte_order(Person.name))
        )
        results = []
        with Session(engine) as session:
            for row in session.execute(stmt):
                display = " ".join(filter(None, (row[1], row[2], row[3])))
                results.append(["person", row[0], display])
        return results

    # Person attribute search — return compact JSON
    elif request.query_params.get("type") == "person":
        where_stmt = []
        if len(set(request.query_params.keys()).intersection({"firstName", "lastName", "patronymic"})) == 0:
            query = request.query_params.get("fullName")
            if query is not None:
                parts = query.split()
                if len(parts) == 1:
                    where_stmt.append(fold(last_col).startswith(fold_text(parts[0])))
                elif len(parts) == 2:
                    where_stmt.append(
                        (fold(last_col) == fold_text(parts[0])) & (fold(first_col) == fold_text(parts[1]))
                    )
                elif len(parts) == 3:
                    where_stmt.append(
                        (fold(last_col) == fold_text(parts[0]))
                        & (fold(first_col) == fold_text(parts[1]))
                        & (fold(patr_col) == fold_text(parts[2]))
                    )
        else:
            firstname = request.query_params.get("firstName")
            lastname = request.query_params.get("lastName")
            patronymic = request.query_params.get("patronymic")
            if firstname:
                where_stmt.append(fold(first_col).startswith(fold_text(firstname)))
            if lastname:
                where_stmt.append(fold(last_col).startswith(fold_text(lastname)))
            if patronymic:
                where_stmt.append(fold(patr_col).startswith(fold_text(patronymic)))

        year_query = request.query_params.get("birthYear")
        if year_query is not None:
            where_stmt.append(extract("year", Person.birth_date) == to_int(year_query))

        final_where = and_(*where_stmt) if where_stmt else True
        stmt = (
            select(Person.id, last_col, first_col, patr_col)
            .where(final_where)
            .order_by(byte_order(last_col), byte_order(first_col))
        )

        results = []
        with Session(engine) as session:
            for row in session.execute(stmt):
                display = " ".join(filter(None, (row[1], row[2], row[3])))
                results.append(["person", row[0], display])
        return results

    # Name-only search for org/doc/field_of_study — already compact (id, name)
    elif request.query_params.get("type") in ["org", "doc", "field_of_study"]:
        obj_type = request.query_params.get("type")
        obj = {"org": Organization, "doc": Document, "field_of_study": FieldOfStudy}[obj_type]
        query = request.query_params.get("name")
        if query:
            stmt = (
                select(obj.id, obj.name)
                .where(fold(obj.name).startswith(fold_text(query)))
                .order_by(byte_order(func.lower(obj.name)))
            )
        else:
            stmt = select(obj.id, obj.name).order_by(byte_order(func.lower(obj.name)))
        results = []
        with Session(engine) as session:
            for row in session.execute(stmt):
                results.append([obj_type, row[0], row[1]])
        return results

    else:
        abort(404)


@app.get("/list")
def list_view(request: Request):
    """
    Renders a list view for organizations, persons, documents, or fields of study.
    This route provides a list of all items of the specified type without pagination.
    It supports sorting to display results in a consistent order.
    Query Parameters:
    - type (str): The type of objects to list ('org', 'person', 'doc', 'field_of_study')
    - sort (str): Field to sort by (default depends on object type)
    Returns:
    - Renders the 'list.html' template with the results
    - Aborts with a 404 status code if the type parameter is invalid
    """
    if request.query_params.get("type") not in ["org", "person", "doc", "field_of_study"]:
        abort(404)

    obj_type = request.query_params.get("type")

    obj_map = {"org": Organization, "person": Person, "doc": Document, "field_of_study": FieldOfStudy}

    obj = obj_map[obj_type]

    heading_map = {
        "org": _("Организации"),
        "person": _("Персоналии"),
        "doc": _("Документы"),
        "field_of_study": _("Области исследования"),
    }

    # Determine default sort field based on object type
    if obj_type == "person":
        sort_field = request.query_params.get("sort", "surname")
        if sort_field == "surname":
            # Only select the necessary columns
            stmt = select(Person.id, Person.surname, Person.name, Person.patronymic).order_by(
                byte_order(Person.surname), byte_order(Person.name)
            )
        elif sort_field in Person.__table__.columns:
            stmt = select(Person.id, Person.surname, Person.name, Person.patronymic).order_by(
                getattr(Person, sort_field)
            )
        else:
            abort(404)
    else:
        sort_field = request.query_params.get("sort", "name")
        if sort_field not in obj.__table__.columns:
            abort(404)
        stmt = select(obj.id, obj.name).order_by(byte_order(func.lower(getattr(obj, sort_field))))

    results = []
    with Session(engine) as session:
        data = session.execute(stmt)
        for row in data:
            if obj_type == "person":
                # row: (id, surname, name, patronymic)
                person_str = " ".join(filter(None, (row[1], row[2], row[3])))
                results.append([obj_type, row[0], person_str])
            else:
                results.append([obj_type, row[0], row[1]])

    page_info = {"heading": heading_map[obj_type], "title": heading_map[obj_type], "type": obj_type}

    return render(request, "list.html", results=results, page=page_info, result_use_pagination=True)


@app.get("/list_custom")
def list_view_custom(request: Request):
    obj_type = request.query_params.get("type")
    if obj_type not in [
        "geography",
        "acad_full_members",  # действительный член
        "acad_foreign_members",  # иностранный член
        "acad_honorary_members",  # почётный член
        "acad_corresponding_members",  # член-корреспондент
        "acad_professors",  # профессор РАН
    ]:
        abort(404)

    if obj_type == "geography":
        # area_of_study holds a comma separated list of places: count how many people worked in each.
        stmt = select(Person.area_of_study).where(Person.area_of_study.is_not(None))
        with Session(engine) as session:
            places = Counter(
                place.strip() for areas in session.scalars(stmt) for place in areas.split(",") if place.strip()
            )
        most_common = sorted(places.items(), key=lambda item: (-item[1], item[0]))[:100]
        page_info = {
            "heading": _("Самые популярные географические регионы"),
            "title": _("Самые популярные географические регионы"),
        }
        results = [
            ["geography", place, _("%(place)s - %(count)s results", place=place, count=count)]
            for place, count in most_common
        ]
        use_pagination = False
    else:
        # DB filter labels (do not translate; must match stored values)
        degree_db_map = {
            "acad_full_members": "действительный член",
            "acad_foreign_members": "иностранный член",
            "acad_honorary_members": "почётный член",
            "acad_corresponding_members": "член-корреспондент",
            "acad_professors": "профессор РАН",
        }
        # UI labels (translate for display)
        degree_label_map = {
            "acad_full_members": _("действительный член"),
            "acad_foreign_members": _("иностранный член"),
            "acad_honorary_members": _("почётный член"),
            "acad_corresponding_members": _("член-корреспондент"),
            "acad_professors": _("профессор РАН"),
        }

        query = (
            select(Person)
            .filter(Person.academic_degree == degree_db_map[obj_type])
            .order_by(byte_order(Person.surname))
        )
        with Session(engine) as session:
            result = session.execute(query)
            results = [["person", person[0].id, str(person[0])] for person in result.fetchall()]
        degree_label = degree_label_map[obj_type]
        page_info = {
            "heading": _("Список академических степеней - %(degree)s", degree=degree_label),
            "title": _("Список академических степеней - %(degree)s", degree=degree_label),
        }
        use_pagination = True
    return render(request, "list.html", results=results, page=page_info, result_use_pagination=use_pagination)


@app.get("/new", dependencies=[Depends(require_login)])
def new(request: Request):
    """
    Renders the 'New' page for creating a new organization, person, or document.

    This route handles the display of the 'New' page, which allows users to create a new entry
    for an organization, person, document, or field of study based on the query parameters provided in the request.
    It expects a 'type' parameter in the request arguments.

    Query Parameters:
    - type (str): The type of object to create ('org', 'person', 'doc', 'field_of_study').

    Returns:
    - Renders the 'new.html' template with the necessary data for creating the specified object type.
    - Aborts with a 501 status code if the 'type' parameter is missing or invalid.
    """
    if len(request.query_params) != 1 or not request.query_params.get("type"):
        abort(501)
    obj_type = request.query_params.get("type")
    obj_dict = {"org": Organization, "person": Person, "doc": Document, "field_of_study": FieldOfStudy}
    if obj_type not in obj_dict:
        abort(404)
    page = {
        "heading": f"New {TITLE_CONVERTER_NEW_EDIT[obj_type]}",
        "title": f"New {TITLE_CONVERTER_NEW_EDIT[obj_type]}",
    }
    obj = obj_dict[obj_type]

    mapper = inspect(obj)
    data_fin = {}
    for column in mapper.attrs:
        if (
            column.key
            not in ["organizations", "documents", "members", "authors", "field_of_study", "education", "alumni"]
            and column.key != "id"
        ):
            data_fin[column.key] = ""
    data2 = {}
    if obj_type == "person":
        data2 = {"doc": [], "org": [], "field_of_study": [], "education": []}
    elif obj_type == "doc":
        data2 = {"person": []}
    elif obj_type == "org":
        data2 = {"person": [], "alumni": []}

    return render(
        request,
        "new.html",
        page=page,
        data1=data_fin,
        data2=data2,
        obj_type=obj_type,
        file=FILE_FIELDS,
        multiple_choice=MULTIPLE_CHOICE_FIELDS,
        connection_types=CONNECTION_TYPE_MAPPING,
    )


@app.get("/edit", dependencies=[Depends(require_login)])
def edit(request: Request):
    """
    Renders the 'Edit' page for editing an existing organization, person, or document.
    Admin only

    This route handles the display of the 'Edit' page, which allows users to edit an existing entry
    for an organization, person, or document based on the query parameters provided in the request.
    It expects 'type' and 'id' parameters in the request arguments.

    Query Parameters:
    - type (str): The type of object to edit ('org', 'person', 'doc').
    - id (int): The ID of the object to edit.

    Returns:
    - Renders the 'new.html' template with the necessary data for editing the specified object type.
    - Aborts with a 501 status code if the 'type' or 'id' parameter is missing or invalid.
    """
    page = {"heading": "Edit document", "title": "Edit document"}
    if len(request.query_params) != 2 or not request.query_params.get("type") or not request.query_params.get("id"):
        abort(501)
    obj_type = request.query_params.get("type")
    obj_id = to_int(request.query_params.get("id"))
    obj_dict = {"org": Organization, "person": Person, "doc": Document, "field_of_study": FieldOfStudy}
    if obj_type not in obj_dict:
        abort(404)
    page = {
        "heading": f"Edit {TITLE_CONVERTER_NEW_EDIT[obj_type]}",
        "title": f"Edit {TITLE_CONVERTER_NEW_EDIT[obj_type]}",
    }
    obj = obj_dict[obj_type]

    stmt = select(obj).where(obj.id == obj_id)
    with Session(engine) as session:
        data = session.execute(stmt).scalar_one_or_none()
        if data is None:
            abort(404)
        mapper = inspect(obj)
        data_fin = {}
        for column in mapper.attrs:
            if not isinstance(getattr(data, column.key), list):
                data_fin[column.key] = getattr(data, column.key)
    data_fin2 = {}
    for k, v in data_fin.items():
        if isinstance(v, list):
            continue
        elif v is None:
            data_fin2[k] = ""
        elif k.endswith("date"):
            data_fin2[k] = parse(str(v)).date()
        else:
            data_fin2[k] = str(v)

    data2 = {}
    with Session(engine) as session:
        obj_real = session.query(obj).filter(obj.id == obj_id).one_or_none()
        if obj_real is None:
            abort(404)
        if obj_type == "person":
            data2 = {"org": [], "doc": [], "field_of_study": [], "education": []}
            for doc_authorship in obj_real.documents:  # doc_authorship is DocumentAuthorship
                doc = doc_authorship.document
                data2["doc"].append({"type": "doc", "id": doc.id, "name": doc.name})
            for org_membership in obj_real.organizations:
                org = org_membership.organization
                data2["org"].append({"type": "org", "id": org.id, "name": org.name})
            for field_relationship in obj_real.field_of_study:
                field = field_relationship.field_of_study
                data2["field_of_study"].append({"type": "field_of_study", "id": field.id, "name": field.name})
            for person_education in obj_real.education:
                org = person_education.organization
                data2["education"].append({"type": "org", "id": org.id, "name": org.name})
        elif obj_type == "org":
            data2 = {"person": [], "alumni": []}
            for obj_person in obj_real.members:
                person = obj_person.person
                data2["person"].append({"type": "person", "id": person.id, "name": str(person)})
            for person_education in obj_real.alumni:
                person = person_education.person
                data2["alumni"].append({"type": "person", "id": person.id, "name": str(person)})
        elif obj_type == "doc":
            data2 = {"person": []}
            for obj_person in obj_real.authors:
                person = obj_person.person
                data2["person"].append({"type": "person", "id": person.id, "name": str(person)})

    return render(
        request,
        "new.html",
        page=page,
        data1=data_fin2,
        data2=data2,
        obj_type=obj_type,
        multiple_choice=MULTIPLE_CHOICE_FIELDS,
        file=FILE_FIELDS,
        connection_types=CONNECTION_TYPE_MAPPING,
    )


@app.post("/save", dependencies=[Depends(require_login)])
async def save(request: Request):
    """
    Saves a new or edited organization, person, or document.

    This route handles the saving of a new or edited entry for an organization, person, or document
    based on the form data provided in the request. It expects a 'type' parameter in the request arguments
    and form data in the request body.

    Query Parameters:
    - type (str): The type of object to save ('org', 'person', 'doc').

    Form Data:
    - Various fields corresponding to the attributes of the specified object type.
    - connection (list): A list of connections to other objects.

    Returns:
    - Renders the 'redirect.html' template to redirect to the search page after saving. [TO BE REMOVED]
    """
    obj_type = request.query_params.get("type")
    if obj_type not in ["org", "person", "doc", "field_of_study"]:
        abort(404)
    if int(request.headers.get("content-length") or 0) > MAX_CONTENT_LENGTH:
        abort(413)
    # Uploaded files are only readable while the form is open, so the saving happens inside this block.
    # It runs in a worker thread, because the database calls block.
    async with request.form(max_fields=100_000, max_part_size=MAX_CONTENT_LENGTH) as form:
        formdata, uploads = {}, {}
        for key, value in form.multi_items():
            if isinstance(value, UploadFile):
                if value.filename:  # a file input that was left empty is not an upload
                    uploads.setdefault(key, value)
            elif key != "connection" and key not in FILE_FIELDS:  # a file field is only ever set by an upload
                formdata.setdefault(key, value)
        connections = [value for value in form.getlist("connection") if isinstance(value, str)]
        obj_id = await run_in_threadpool(save_object, obj_type, formdata, uploads, connections)
    return render(request, "redirect.html", url=f"/view?type={obj_type}&id={obj_id}")


def save_object(obj_type: str, formdata: dict, uploads: dict[str, UploadFile], connections: list[str]) -> int:
    """Create or update an object and replace its connections. Returns the id of the object."""
    obj = {"org": Organization, "person": Person, "doc": Document, "field_of_study": FieldOfStudy}[obj_type]
    formdata = {key: (value if value not in ("", "None") else None) for key, value in formdata.items()}
    for key, value in formdata.items():
        if key.endswith("date") and value is not None:
            try:
                formdata[key] = datetime.strptime(value, "%Y-%m-%d")
            except ValueError:
                abort(400)
    os.makedirs(BASE_DIR / UPLOAD_DIR, exist_ok=True)
    for key, upload in uploads.items():
        # basename: the name comes from the browser and must not be able to point outside the upload folder
        upload_path = f"{UPLOAD_DIR}/[{datetime.now()!s}]{os.path.basename(upload.filename or '')}"
        with open(BASE_DIR / upload_path, "wb") as destination:
            shutil.copyfileobj(upload.file, destination)
        formdata[key] = upload_path
    if "bibliography" in formdata:
        formdata["bibliography"] = clean_html(formdata["bibliography"])
    if "biography" in formdata:
        formdata["biography"] = clean_html(formdata["biography"])
    if formdata.get("id"):
        obj_id = to_int(formdata.pop("id"))
        stmt = select(obj).where(obj.id == obj_id)
        with Session(engine) as session:
            data = session.execute(stmt).scalar_one_or_none()
            if data is None:
                abort(404)
            for key, value in formdata.items():
                setattr(data, key, value)
            session.commit()
    else:
        formdata.pop("id", None)
        data = obj(**formdata)
        with Session(engine) as session:
            session.add(data)
            session.commit()
            obj_id = data.id

    with Session(engine) as session:
        if obj_type == "person":
            session.query(DocumentAuthorship).filter(DocumentAuthorship.person_id == obj_id).delete()
            session.query(OrganizationMembership).filter(OrganizationMembership.person_id == obj_id).delete()
            session.query(PersonFieldOfStudy).filter(PersonFieldOfStudy.person_id == obj_id).delete()
            session.query(PersonEducation).filter(PersonEducation.person_id == obj_id).delete()
        elif obj_type == "org":
            session.query(OrganizationMembership).filter(OrganizationMembership.organization_id == obj_id).delete()
            session.query(PersonEducation).filter(PersonEducation.organization_id == obj_id).delete()
        elif obj_type == "doc":
            session.query(DocumentAuthorship).filter(DocumentAuthorship.document_id == obj_id).delete()
        session.commit()

        for connection in connections:
            connection_parts = connection.split(":")
            connection_type = connection_parts[0]
            connection_id = to_int(connection_parts[1] if len(connection_parts) > 1 else None)
            connection_category = connection_parts[2] if len(connection_parts) > 2 else None
            if obj == Person:
                if connection_type == "doc":
                    session.add(DocumentAuthorship(document_id=connection_id, person_id=obj_id))
                    session.commit()
                elif connection_type == "org":
                    if connection_category == "education":
                        # This is an education relationship
                        session.add(PersonEducation(organization_id=connection_id, person_id=obj_id))
                        session.commit()
                    else:
                        # This is a regular organization membership
                        session.add(OrganizationMembership(organization_id=connection_id, person_id=obj_id))
                        session.commit()
                elif connection_type == "field_of_study":
                    session.add(PersonFieldOfStudy(field_of_study_id=connection_id, person_id=obj_id))
                    session.commit()
            elif obj == Organization:
                if connection_category == "alumni":
                    session.add(PersonEducation(organization_id=obj_id, person_id=connection_id))
                    session.commit()
                else:
                    session.add(OrganizationMembership(organization_id=obj_id, person_id=connection_id))
                    session.commit()
            elif obj == Document:
                session.add(DocumentAuthorship(document_id=obj_id, person_id=connection_id))
                session.commit()
    return obj_id


@app.get("/delete", dependencies=[Depends(require_login)])
def delete(request: Request):
    """
    Deletes an existing organization, person, or document.

    This route handles the deletion of an existing entry for an organization, person, or document
    based on the query parameters provided in the request. It expects 'type' and 'id' parameters
    in the request arguments.

    Query Parameters:
    - type (str): The type of object to delete ('org', 'person', 'doc', 'field_of_study').
    - id (int): The ID of the object to delete.

    Returns:
    - Renders the 'redirect.html' template to redirect to the search page after deletion.
    - Aborts with a 501 status code if the 'type' or 'id' parameter is missing or invalid.
    - Aborts with a 404 status code if the object to delete is not found.
    """
    if len(request.query_params) != 2 or not request.query_params.get("type") or not request.query_params.get("id"):
        abort(501)
    obj_type = request.query_params.get("type")
    obj_id = to_int(request.query_params.get("id"))
    obj_dict = {"org": Organization, "person": Person, "doc": Document, "field_of_study": FieldOfStudy}
    if obj_type not in obj_dict:
        abort(404)
    obj = obj_dict[obj_type]
    stmt = select(obj).where(obj.id == obj_id)
    with Session(engine) as session:
        data = session.execute(stmt).scalar_one_or_none()
        if data:
            if obj_type == "person":
                session.query(DocumentAuthorship).filter(DocumentAuthorship.person_id == obj_id).delete()
                session.query(OrganizationMembership).filter(OrganizationMembership.person_id == obj_id).delete()
                session.query(PersonFieldOfStudy).filter(PersonFieldOfStudy.person_id == obj_id).delete()
                session.query(PersonEducation).filter(PersonEducation.person_id == obj_id).delete()
            elif obj_type == "org":
                session.query(OrganizationMembership).filter(OrganizationMembership.organization_id == obj_id).delete()
                session.query(PersonEducation).filter(PersonEducation.organization_id == obj_id).delete()
            elif obj_type == "doc":
                session.query(DocumentAuthorship).filter(DocumentAuthorship.document_id == obj_id).delete()
            elif obj_type == "field_of_study":
                session.query(PersonFieldOfStudy).filter(PersonFieldOfStudy.field_of_study_id == obj_id).delete()
            session.delete(data)
            session.commit()
        else:
            abort(404)

    return render(request, "redirect.html", url="/search")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="localhost", port=5000, reload=True)
