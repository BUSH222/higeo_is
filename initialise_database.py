from sqlalchemy import create_engine, ForeignKey
from sqlalchemy.orm import DeclarativeBase, relationship, Mapped, mapped_column
import psycopg2
from psycopg2 import sql
from datetime import datetime
import logging
from settings import DATABASE_USER, DATABASE_PASSWORD, DATABASE_NAME, DATABASE_HOST, DATABASE_PORT


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
    patronymic: Mapped[str] = mapped_column()

    name_en: Mapped[str] = mapped_column()
    surname_en: Mapped[str] = mapped_column()
    patronymic_en: Mapped[str] = mapped_column()

    birth_date: Mapped[datetime] = mapped_column()
    death_date: Mapped[datetime] = mapped_column()
    birth_place: Mapped[str] = mapped_column()
    death_place: Mapped[str] = mapped_column()

    academic_degree: Mapped[str] = mapped_column()
    field_of_study: Mapped[str] = mapped_column()
    area_of_study: Mapped[str] = mapped_column()

    organizations: Mapped[list["OrganizationMembership"]] = \
        relationship("OrganizationMembership", back_populates="person")
    documents: Mapped[list["DocumentAuthorship"]] = \
        relationship("DocumentAuthorship", back_populates="person")

    biography: Mapped[str] = mapped_column()
    bibliography: Mapped[str] = mapped_column()

    photo: Mapped[str] = mapped_column()
    comment: Mapped[str] = mapped_column()


class Organization(Base):
    __tablename__ = 'organization'
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(nullable=False)
    members: Mapped[list["OrganizationMembership"]] = \
        relationship("OrganizationMembership", back_populates="organization")
    comment: Mapped[str] = mapped_column()


class Document(Base):
    __tablename__ = 'document'
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(nullable=False)
    source: Mapped[str] = mapped_column()
    authors: Mapped[list["DocumentAuthorship"]] = relationship("DocumentAuthorship", back_populates="document")
    year: Mapped[str] = mapped_column()
    file: Mapped[str] = mapped_column()
    comment: Mapped[str] = mapped_column()


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


Base.metadata.create_all(engine)

logging.info('Tables ensured.')
