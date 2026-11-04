"""Versioned, additive schema and conservative legacy-data migrations."""
from sqlalchemy import text,inspect
from sqlalchemy import select
from sqlalchemy.orm import Session as MigrationSession
from .db import engine,Base,Agent
from .appearance import DEFAULT_EMPLOYEES, default_appearance

def migrate_employee_profiles(connection):
    """Only migrate original seed markers; retain user names and custom visuals."""
    with MigrationSession(bind=connection) as s:
        for agent in s.scalars(select(Agent)):
            appearance=agent.appearance if isinstance(agent.appearance,dict) else {}
            index=appearance.get('index')
            if type(index) is not int or not 0<=index<len(DEFAULT_EMPLOYEES):continue
            default=DEFAULT_EMPLOYEES[index]
            if agent.role!=default['role']:continue
            # index+original role is the old seed provenance. A renamed employee
            # still receives its original portrait, but keeps its edited name.
            if agent.name==default['legacy_name']:agent.name=default['name']
            if set(appearance)=={'index'}:agent.appearance=default_appearance(default['portrait_id'],index)
        s.flush()

def migrate_usage_metrics(connection):
    if 'metrics' not in {c['name'] for c in inspect(connection).get_columns('usage_records')}:
        # Both SQLite and PostgreSQL accept JSON with an empty-object default.
        # Existing records retain their IDs, task links, costs and counters.
        connection.execute(text("ALTER TABLE usage_records ADD COLUMN metrics JSON NOT NULL DEFAULT '{}'"))

def migrate():
    with engine.begin() as c:
        if engine.dialect.name=='postgresql':c.execute(text('SELECT pg_advisory_xact_lock(19840219)'))
        c.execute(text('CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at VARCHAR(40) NOT NULL)'))
        versions={r[0] for r in c.execute(text('SELECT version FROM schema_migrations'))}
        if 1 not in versions:
            Base.metadata.create_all(c)
            c.execute(text('INSERT INTO schema_migrations VALUES (1,CURRENT_TIMESTAMP)'))
        if 2 not in versions:
            migrate_employee_profiles(c)
            c.execute(text('INSERT INTO schema_migrations VALUES (2,CURRENT_TIMESTAMP)'))
        if 3 not in versions:
            migrate_usage_metrics(c)
            c.execute(text('INSERT INTO schema_migrations VALUES (3,CURRENT_TIMESTAMP)'))
if __name__=='__main__':migrate();print('Schema migrations 1–3 applied/verified')
