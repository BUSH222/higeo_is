import html
from datetime import datetime

from sqlalchemy import URL, ForeignKey, String, Text, create_engine, event, text
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from helper import ACADEMIC_DEGREE_TO_LIST, DATABASE_ENGINE
from helper.cleanup.clean_dict import clean_dict
from helper.db.settings import DatabaseSettings

# Collations that sort by code point, so that every engine orders names the same way.
BYTE_ORDER_COLLATIONS = {"sqlite": "BINARY", "postgresql": "C", "mysql": "utf8mb4_bin"}


def _academic_degree_link(degree: str | None) -> str | None:
    """Render the degree as a link to its /list_custom page (plain escaped text if there is no such list)."""
    if not degree:
        return degree
    list_type = ACADEMIC_DEGREE_TO_LIST.get(degree)
    if list_type is None:
        return html.escape(degree)
    return f'<a href="/list_custom?type={list_type}">{html.escape(degree)}</a>'


def _documents_by_year(authorships: list[DocumentAuthorship]) -> list[list]:
    """Entries ``["doc", id, "<year> - <title>"]``, oldest first; documents without a year go last (by title)."""
    documents = sorted(
        (authorship.document for authorship in authorships),
        key=lambda document: (document.year is None, document.year or "", str(document)),
    )
    return [
        ["doc", document.id, f"{document.year} - {document}" if document.year else str(document)]
        for document in documents
    ]


def database_url(database: str | None = None) -> URL:
    """Build the connection URL of the configured engine, for the given database (default: the configured one)."""
    return DatabaseSettings.from_config().url(database)


def byte_order(column):
    """Order by code point rather than by the locale of the database."""
    return column.collate(BYTE_ORDER_COLLATIONS[DATABASE_ENGINE])


