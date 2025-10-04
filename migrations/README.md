# Database Migrations

This directory houses Alembic configuration for managing schema changes. Use the `alembic` CLI to generate revisions and apply upgrades/downgrades.

## Quickstart

```powershell
# Activate the project virtualenv first
.venv\Scripts\activate

# Create a new revision
alembic revision -m "<message>"

# Apply migrations
alembic upgrade head

# Roll back last migration
alembic downgrade -1
```

The Alembic environment is configured to share metadata with `infrastructure.database.database.Base`, so revisions will reflect the FastAPI models automatically when using `--autogenerate`.
