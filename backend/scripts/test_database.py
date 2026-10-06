"""Create/migrate an isolated PostgreSQL database for integration tests."""

import os

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.core.config import ROOT, get_settings

url = make_url(get_settings().database_url.get_secret_value())
test_url = url.set(database="expense_audit_test")
admin = create_engine(
    url.set(database="postgres"), isolation_level="AUTOCOMMIT", connect_args={"connect_timeout": 5}
)
with admin.connect() as connection:
    if not connection.scalar(
        text("SELECT 1 FROM pg_database WHERE datname = 'expense_audit_test'")
    ):
        connection.execute(text("CREATE DATABASE expense_audit_test"))
admin.dispose()
os.environ["DATABASE_URL"] = test_url.render_as_string(hide_password=False)
get_settings.cache_clear()
command.upgrade(Config(str(ROOT / "backend" / "alembic.ini")), "head")
print("Isolated PostgreSQL test database ready")
