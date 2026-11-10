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

3. **Choose the database**. SQLite, PostgreSQL and MySQL are supported. The choice is stored in the `.env` file by `manager.py`:
    ```sh
    uv run manager.py db_set sqlite                                   # the default: a higeo.sqlite3 file, no server needed
    uv run manager.py db_set sqlite --name /path/to/file.sqlite3
    uv run manager.py db_set postgresql --name higeo --user postgres -p   # -p prompts for the password
    uv run manager.py db_set mysql --name higeo --user root --host localhost --port 3306 -p
    uv run manager.py db_show                                         # print the current settings
    ```
    Without any configuration the application uses SQLite and the file `higeo.sqlite3`.

4. **Create the database and its tables** (PostgreSQL and MySQL must be installed and running):
    ```sh
    sh quicksetup.sh
    ```

5. **Set a secret key**, which signs the login cookie. Add a random string to `.env`:
    ```env
    SECRET_KEY = ...
    ```
    Without it a new key is generated on every start, which logs everyone out.

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

The `pg_backup.sh` scripts only work with PostgreSQL.

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
