"""Character validation and upgrades must preserve owner-authored data."""
import pytest
from pydantic import ValidationError

from app.appearance import DEFAULT_EMPLOYEES, default_appearance, normalize_appearance


@pytest.mark.parametrize('payload', [
    {'avatar_url': 'https://example.com/portrait.png'},
    {'avatar_url': '/assets/portraits/../../private.png'},
    {'avatar_url': 'data:image/png;base64,123'},
    {'portrait_id': 'missing-person'},
    {'portrait_id': 'lin-yuan', 'avatar_url': '/assets/portraits/shen-zhixia.png'},
    {'portrait_id': 'lin-yuan', 'character_profile': {'nationality': 'GB'}},
    {'portrait_id': 'olivia-morgan', 'character_profile': {'skills': ['admin']}},
    {'portrait_id': 'lin-yuan', 'character_profile': {'age_range': 'child'}},
    {'portrait_id': 'lin-yuan', 'index': True},
    {'character_profile': None},
    {}, None, [],
])
def test_untrusted_character_configuration_is_rejected(payload):
    with pytest.raises((ValidationError, ValueError)):
        normalize_appearance(payload)


def test_migration_preserves_names_custom_appearance_history_and_other_organizations():
    # A separate in-memory database never touches the runtime or owner's DB.
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session
    from app.db import Base, Agent, Organization, Task
    from app.migrate import migrate_employee_profiles

    isolated = create_engine('sqlite://')
    Base.metadata.create_all(isolated)
    with isolated.begin() as connection:
        with Session(bind=connection) as s:
            for org_id in ['first', 'second']:
                s.add(Organization(id=org_id, name=org_id))
                for i, preset in enumerate(DEFAULT_EMPLOYEES):
                    name = '老板自定义姓名' if i == 1 else preset['legacy_name']
                    s.add(Agent(id=org_id + str(i), organization_id=org_id, name=name,
                                role=preset['role'], appearance={'index': i}))
            custom_visual = {'index': 2, 'avatar_url': '/owner-original-portrait.png'}
            s.add(Agent(id='custom', organization_id='first', name='另一个员工',
                        role='数据分析师', appearance=custom_visual))
            s.add(Agent(id='nonseed', organization_id='first', name='Atlas', role='AI CEO'))
            s.add(Agent(id='changed-role', organization_id='first', name='Emma',
                        role='自定义岗位', appearance={'index': 1}))
            s.add(Task(id='history', organization_id='first', agent_id='first0', title='历史任务'))
            s.flush()
        migrate_employee_profiles(connection)
        migrate_employee_profiles(connection)
        with Session(bind=connection) as s:
            for org_id in ['first', 'second']:
                for i, preset in enumerate(DEFAULT_EMPLOYEES):
                    row = s.get(Agent, org_id + str(i))
                    assert row.name == ('老板自定义姓名' if i == 1 else preset['name'])
                    assert row.appearance == default_appearance(preset['portrait_id'], i)
            assert s.get(Agent, 'custom').appearance == custom_visual
            assert s.get(Agent, 'nonseed').name == 'Atlas'
            assert s.get(Agent, 'changed-role').name == 'Emma'
            assert s.get(Task, 'history').agent_id == 'first0'
            assert len(list(s.scalars(select(Agent)))) == 19
    isolated.dispose()


def test_usage_metrics_upgrade_keeps_existing_call_records_and_is_repeatable():
    from sqlalchemy import create_engine, text
    from app.migrate import migrate_usage_metrics

    isolated = create_engine('sqlite://')
    with isolated.begin() as connection:
        connection.execute(text('CREATE TABLE usage_records (id TEXT PRIMARY KEY, task_id TEXT, cost_cents INTEGER)'))
        connection.execute(text("INSERT INTO usage_records VALUES ('previous-call','previous-task',7)"))
        migrate_usage_metrics(connection)
        migrate_usage_metrics(connection)
        row = connection.execute(text('SELECT id,task_id,cost_cents,metrics FROM usage_records')).one()
        assert tuple(row) == ('previous-call', 'previous-task', 7, '{}')
    isolated.dispose()
