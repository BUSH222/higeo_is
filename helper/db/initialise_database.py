from sqlalchemy import create_engine, ForeignKey
from sqlalchemy.orm import DeclarativeBase, relationship, Mapped, mapped_column
import psycopg2
from psycopg2 import sql
from datetime import datetime
import logging
from helper import DATABASE_USER, DATABASE_PASSWORD, DATABASE_NAME, DATABASE_HOST, DATABASE_PORT
from helper.cleanup.clean_dict import clean_dict


DATABASE_URL = f"postgresql://{DATABASE_USER}:{DATABASE_PASSWORD}@{DATABASE_HOST}:{DATABASE_PORT}/{DATABASE_NAME}"

conn = psycopg2.connect(dbname='postgres', user=DATABASE_USER, password=DATABASE_PASSWORD, host=DATABASE_HOST)
conn.autocommit = True
cursor = conn.cursor()

cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DATABASE_NAME, ))
exists = cursor.fetchone()

if not exists:
    logging.info('Creating the database for the first time...')
    query = sql.SQL("CREATE DATABASE {} WITH\
                    OWNER = postgres\
                    ENCODING = 'UTF8'\
                    LOCALE_PROVIDER = 'libc'\
                    CONNECTION LIMIT = -1\
                    IS_TEMPLATE = False;").format(sql.Identifier(DATABASE_NAME))
    cursor.execute(query)

cursor.close()
conn.close()


engine = create_engine(DATABASE_URL)


class Base(DeclarativeBase):
    pass


class Person(Base):
    __tablename__ = 'person'
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(nullable=False)
    surname: Mapped[str] = mapped_column(nullable=False)
    patronymic: Mapped[str | None] = mapped_column(nullable=True)

    name_en: Mapped[str | None] = mapped_column(nullable=True)
    surname_en: Mapped[str | None] = mapped_column(nullable=True)
    patronymic_en: Mapped[str | None] = mapped_column(nullable=True)

    birth_date: Mapped[datetime | None] = mapped_column(nullable=True)
    death_date: Mapped[datetime | None] = mapped_column(nullable=True)
    birth_place: Mapped[str | None] = mapped_column(nullable=True)
    death_place: Mapped[str | None] = mapped_column(nullable=True)

    academic_degree: Mapped[str | None] = mapped_column(nullable=True)
    field_of_study: Mapped[str | None] = mapped_column(nullable=True)
    area_of_study: Mapped[str | None] = mapped_column(nullable=True)  # geography

    organizations: Mapped[list["OrganizationMembership"]] = \
        relationship("OrganizationMembership", back_populates="person")
    documents: Mapped[list["DocumentAuthorship"]] = \
        relationship("DocumentAuthorship", back_populates="person")

    biography: Mapped[str | None] = mapped_column(nullable=True)
    bibliography: Mapped[str | None] = mapped_column(nullable=True)

    photo: Mapped[str | None] = mapped_column(nullable=True)
    comment: Mapped[str | None] = mapped_column(nullable=True)

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
    __tablename__ = 'organization'
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(nullable=False)
    members: Mapped[list["OrganizationMembership"]] = \
        relationship("OrganizationMembership", back_populates="organization")
    org_type: Mapped[str | None] = mapped_column(nullable=True)
    history: Mapped[str | None] = mapped_column(nullable=True)
    comment: Mapped[str | None] = mapped_column(nullable=True)

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
    __tablename__ = 'document'
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(nullable=False)
    doc_type: Mapped[str] = mapped_column(nullable=False)
    language: Mapped[str] = mapped_column(nullable=True)
    source: Mapped[str | None] = mapped_column(nullable=True)
    authors: Mapped[list["DocumentAuthorship"]] = relationship("DocumentAuthorship", back_populates="document")
    year: Mapped[str | None] = mapped_column(nullable=True)
    file: Mapped[str | None] = mapped_column(nullable=True)
    comment: Mapped[str | None] = mapped_column(nullable=True)

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
    __tablename__ = 'organization_membership'
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    person_id: Mapped[int] = mapped_column(ForeignKey('person.id'))
    organization_id: Mapped[int] = mapped_column(ForeignKey('organization.id'))

    person: Mapped["Person"] = relationship("Person", back_populates="organizations")
    organization: Mapped["Organization"] = relationship("Organization", back_populates="members")


class DocumentAuthorship(Base):
    __tablename__ = 'document_authorship'
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    person_id: Mapped[int] = mapped_column(ForeignKey('person.id'))
    document_id: Mapped[int] = mapped_column(ForeignKey('document.id'))

    person: Mapped["Person"] = relationship("Person", back_populates="documents")
    document: Mapped["Document"] = relationship("Document", back_populates="authors")


def create_tables():
    Base.metadata.create_all(engine)
    logging.info('Tables ensured.')
