from alembic import context
from db import database, metadata

with database(migrations=True).begin() as connection:
    context.configure(connection=connection, target_metadata=metadata)
    with context.begin_transaction():
        context.run_migrations()
