from alembic import context

from app.core import models  # noqa: F401
from app.core.database import Base, engine

if context.is_offline_mode():
    from app.core.config import get_settings

    context.configure(
        url=get_settings().database_url.get_secret_value(),
        target_metadata=Base.metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()
