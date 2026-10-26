"""Candidate migration environment, independent of the team's Alembic env.py."""
from alembic import context
from sqlalchemy import create_engine, pool
from sqlmodel import SQLModel

from app.candidate import model as candidate_model  # noqa: F401
from app.users import model as user_model  # noqa: F401
from app.core.config import settings

options = dict(target_metadata=SQLModel.metadata, compare_type=True)
if context.is_offline_mode():
    context.configure(url=settings.DATABASE_URL, literal_binds=True, **options)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(settings.DATABASE_URL, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, **options)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()
