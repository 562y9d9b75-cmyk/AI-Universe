"""Initial versioned schema migration; future migrations must be additive."""
from sqlalchemy import text
from .db import engine,Base
def migrate():
    with engine.begin() as c:
        if engine.dialect.name=='postgresql':c.execute(text('SELECT pg_advisory_xact_lock(19840219)'))
        c.execute(text('CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at VARCHAR(40) NOT NULL)'))
        versions={r[0] for r in c.execute(text('SELECT version FROM schema_migrations'))}
        if 1 not in versions:
            Base.metadata.create_all(c)
            c.execute(text('INSERT INTO schema_migrations VALUES (1,CURRENT_TIMESTAMP)'))
if __name__=='__main__':migrate();print('Schema migration 1 applied/verified')
