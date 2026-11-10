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

# Project constants
# /list_custom?type=<key> page -> stored Person.academic_degree value (must match the DB exactly).
# Long forms (e.g. "... АН АзСССР") are deliberately separate from the plain titles.
ACADEMIC_DEGREE_LISTS = {
    "acad_full_members": "действительный член",
    "acad_foreign_members": "иностранный член",
    "acad_honorary_members": "почётный член",
    "acad_corresponding_members": "член-корреспондент",
    "acad_professors": "профессор РАН",
    "acad_foreign_correspondents": "иностранный корреспондент",
    "acad_full_members_azssr": "Действительный член АН АзСССР",
    "acad_corresponding_members_uassr": "Член-корреспондент АН Украинской ССР",
    "acad_corresponding_members_azssr": "Член-корреспондент Академии наук Азербайджанской ССР",
}
ACADEMIC_DEGREE_TO_LIST = {degree: list_type for list_type, degree in ACADEMIC_DEGREE_LISTS.items()}

MULTIPLE_CHOICE_FIELDS = {
    "academic_degree": ["", *ACADEMIC_DEGREE_LISTS.values()],
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
