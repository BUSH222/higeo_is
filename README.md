# Information System for HIGEO
#### View the running version of the website! [higeo.ru](https://higeo.ru)

This project is a web-based information system (FastAPI, SQLAlchemy) for the Department of History of Geology of the Russian Academy of Sciences. It allows users to view, search, and manage information about organizations, people, and documents related to the department.

## Features

- **View Information**: View detailed information about organizations, people, and documents.
- **Search**: Perform searches based on various criteria.
- **Add New Records**: Admins can add new records for organizations, people, and documents.
- **Edit Records**: Admins can edit existing records.
- **Delete Records**: Admins can delete records.

## Installation

1. **Clone the repository**:
    ```sh
    git clone https://github.com/BUSH222/higeo_is.git
    cd higeo_is
    ```

2. **Install dependencies** (requires [uv](https://docs.astral.sh/uv/)):
    ```sh
    uv sync
    uv run pre-commit install
    ```

3. **Set everything up in one go** (database, data, uploaded files, admin account):
    ```sh
    uv run manager.py quicksetup
    ```
    It asks which database to use (SQLite, PostgreSQL or MySQL; the choice is saved to `.env`, together with a new
    `SECRET_KEY` that signs the login cookie), creates it, and then offers to load a **database dump** and an
    **uploads archive**, each given as an `https://` link (for example a file of a GitHub release) or a path on the
    disk. Press Enter to skip a step; without a dump the database starts empty. Finally it can create the first
    admin account. PostgreSQL and MySQL must be installed and running, and loading a SQL dump needs their command
    line tools (`psql` / `mysql`) on the `PATH`.

    The steps are also available one by one:
    ```sh
    uv run manager.py db_set postgresql --name higeo --user postgres -p   # -p prompts for the password
    uv run manager.py db_show                                             # print the current settings
    uv run manager.py db_init                                             # create the database and the missing tables
    uv run manager.py db_restore https://github.com/.../higeo.sql.gz      # or a path; .gz is detected
    uv run manager.py uploads_unpack uploads.tar.gz                       # a link or a path
    ```

## Usage

0. **Create an admin account** (admins can create, edit and delete records; log in at `/login`):
    ```sh
    uv run manager.py user_add admin@example.com
    uv run manager.py user_edit admin@example.com -e new@example.com -p   # change email and/or password
    uv run manager.py user_delete admin@example.com
    ```

1. **Run the application**:
    ```sh
    cd /path/to/higeo_is
    uv run main.py
    ```

2. **Access the application**:
    Open your web browser and go to `http://localhost:5000`.

> This runs the app in development mode, restarting when the code changes. For normal operation run it with an
> ASGI server, for example `uv run uvicorn main:app --host 127.0.0.1 --port 8000 --proxy-headers`, behind a web server.

## Configuration

`manager.py db_set` writes the database settings to `.env`; they can also be edited by hand or set as environment variables.

| Variable | Meaning |
|---|---|
| `DATABASE_ENGINE` | `sqlite` (default), `postgresql` or `mysql`. |
| `DATABASE_NAME` | Database name. For SQLite, the path of the database file (default `higeo.sqlite3`). |
| `DATABASE_HOST` | Database host (default `localhost`). Not used by SQLite. |
| `DATABASE_PORT` | Database port (default 5432 for PostgreSQL, 3306 for MySQL). Not used by SQLite. |
| `DATABASE_USER` | Database username. Not used by SQLite. |
| `DATABASE_PASSWORD` | Database password. Not used by SQLite. |
| `SECRET_KEY` | Random string that signs the session cookie. |

> Upgrading an installation that already uses PostgreSQL: add `DATABASE_ENGINE = postgresql` to its `.env`,
> otherwise the application starts on an empty SQLite database.

## Backups, releases and changing the database engine

| Command | What it does |
|---|---|
| `db_dump [-o FILE] [--keep-days N] [--with-users]` | Backs the database up to one file, by default `backups/<name>_<date>.sql.gz` (SQLite: `.db.gz`). A name ending in `.gz` is compressed. A `.sha256` file is written next to it. The staff accounts (password hashes) are left out unless `--with-users`; `--keep-days` deletes older dumps of this database. |
| `db_restore SOURCE [--force]` | Loads a dump (path or `https` link) into the configured database. It refuses a database that already holds data unless `--force`. A SQLite dump can be loaded into any engine; a SQL dump only into its own. |
| `db_migrate ENGINE [-n NAME -H HOST -P PORT -u USER -p] [--with-users] [--force] [--switch]` | Copies all the records to a database of another engine, creating it. `--switch` then points `.env` at the new database. |
| `db_init [--drop]` | Creates the database and the missing tables; `--drop` deletes all data first. |
| `uploads_pack [-o FILE]` / `uploads_unpack SOURCE` | Packs `static/uploads` into a `.tar.gz` / unpacks one (existing files are kept unless `--overwrite`). |

Dump formats: SQLite is the database file itself, PostgreSQL and MySQL are plain SQL made by `pg_dump` and
`mysqldump` (their client tools must be on the `PATH`). Passwords are passed to them through the environment.

**Publishing a release.** The record of the current state can be published without the uploads and without any
accounts: make one file per engine, then attach them to a GitHub release (an asset must be smaller than 2 GiB; the
commands print a warning otherwise):

```sh
# starting from the database in .env, whatever its engine, copy it into a SQLite file and dump that
uv run manager.py db_migrate sqlite -n /tmp/release.sqlite3
DATABASE_ENGINE=sqlite DATABASE_NAME=/tmp/release.sqlite3 uv run manager.py db_dump -o release/higeo-sqlite.db.gz

# the same data in PostgreSQL and MySQL (scratch databases), dumped as SQL
DATABASE_ENGINE=sqlite DATABASE_NAME=/tmp/release.sqlite3 uv run manager.py db_migrate postgresql -n release -u postgres -p
DATABASE_ENGINE=postgresql DATABASE_NAME=release DATABASE_USER=postgres uv run manager.py db_dump -o release/higeo-postgresql.sql.gz
DATABASE_ENGINE=sqlite DATABASE_NAME=/tmp/release.sqlite3 uv run manager.py db_migrate mysql -n release -u root -p
DATABASE_ENGINE=mysql DATABASE_NAME=release DATABASE_USER=root uv run manager.py db_dump -o release/higeo-mysql.sql.gz

uv run manager.py uploads_pack -o release/uploads.tar.gz               # optional: the uploaded files
```

Because a dump is run by a database client, restore only dumps you trust. `db_restore` runs `psql` in restricted
mode and `mysql` with `--binary-mode`, so a dump cannot start programs through the clients' own commands, but its SQL
still has all the rights of the database user.

**Regular backups**: run `db_dump` from cron, for example every third day at 02:00, keeping 30 days:

```cron
0 2 */3 * * cd /path/to/higeo_is && uv run manager.py db_dump --keep-days 30 >> backups/backup.log 2>&1
```


## Tests

```sh
uv run pytest
```

The tests use a temporary SQLite database. To run them against PostgreSQL or MySQL, point the settings at a
database whose name contains `test` (its tables are dropped and recreated) and set `HIGEO_TEST_DATABASE=configured`:

```sh
DATABASE_ENGINE=postgresql DATABASE_NAME=higeo_test HIGEO_TEST_DATABASE=configured uv run pytest
```

## Contributing

1. **Fork the repository**.
2. **Create a new branch**:
    ```sh
    git checkout -b feature/your-feature-name
    ```
3. **Make your changes**.
4. **Commit your changes**:
    ```sh
    git commit -m 'Add some feature'
    ```
5. **Push to the branch**:
    ```sh
    git push origin feature/your-feature-name
    ```
6. **Open a pull request**.

## License

This project is licensed under the MIT License.
