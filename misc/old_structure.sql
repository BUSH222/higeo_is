CREATE TABLE author (
    pub      INT     NOT NULL,
    person   INT     NOT NULL,
    _sortkey SMALLINT NOT NULL,
    PRIMARY KEY (pub, person)
);

CREATE INDEX idx_sortkey ON author (_sortkey);

CREATE TABLE employ (
    person   INT     NOT NULL,
    org      INT     NOT NULL,
    _sortkey SMALLINT NULL,
    PRIMARY KEY (person, org)
);

CREATE TABLE org (
    _id       SERIAL PRIMARY KEY,
    name      VARCHAR(250) NOT NULL,
    nm2       VARCHAR(500) NULL,
    cit       VARCHAR(500) NULL,
    typ       VARCHAR(50) NULL,
    ist       TEXT NULL,
    chl       TEXT NULL,
    med       TEXT NULL,
    tel       VARCHAR(100) NULL,
    lrt       TEXT NULL,
    _user_id  INT DEFAULT 1 NOT NULL,
    _modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

COMMENT ON TABLE org IS 'Organizations';

CREATE INDEX idx_name ON org (name);

CREATE TABLE person (
    _id            SERIAL PRIMARY KEY,
    name           VARCHAR(200) NOT NULL,
    _user_id       INT DEFAULT 1 NOT NULL,
    _modified      TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    first_name_ru  VARCHAR(200) NULL,
    middle_name_ru VARCHAR(200) NULL,
    last_name_ru   VARCHAR(200) NULL,
    first_name_en  VARCHAR(200) NULL,
    last_name_en   VARCHAR(200) NULL,
    century        VARCHAR(100) NULL,
    birth_date     VARCHAR(20) NULL,
    birth_country  VARCHAR(200) NULL,
    death_date     VARCHAR(20) NULL,
    death_country  VARCHAR(200) NULL,
    degree         VARCHAR(50) NULL,
    int            TEXT NULL,
    geo            VARCHAR(200) NULL,
    chl            TEXT NULL,
    bio            TEXT NULL,
    bib            TEXT NULL,
    fot            VARCHAR(100) NULL
);

COMMENT ON TABLE person IS 'Persons';

CREATE TABLE pub (
    _id       SERIAL PRIMARY KEY,
    _source   INT DEFAULT 0 NOT NULL,
    name      VARCHAR(500) NOT NULL,
    tor       VARCHAR(500) NULL,
    vid       VARCHAR(50) NOT NULL,
    lng       TEXT NULL,
    god       INT NULL,
    vst       VARCHAR(500) NULL,
    bib       VARCHAR(800) NULL,
    _user_id  INT DEFAULT 1 NOT NULL,
    _modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    txt       TEXT NULL,
    fil       VARCHAR(16) NULL
);

COMMENT ON TABLE pub IS 'Publications';

CREATE INDEX idx_name_pub ON pub (name);

CREATE INDEX idx_source ON pub (_source);

CREATE TABLE source (
    _id       SERIAL PRIMARY KEY,
    name      VARCHAR(400) NOT NULL,
    type      TEXT NULL,
    out       VARCHAR(600) NULL,
    _user_id  INT DEFAULT 1 NOT NULL,
    _modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX idx_out ON source (out);