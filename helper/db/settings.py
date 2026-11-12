"""Where a database is and how to reach it. Unlike the constants in `helper`, any number of these can exist at once,
which is what copying from one database to another needs."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import URL, Engine, create_engine


class TransferError(ValueError):
    """A dump, restore or copy that cannot be done; the message says why, for the administrator."""


DATABASE_ENGINES = ("sqlite", "postgresql", "mysql")
DEFAULT_PORTS = {"postgresql": "5432", "mysql": "3306"}
DEFAULT_NAMES = {"sqlite": "higeo.sqlite3", "postgresql": "higeo", "mysql": "higeo"}
DRIVERS = {"sqlite": "sqlite", "postgresql": "postgresql+psycopg2", "mysql": "mysql+pymysql"}


@dataclass(frozen=True)
class DatabaseSettings:
    engine: str
    name: str
    host: str = "localhost"
    port: str | None = None
    user: str | None = None
    password: str | None = None

    @classmethod
    def from_config(cls) -> DatabaseSettings:
        """The database that the application itself uses (from `.env` and the environment)."""
        import helper

        return cls(
            helper.DATABASE_ENGINE,
            helper.DATABASE_NAME,
            helper.DATABASE_HOST,
            helper.DATABASE_PORT,
            helper.DATABASE_USER,
            helper.DATABASE_PASSWORD,
        )

    @classmethod
    def sqlite_file(cls, path: str) -> DatabaseSettings:
        return cls("sqlite", str(path))

    @property
    def effective_port(self) -> str | None:
        return self.port or DEFAULT_PORTS.get(self.engine)

    def url(self, database: str | None = None) -> URL:
        """The connection URL, for `database` instead of this one's own (for example the maintenance database)."""
        database = self.name if database is None else database
        if self.engine == "sqlite":
            return URL.create(DRIVERS["sqlite"], database=database)
        return URL.create(
            DRIVERS[self.engine],
            username=self.user,
            password=self.password,
            host=self.host,
            port=int(self.port) if self.port else None,
            database=database,
            query={"charset": "utf8mb4"} if self.engine == "mysql" else {},
        )

    def make_engine(self, **kwargs) -> Engine:
        return create_engine(self.url(), pool_pre_ping=True, **kwargs)

    def describe(self) -> str:
        """For messages. Never contains the password."""
        if self.engine == "sqlite":
            return f"sqlite file {self.name}"
        return f"{self.engine} database {self.name} on {self.host}:{self.effective_port}"
