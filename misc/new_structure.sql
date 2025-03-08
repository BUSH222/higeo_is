CREATE TABLE IF NOT EXISTS person (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    surname VARCHAR(255) NOT NULL,
    patronymic VARCHAR(255),
    name_en VARCHAR(255),
    surname_en VARCHAR(255),
    patronymic_en VARCHAR(255),
    birth_date TIMESTAMP,
    death_date TIMESTAMP,
    birth_place VARCHAR(255),
    death_place VARCHAR(255),
    academic_degree VARCHAR(255),
    field_of_study VARCHAR(255),
    area_of_study VARCHAR(255),
    biography TEXT,
    bibliography TEXT,
    photo VARCHAR(255),
    comment TEXT
);

CREATE TABLE IF NOT EXISTS organization (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    comment TEXT
);

CREATE TABLE IF NOT EXISTS document (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    source VARCHAR(255),
    year VARCHAR(4),
    file VARCHAR(255),
    comment TEXT
);

CREATE TABLE IF NOT EXISTS organization_membership (
    id SERIAL PRIMARY KEY,
    person_id INT REFERENCES person(id),
    organization_id INT REFERENCES organization(id)
);

CREATE TABLE IF NOT EXISTS document_authorship (
    id SERIAL PRIMARY KEY,
    person_id INT REFERENCES person(id),
    document_id INT REFERENCES document(id)
);