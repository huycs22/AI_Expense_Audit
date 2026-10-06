import os

# Must happen before feature imports create the SQLAlchemy engine.
# Tests never reconcile/delete the active application's jobs.
os.environ["DATABASE_URL"] = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://expense:expense_local@127.0.0.1:5432/expense_audit_test",
)
