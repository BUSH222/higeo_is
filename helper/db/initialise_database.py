from sqlalchemy import create_engine, ForeignKey
from sqlalchemy.orm import DeclarativeBase, relationship, Mapped, mapped_column
import psycopg2
from psycopg2 import sql
from datetime import datetime
from helper import DATABASE_USER, DATABASE_PASSWORD, DATABASE_NAME, DATABASE_HOST, DATABASE_PORT
from helper.cleanup.clean_dict import clean_dict


DATABASE_URL = f"postgresql://{DATABASE_USER}:{DATABASE_PASSWORD}@{DATABASE_HOST}:{DATABASE_PORT}/{DATABASE_NAME}"


def create_database():
    """
    Creates a PostgreSQL database if it does not already exist.
    This function connects to the PostgreSQL server using the provided
    credentials and checks if a database with the specified name exists.
    If the database does not exist, it creates a new database with the
    specified name and configuration.
    Raises:
        psycopg2.DatabaseError: If there is an error connecting to the
        PostgreSQL server or executing the SQL queries.
    Notes:
        - The function assumes that the PostgreSQL server is running and
          accessible with the provided credentials.
        - The function uses the `psycopg2` library to interact with the
          PostgreSQL server.
        - The database is created with the following configuration:
            - Owner: postgres
            - Encoding: UTF8
            - Connection limit: -1 (unlimited)
            - Is template: False
    """
    conn = psycopg2.connect(dbname='postgres', user=DATABASE_USER, password=DATABASE_PASSWORD, host=DATABASE_HOST)
    conn.autocommit = True
    cursor = conn.cursor()

    cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DATABASE_NAME, ))
    exists = cursor.fetchone()

    if not exists:
        print('Creating the database for the first time...')
        query = sql.SQL("CREATE DATABASE {} WITH\
                        OWNER = postgres\
                        ENCODING = 'UTF8'\
                        CONNECTION LIMIT = -1\
                        IS_TEMPLATE = False;").format(sql.Identifier(DATABASE_NAME))
        cursor.execute(query)
    else:
        print('Database already exists. Skipping creation.')

    cursor.close()
    conn.close()


engine = create_engine(DATABASE_URL)


class Base(DeclarativeBase):
    """
    Base class for the SQLAlchemy declarative base.
    This class serves as the base class for all ORM-mapped classes in the database.
    It inherits from `DeclarativeBase`, which is a SQLAlchemy base class used for
    declarative class definitions.
    Attributes:
        None
    """
    pass


class Person(Base):
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
    __tablename__ = 'person'
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(nullable=False)
    surname: Mapped[str] = mapped_column(nullable=False)
    patronymic: Mapped[str] = mapped_column(nullable=True)

    name_en: Mapped[str] = mapped_column(nullable=True)
    surname_en: Mapped[str] = mapped_column(nullable=True)
    patronymic_en: Mapped[str] = mapped_column(nullable=True)

    birth_date: Mapped[datetime] = mapped_column(nullable=True)
    death_date: Mapped[datetime] = mapped_column(nullable=True)
    birth_place: Mapped[str] = mapped_column(nullable=True)
    death_place: Mapped[str] = mapped_column(nullable=True)

    academic_degree: Mapped[str] = mapped_column(nullable=True)
    field_of_study: Mapped[str] = mapped_column(nullable=True)
    area_of_study: Mapped[str] = mapped_column(nullable=True)  # geography

    organizations: Mapped[list["OrganizationMembership"]] = \
        relationship("OrganizationMembership", back_populates="person")
    documents: Mapped[list["DocumentAuthorship"]] = \
        relationship("DocumentAuthorship", back_populates="person")

    biography: Mapped[str] = mapped_column(nullable=True)
    bibliography: Mapped[str] = mapped_column(nullable=True)

    photo: Mapped[str] = mapped_column(nullable=True)
    comment: Mapped[str] = mapped_column(nullable=True)

    def values_ru(self):
        values = {'ФИО': str(self),
                  'Дата рождения': self.birth_date,
                  'Место рождения': self.birth_place,
                  'Дата сметри': self.death_date,
                  'Место смерти': self.death_date,
                  'Академическое звание': self.academic_degree,
                  'Область исследования': self.field_of_study,
                  'Географи исследования': self.area_of_study,
                  'Связанные организации':
                  [['org', org.organization.id, str(org.organization)] for org in self.organizations],
                  'Документы': [['doc', doc.document.id, str(doc.document)] for doc in self.documents],
                  'Биография': self.biography,
                  'Библиография': self.bibliography,
                  'Фотография': self.photo,
                  'Комментарии': self.comment}
        return clean_dict(values)

    def __str__(self):
        return ' '.join(filter(None, (self.surname, self.name, self.patronymic)))


class Organization(Base):
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
    __tablename__ = 'organization'
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(nullable=False)
    members: Mapped[list["OrganizationMembership"]] = \
        relationship("OrganizationMembership", back_populates="organization")
    org_type: Mapped[str] = mapped_column(nullable=True)
    history: Mapped[str] = mapped_column(nullable=True)
    comment: Mapped[str] = mapped_column(nullable=True)

    def values_ru(self):
        values = {'Связанные персоналии':
                  [['person', member.person.id, str(member.person)] for member in self.members],
                  'Название': self.name,
                  'Тип организации': self.org_type,
                  'История': self.history,
                  'Комментарий': self.comment}
        return clean_dict(values)

    def __str__(self):
        return self.name


class Document(Base):
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

    __tablename__ = 'document'
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(nullable=False)
    doc_type: Mapped[str] = mapped_column(nullable=False)
    language: Mapped[str] = mapped_column(nullable=True)
    source: Mapped[str] = mapped_column(nullable=True)
    authors: Mapped[list["DocumentAuthorship"]] = relationship("DocumentAuthorship", back_populates="document")
    year: Mapped[str] = mapped_column(nullable=True)
    file: Mapped[str] = mapped_column(nullable=True)
    comment: Mapped[str] = mapped_column(nullable=True)

    def values_ru(self):
        values = {'Авторы': [['person', author.person.id, str(author.person)] for author in self.authors],
                  'Источник': self.source,
                  'Название': self.name,
                  'Тип документа': self.doc_type,
                  'Язык': self.language,
                  'Год издания': self.year,
                  'Файл': self.file,
                  'Комментарий': self.comment}
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
    __tablename__ = 'organization_membership'
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    person_id: Mapped[int] = mapped_column(ForeignKey('person.id'))
    organization_id: Mapped[int] = mapped_column(ForeignKey('organization.id'))

    person: Mapped["Person"] = relationship("Person", back_populates="organizations")
    organization: Mapped["Organization"] = relationship("Organization", back_populates="members")


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
    __tablename__ = 'document_authorship'
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    person_id: Mapped[int] = mapped_column(ForeignKey('person.id'))
    document_id: Mapped[int] = mapped_column(ForeignKey('document.id'))

    person: Mapped["Person"] = relationship("Person", back_populates="documents")
    document: Mapped["Document"] = relationship("Document", back_populates="authors")


def create_tables():
    """
    Creates all tables defined in the metadata.
    """
    Base.metadata.create_all(engine)
    print('Tables created.')