def create_database(settings: DatabaseSettings | None = None):
    """
    Creates the database (the configured one, unless `settings` says otherwise) if it does not already exist.

    - sqlite: nothing to do, the file is created on the first connection.
    - postgresql: connects to the `postgres` maintenance database and creates a UTF8 database
      with the ru_RU.UTF-8 locale, owned by the connecting user.
    - mysql: connects to the server and creates a utf8mb4 database. Its collation is utf8mb4_bin, so that
      comparisons are exact, as they are on the other two engines.
    """
    settings = settings or DatabaseSettings.from_config()
    if settings.engine == "sqlite":
        print("SQLite creates the database file on first use. Skipping creation.")
        return

    maintenance_database = "postgres" if settings.engine == "postgresql" else ""
    server = create_engine(settings.url(maintenance_database), isolation_level="AUTOCOMMIT")
    quoted_name = server.dialect.identifier_preparer.quote(settings.name)
    with server.connect() as conn:
        if settings.engine == "postgresql":
            exists = conn.execute(text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": settings.name})
            create = (
                f"CREATE DATABASE {quoted_name} WITH ENCODING = 'UTF8' TEMPLATE = template0"
                " LC_COLLATE = 'ru_RU.UTF-8' LC_CTYPE = 'ru_RU.UTF-8'"
            )
        else:
            exists = conn.execute(
                text("SELECT 1 FROM information_schema.schemata WHERE schema_name = :name"), {"name": settings.name}
            )
            create = f"CREATE DATABASE {quoted_name} CHARACTER SET utf8mb4 COLLATE utf8mb4_bin"
        if exists.first():
            print("Database already exists. Skipping creation.")
        else:
            print("Creating the database for the first time...")
            conn.execute(text(create))
    server.dispose()


engine = create_engine(database_url(), pool_pre_ping=True)

if DATABASE_ENGINE == "sqlite":

    @event.listens_for(engine, "connect")
    def _configure_sqlite(dbapi_connection, _connection_record):
        # SQLite only folds ASCII in lower() and does not enforce foreign keys unless asked to.
        dbapi_connection.create_function(
            "lower", 1, lambda value: value.lower() if isinstance(value, str) else value, deterministic=True
        )
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


class Base(DeclarativeBase):
    """
    Base class for the SQLAlchemy declarative base.
    This class serves as the base class for all ORM-mapped classes in the database.
    It inherits from `DeclarativeBase`, which is a SQLAlchemy base class used for
    declarative class definitions.
    Attributes:
        None
    """

    # MySQL needs a length for VARCHAR and caps TEXT at 64 KB, which a biography can exceed,
    # so strings are TEXT (LONGTEXT on MySQL) unless a column says otherwise.
    type_annotation_map = {str: Text().with_variant(LONGTEXT(), "mysql")}  # noqa: RUF012 (read by SQLAlchemy)


class Timestamped:
    """Adds the date of the last change, which the administrator's pages show in cursive at the end."""

    last_updated: Mapped[datetime] = mapped_column(nullable=True, default=datetime.now, onupdate=datetime.now)


class Person(Timestamped, Base):
    """
    Represents a person with various attributes and relationships.
    Attributes:
        id (int): Primary key, auto-incremented.
        name (str): First name of the person, cannot be null.
        surname (str): Surname of the person, cannot be null.
        patronymic (str): Patronymic of the person.
        name_en (str): First name in English.
        surname_en (str): Surname in English.
        patronymic_en (str): Patronymic in English.
        birth_date (datetime): Birth date of the person.
        death_date (datetime): Death date of the person.
        birth_place (str): Birth place of the person.
        death_place (str): Death place of the person.
        academic_degree (str): Academic degree of the person.
        field_of_study (str): Field of study of the person.
        area_of_study (str): Area of study of the person.
        organizations (list[OrganizationMembership]): List of organization memberships.
        documents (list[DocumentAuthorship]): List of document authorships.
        biography (str): Biography of the person.
        bibliography (str): Bibliography of the person.
        photo (str): Photo of the person.
        comment (str): Additional comments.
    Methods:
        values_ru(): Returns a dictionary of the person's attributes in Russian.
        __str__(): Returns a string representation of the person's full name.
    """

    __tablename__ = "person"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    surname: Mapped[str] = mapped_column(nullable=False)
    name: Mapped[str] = mapped_column(nullable=False)
    patronymic: Mapped[str] = mapped_column(nullable=True)

    name_en: Mapped[str] = mapped_column(nullable=True)
    surname_en: Mapped[str] = mapped_column(nullable=True)
    patronymic_en: Mapped[str] = mapped_column(nullable=True)

    birth_date: Mapped[datetime] = mapped_column(nullable=True)
    death_date: Mapped[datetime] = mapped_column(nullable=True)
    birth_place: Mapped[str] = mapped_column(nullable=True)
    death_place: Mapped[str] = mapped_column(nullable=True)

    academic_degree: Mapped[str] = mapped_column(nullable=True)

    field_of_study: Mapped[list[FieldOfStudy]] = relationship("PersonFieldOfStudy", back_populates="person")

    area_of_study: Mapped[str] = mapped_column(nullable=True)  # geography

    education: Mapped[list[PersonEducation]] = relationship("PersonEducation", back_populates="person")

    organizations: Mapped[list[OrganizationMembership]] = relationship(
        "OrganizationMembership", back_populates="person"
    )
    documents: Mapped[list[DocumentAuthorship]] = relationship("DocumentAuthorship", back_populates="person")

    biography: Mapped[str] = mapped_column(nullable=True)
    bibliography: Mapped[str] = mapped_column(nullable=True)

    photo: Mapped[str] = mapped_column(nullable=True)
    comment: Mapped[str] = mapped_column(nullable=True)

    def values_ru(self):
        values = {
            "Фамилия Имя Отчество": "<b>" + str(self) + "</b>",
            "Дата рождения": self.birth_date,
            "Место рождения": self.birth_place,
            "Дата смерти": self.death_date,
            "Место смерти": self.death_place,
            "Академическое звание": _academic_degree_link(self.academic_degree),
            "Область исследования": sorted(
                [["field_of_study", f.field_of_study.id, str(f.field_of_study)] for f in self.field_of_study],
                key=lambda x: x[2],
            ),
            "Районы работ": self.area_of_study,
            "Образование": sorted(
                [["org", org.organization.id, str(org.organization)] for org in self.education], key=lambda x: x[2]
            ),
            "Места работы": sorted(
                [["org", org.organization.id, str(org.organization)] for org in self.organizations], key=lambda x: x[2]
            ),
            "Биография": self.biography,
            "Библиография": self.bibliography,
            "Фотография": self.photo,
            "Документы": _documents_by_year(self.documents),
            "Комментарии": self.comment,
        }
        return clean_dict(values)

    def values_en(self):
        """
        Returns a dictionary of the person's attributes with English labels.
        Structure mirrors values_ru and keeps the same data values.
        """
        values = {
            "Full name": "<b>" + " ".join(filter(None, (self.surname_en, self.name_en, self.patronymic_en))) + "</b>",
            "Birth date": self.birth_date,
            "Birth place": self.birth_place,
            "Death date": self.death_date,
            "Death place": self.death_place,
            "Academic degree": _academic_degree_link(self.academic_degree),
            "Field of study": sorted(
                [["field_of_study", f.field_of_study.id, str(f.field_of_study)] for f in self.field_of_study],
                key=lambda x: x[2],
            ),
            "Work areas": self.area_of_study,
            "Education": sorted(
                [["org", org.organization.id, str(org.organization)] for org in self.education], key=lambda x: x[2]
            ),
            "Workplaces": sorted(
                [["org", org.organization.id, str(org.organization)] for org in self.organizations], key=lambda x: x[2]
            ),
            "Biography": self.biography,
            "Bibliography": self.bibliography,
            "Photo": self.photo,
            "Documents": _documents_by_year(self.documents),
            "Comments": self.comment,
        }
        return clean_dict(values)

    def __str__(self):
        return " ".join(filter(None, (self.surname, self.name, self.patronymic)))


class Organization(Timestamped, Base):
    """
    Represents an organization entity in the database.
    Attributes:
        id (int): The primary key of the organization, auto-incremented.
        name (str): The name of the organization, cannot be null.
        members (list[OrganizationMembership]): A list of memberships associated with the organization.
        org_type (str): The type of the organization.
        history (str): The history of the organization.
        comment (str): Additional comments about the organization.
    Methods:
        values_ru():
            Returns a dictionary of the organization's attributes with Russian labels.
        __str__():
            Returns the name of the organization as its string representation.
    """

    __tablename__ = "organization"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(nullable=False)
    members: Mapped[list[OrganizationMembership]] = relationship(
        "OrganizationMembership", back_populates="organization"
    )
    alumni: Mapped[list[PersonEducation]] = relationship("PersonEducation", back_populates="organization")
    org_type: Mapped[str] = mapped_column(nullable=True)
    history: Mapped[str] = mapped_column(nullable=True)
    comment: Mapped[str] = mapped_column(nullable=True)

    def values_ru(self):
        values = {
            "Название": "<b>" + self.name + "</b>",
            "Тип организации": self.org_type,
            "История": self.history,
            "Комментарий": self.comment,
            "Связанные персоналии": sorted(
                [["person", member.person.id, str(member.person)] for member in self.members], key=lambda x: x[2]
            ),
            "Выпускники": sorted(
                [["person", alum.person.id, str(alum.person)] for alum in self.alumni], key=lambda x: x[2]
            ),
        }
        return clean_dict(values)

    def values_en(self):
        """
        Returns a dictionary of the organization's attributes with English labels.
        Mirrors values_ru structure.
        """

        def person_display(p):
            last = p.surname_en or p.surname
            first = p.name_en or p.name
            patr = p.patronymic_en or p.patronymic
            return " ".join(filter(None, (last, first, patr)))

        values = {
            "Name": "<b>" + self.name + "</b>",
            "Type of organization": self.org_type,
            "History": self.history,
            "Comment": self.comment,
            "Related persons": sorted(
                [["person", member.person.id, person_display(member.person)] for member in self.members],
                key=lambda x: x[2],
            ),
            "Alumni": sorted(
                [["person", alum.person.id, person_display(alum.person)] for alum in self.alumni], key=lambda x: x[2]
            ),
        }
        return clean_dict(values)

    def __str__(self):
        return self.name


class Document(Timestamped, Base):
    """
    Represents a document entity in the database.
    Attributes:
        id (int): Primary key, auto-incremented.
        name (str): Name of the document, cannot be null.
        doc_type (str): Type of the document, cannot be null.
        language (str, optional): Language of the document.
        source (str, optional): Source of the document.
        authors (list[DocumentAuthorship]): List of authors associated with the document.
        year (str, optional): Year of publication.
        file (str, optional): File associated with the document.
        comment (str, optional): Additional comments about the document.
    Methods:
        values_ru():
            Returns a dictionary of document attributes with Russian keys.
        __str__():
            Returns the name of the document as its string representation.
    """

    __tablename__ = "document"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(nullable=False)
    doc_type: Mapped[str] = mapped_column(nullable=False)
    language: Mapped[str] = mapped_column(nullable=True)
    source: Mapped[str] = mapped_column(nullable=True)
    authors: Mapped[list[DocumentAuthorship]] = relationship("DocumentAuthorship", back_populates="document")
    year: Mapped[str] = mapped_column(nullable=True)
    file: Mapped[str] = mapped_column(nullable=True)
    comment: Mapped[str] = mapped_column(nullable=True)

    def values_ru(self):
        values = {
            "Авторы": sorted(
                [["person", author.person.id, str(author.person)] for author in self.authors], key=lambda x: x[2]
            ),
            "Источник": self.source,
            "Название": "<b>" + self.name + "</b>",
            "Тип документа": self.doc_type,
            "Язык": self.language,
            "Год издания": self.year,
            "Файл": self.file,
            "Комментарий": self.comment,
        }
        return clean_dict(values)

    def values_en(self):
        """
        Returns a dictionary of the document's attributes with English labels.
        Mirrors values_ru structure.
        """

        def person_display(p):
            last = p.surname_en or p.surname
            first = p.name_en or p.name
            patr = p.patronymic_en or p.patronymic
            return " ".join(filter(None, (last, first, patr)))

        values = {
            "Authors": sorted(
                [["person", author.person.id, person_display(author.person)] for author in self.authors],
                key=lambda x: x[2],
            ),
            "Source": self.source,
            "Title": "<b>" + self.name + "</b>",
            "Document type": self.doc_type,
            "Language": self.language,
            "Year of publication": self.year,
            "File": self.file,
            "Comment": self.comment,
        }
        return clean_dict(values)

    def __str__(self):
        return self.name


class FieldOfStudy(Timestamped, Base):
    """
    Represents a field of study entity in the database.
    Attributes:
        id (int): The primary key of the field of study, auto-incremented.
        name (str): The name of the field of study, cannot be null.
        comment (str): Additional comments about the field of study.
    Methods:
        values_ru():
            Returns a dictionary of the field of study's attributes with Russian labels.
        __str__():
            Returns the name of the field of study as its string representation.
    """

    __tablename__ = "field_of_study"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(nullable=False)
    comment: Mapped[str] = mapped_column(nullable=True)
    members: Mapped[list[OrganizationMembership]] = relationship("PersonFieldOfStudy", back_populates="field_of_study")

    def values_ru(self):
        values = {
            "Название": self.name,
            "Комментарий": self.comment,
            "Связанные персоналии": sorted(
                [["person", member.person.id, str(member.person)] for member in self.members], key=lambda x: x[2]
            ),
        }
        return clean_dict(values)

    def values_en(self):
        """
        Returns a dictionary of the field of study's attributes with English labels.
        Mirrors values_ru structure.
        """

        def person_display(p):
            last = p.surname_en or p.surname
            first = p.name_en or p.name
            patr = p.patronymic_en or p.patronymic
            return " ".join(filter(None, (last, first, patr)))

        values = {
            "Name": self.name,
            "Comment": self.comment,
            "Related persons": sorted(
                [["person", member.person.id, person_display(member.person)] for member in self.members],
                key=lambda x: x[2],
            ),
        }
        return clean_dict(values)

    def __str__(self):
        return self.name


class OrganizationMembership(Base):
    """
    Represents the membership of a person in an organization.
    Attributes:
        id (int): The primary key of the membership record.
        person_id (int): The foreign key referencing the person.
        organization_id (int): The foreign key referencing the organization.
        person (Person): The relationship to the Person model.
        organization (Organization): The relationship to the Organization model.
    """

    __tablename__ = "organization_membership"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("person.id"))
    organization_id: Mapped[int] = mapped_column(ForeignKey("organization.id"))

    person: Mapped[Person] = relationship("Person", back_populates="organizations")
    organization: Mapped[Organization] = relationship("Organization", back_populates="members")


