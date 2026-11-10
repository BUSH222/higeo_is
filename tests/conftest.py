"""Test setup. The tests drop and recreate every table, so they never run against a real database by accident.

By default they use a throwaway SQLite file. To test another engine, point the DATABASE_* settings at a
database whose name contains "test" and set HIGEO_TEST_DATABASE=configured, for example:

    DATABASE_ENGINE=postgresql DATABASE_NAME=higeo_test HIGEO_TEST_DATABASE=configured uv run pytest
"""

import os
import tempfile
from datetime import datetime

import pytest

if os.environ.get("HIGEO_TEST_DATABASE") != "configured":
    os.environ["DATABASE_ENGINE"] = "sqlite"
    os.environ["DATABASE_NAME"] = os.path.join(tempfile.mkdtemp(prefix="higeo-test-"), "test.sqlite3")
os.environ.setdefault("SECRET_KEY", "test-secret-key")

import helper

if "test" not in os.path.basename(helper.DATABASE_NAME):
    pytest.exit(f"Refusing to wipe the database {helper.DATABASE_NAME!r}: its name does not contain 'test'.", 2)

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import main
from helper.db import initialise_database as db
from helper.login import users

STAFF_EMAIL = "staff@example.com"
STAFF_PASSWORD = "correct horse battery"


@pytest.fixture(scope="session", autouse=True)
def database():
    """A fresh schema with a few records. Ё sorts before А by code point, which the ordering tests rely on."""
    db.create_database()
    db.Base.metadata.drop_all(db.engine)
    db.Base.metadata.create_all(db.engine)
    with Session(db.engine) as session:
        vernadsky = db.Person(
            surname="Вернадский",
            name="Владимир",
            patronymic="Иванович",
            surname_en="Vernadsky",
            name_en="Vladimir",
            patronymic_en="Ivanovich",
            birth_date=datetime(1863, 3, 12),
            area_of_study="Урал, Крым",
            academic_degree="действительный член",
            bibliography="<p>Очерки геохимии. 1927.</p>",
        )
        fersman = db.Person(
            surname="Ферсман",
            name="Александр",
            patronymic="Евгеньевич",
            birth_date=datetime(1883, 11, 8),
            area_of_study="Урал , Кольский полуостров",
            academic_degree="действительный член",
        )
        obruchev = db.Person(
            surname="Обручев",
            name="Владимир",
            patronymic="Афанасьевич",
            birth_date=datetime(1863, 10, 10),
            area_of_study="Сибирь,Урал,",
        )
        yolkin = db.Person(surname="Ёлкин", name="Пётр")
        institute = db.Organization(name="Геологический институт", org_type="Научные учреждения")
        university = db.Organization(name="Московский университет", org_type="Высшие учебные заведения")
        biosphere = db.Document(name="Биосфера", doc_type="книга", year="1926")
        later_work = db.Document(name="Яблоко", doc_type="статья", year="1940")
        early_work = db.Document(name="Ящик", doc_type="статья", year="1900")
        undated_work = db.Document(name="Аннотация", doc_type="статья", year=None)
        geochemistry = db.FieldOfStudy(name="Геохимия")
        session.add_all(
            [
                vernadsky,
                fersman,
                obruchev,
                yolkin,
                institute,
                university,
                biosphere,
                later_work,
                early_work,
                undated_work,
                geochemistry,
            ]
        )
        session.flush()
        session.add_all(
            [
                db.OrganizationMembership(person_id=vernadsky.id, organization_id=institute.id),
                db.OrganizationMembership(person_id=fersman.id, organization_id=institute.id),
                db.PersonEducation(person_id=vernadsky.id, organization_id=university.id),
                db.DocumentAuthorship(person_id=vernadsky.id, document_id=biosphere.id),
                db.DocumentAuthorship(person_id=vernadsky.id, document_id=later_work.id),
                db.DocumentAuthorship(person_id=vernadsky.id, document_id=early_work.id),
                db.DocumentAuthorship(person_id=vernadsky.id, document_id=undated_work.id),
                db.PersonFieldOfStudy(person_id=vernadsky.id, field_of_study_id=geochemistry.id),
                db.PersonFieldOfStudy(person_id=fersman.id, field_of_study_id=geochemistry.id),
            ]
        )
        session.commit()
        users.create(session, STAFF_EMAIL, STAFF_PASSWORD)
    yield
    db.engine.dispose()


@pytest.fixture
def client():
    """An anonymous visitor."""
    with TestClient(main.app, follow_redirects=False) as test_client:
        yield test_client


@pytest.fixture
def staff(client):
    """A logged in staff user."""
    response = client.post("/login", data={"email": STAFF_EMAIL, "password": STAFF_PASSWORD})
    assert response.status_code == 303
    return client


@pytest.fixture
def ids():
    """The ids of the seeded records, by name."""
    with Session(db.engine) as session:
        found = {person.surname: person.id for person in session.query(db.Person)}
        found.update({org.name: org.id for org in session.query(db.Organization)})
        found.update({doc.name: doc.id for doc in session.query(db.Document)})
        found.update({field.name: field.id for field in session.query(db.FieldOfStudy)})
    return found
