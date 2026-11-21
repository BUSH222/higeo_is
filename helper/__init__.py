import os
from secrets import token_urlsafe

from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())

# Database configuration (written by `manager.py db_set`)
DATABASE_ENGINES = ("sqlite", "postgresql", "mysql")
DATABASE_ENGINE = os.environ.get("DATABASE_ENGINE") or "sqlite"
if DATABASE_ENGINE not in DATABASE_ENGINES:
    raise RuntimeError(f"DATABASE_ENGINE must be one of {', '.join(DATABASE_ENGINES)}, not {DATABASE_ENGINE!r}.")
# For sqlite this is the path of the database file; the host, port, user and password are not used.
DATABASE_NAME = os.environ.get("DATABASE_NAME") or ("higeo.sqlite3" if DATABASE_ENGINE == "sqlite" else "higeo")
DATABASE_HOST = os.environ.get("DATABASE_HOST") or "localhost"
DATABASE_PORT = os.environ.get("DATABASE_PORT") or None
DATABASE_USER = os.environ.get("DATABASE_USER") or None
DATABASE_PASSWORD = os.environ.get("DATABASE_PASSWORD") or None

# Web application configuration
SECRET_KEY = os.environ.get("SECRET_KEY") or token_urlsafe(16)


def N_(message: str) -> str:
    """Mark a string for `pybabel extract` without translating it; it is translated where it is shown."""
    return message


# Project constants
# /list_custom?type=<key> page -> stored Person.academic_degree value (must match the DB exactly).
# The list page translates the value for its heading.
ACADEMIC_DEGREE_LISTS = {
    "acad_full_members": N_("действительный член"),
    "acad_foreign_members": N_("иностранный член"),
    "acad_honorary_members": N_("почётный член"),
    "acad_corresponding_members": N_("член-корреспондент"),
    "acad_professors": N_("профессор РАН"),
    "acad_foreign_correspondents": N_("иностранный корреспондент"),
}
ACADEMIC_DEGREE_TO_LIST = {degree: list_type for list_type, degree in ACADEMIC_DEGREE_LISTS.items()}
# Any other title, e.g. of the academies of the Soviet republics: it has no list page; the person is linked to the
# academy as an organization and the exact title is written in the comment.
ACADEMIC_DEGREE_OTHER = "другое"

MULTIPLE_CHOICE_FIELDS = {
    "academic_degree": ["", *ACADEMIC_DEGREE_LISTS.values(), ACADEMIC_DEGREE_OTHER],
    "org_type": [
        "Международные союзы",
        "",
        "Научные учреждения",
        "Музеи",
        "Координирующие организации",
        "Академии",
        "Научные общества",
        "Высшие учебные заведения",
        "Подразделения",
        "Прочие",
    ],
}
FILE_FIELDS = ["file"]


CONNECTION_TYPE_MAPPING = {
    "doc": "doc",
    "org": "org",
    "person": "person",
    "education": "org",  # education connects to organizations
    "alumni": "person",  # alumni connects to persons
    "field_of_study": "field_of_study",
}


TITLE_CONVERTER_NEW_EDIT = {
    "org": "organization",
    "person": "person",
    "doc": "document",
    "field_of_study": "field of study",
}

HEADING_CONVERTER = {
    "org": "Организация",
    "person": "Персоналия",
    "doc": "Документ",
    "field_of_study": "Область знаний",
}

TITLE_CONVERTER_LIST = {
    "org": "Организации",
    "person": "Персоналии",
    "doc": "Документы",
    "field_of_study": "Области исследования",
}