class PersonEducation(Base):
    """
    Represents the membership of a person in an organization.
    Attributes:
        id (int): The primary key of the membership record.
        person_id (int): The foreign key referencing the person.
        organization_id (int): The foreign key referencing the organization.
        person (Person): The relationship to the Person model.
        organization (Organization): The relationship to the Organization model.
    """

    __tablename__ = "person_education"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("person.id"))
    organization_id: Mapped[int] = mapped_column(ForeignKey("organization.id"))

    person: Mapped[Person] = relationship("Person", back_populates="education")
    organization: Mapped[Organization] = relationship("Organization", back_populates="alumni")


class DocumentAuthorship(Base):
    """
    Represents the authorship relationship between a person and a document.
    Attributes:
        id (int): The primary key for the document authorship record.
        person_id (int): The foreign key referencing the person who authored the document.
        document_id (int): The foreign key referencing the document authored by the person.
        person (Person): The relationship to the Person model, representing the author.
        document (Document): The relationship to the Document model, representing the authored document.
    """

    __tablename__ = "document_authorship"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("person.id"))
    document_id: Mapped[int] = mapped_column(ForeignKey("document.id"))

    person: Mapped[Person] = relationship("Person", back_populates="documents")
    document: Mapped[Document] = relationship("Document", back_populates="authors")


class PersonFieldOfStudy(Base):
    """
    Represents the relationship between a person and their field of study.
    Attributes:
        id (int): The primary key for the person-field of study relationship.
        person_id (int): The foreign key referencing the person.
        field_of_study_id (int): The foreign key referencing the field of study.
        person (Person): The relationship to the Person model.
        field_of_study (FieldOfStudy): The relationship to the FieldOfStudy model.
    """

    __tablename__ = "person_field_of_study"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("person.id"))
    field_of_study_id: Mapped[int] = mapped_column(ForeignKey("field_of_study.id"))

    person: Mapped[Person] = relationship("Person")
    field_of_study: Mapped[FieldOfStudy] = relationship("FieldOfStudy")


class User(Base):
    """A staff user who can create, edit and delete records."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str]


def create_tables():
    """
    Creates all tables defined in the metadata.
    """
    Base.metadata.create_all(engine)
    print("Tables created.")


def drop_tables():
    """
    Drops all tables defined in the metadata.
    """
    Base.metadata.drop_all(engine)
    print("Tables dropped.")
