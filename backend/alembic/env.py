from logging.config import fileConfig

from alembic import context
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

from app import models  # noqa: F401  (registers tables on Base.metadata)
from app.db import Base, engine

if context.config.config_file_name is not None:
    fileConfig(context.config.config_file_name)

target_metadata = Base.metadata

# Our migrations are tracked in their own table, so they can share a database with another
# branch's Alembic history (the shared Supabase also has `alembic_version`, owned by a
# teammate's branch). Neither history overwrites the other.
VERSION_TABLE = "alembic_version_triage"
LEGACY_TABLE = "alembic_version"
BASE_REVISION = "0001"


def adopt_existing_database(connection) -> None:
    """First run against a database that has no VERSION_TABLE yet:
    - legacy table holds one of OUR revisions (older local DBs) -> continue from it;
    - our base tables exist but the legacy revision is someone else's -> start from 0001;
    - empty database -> do nothing, Alembic creates everything."""
    db = inspect(connection)
    if not db.has_table(VERSION_TABLE):
        ours = {rev.revision for rev in ScriptDirectory.from_config(context.config).walk_revisions()}
        legacy = connection.execute(text(f"select version_num from {LEGACY_TABLE}")).scalar() if db.has_table(LEGACY_TABLE) else None
        start = legacy if legacy in ours else BASE_REVISION if db.has_table("tickets") else None
        if start:
            connection.execute(text(f"create table {VERSION_TABLE} (version_num varchar(32) not null primary key)"))
            connection.execute(text(f"insert into {VERSION_TABLE} (version_num) values (:v)"), {"v": start})
    # Always end the implicit transaction the checks above opened; otherwise Alembic's own
    # transaction nests inside it and the migrations are rolled back when the connection closes.
    connection.commit()


def run_migrations_offline() -> None:
    context.configure(url=str(engine.url), target_metadata=target_metadata, literal_binds=True,
                      version_table=VERSION_TABLE)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    with engine.connect() as connection:
        adopt_existing_database(connection)
        context.configure(connection=connection, target_metadata=target_metadata, version_table=VERSION_TABLE,
                          include_name=lambda name, type_, parent: not (type_ == "table" and name in {LEGACY_TABLE, VERSION_TABLE}))
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
