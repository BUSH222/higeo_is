import os
from secrets import token_urlsafe

from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())

# Database configuration
DATABASE_NAME = os.environ.get("DATABASE_NAME")
DATABASE_HOST = os.environ.get("DATABASE_HOST")
DATABASE_PORT = os.environ.get("DATABASE_PORT")
DATABASE_USER = os.environ.get("DATABASE_USER")
DATABASE_PASSWORD = os.environ.get("DATABASE_PASSWORD")

# Flask configuration
SECRET_KEY = os.environ.get("SECRET_KEY", token_urlsafe(16))

# Project constants
MULTIPLE_CHOICE_FIELDS = {
    "academic_degree": [
        "",
        "действительный член",
        "иностранный член",
        "почётный член",
        "член-корреспондент",
        "профессор РАН",
    ],
    "org_type": [
        "Международные союзы",
        "",
        "Научные учреждения",
        "Музеи",
        "Координирующие организации",
        "Академии",
        "Научные общества",
        "Высшие учебные заведения",
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
