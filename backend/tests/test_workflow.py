"""Model orchestration acceptance using a fake authorized provider, never Plus.

Exercises the real scheduler, job boundary, durable DAG, file writer and fenced
commits against an isolated database. No network or model credential is used.
"""
import copy
import json
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app import files, job, runtime
from app.db import (Base, Organization, Agent, Task, TaskRun, TaskDependency,
                    UsageRecord, Artifact, Approval, AgentMessage)
from app.providers import AuthorizationRequired, QuotaExhausted
from app.workflow import InvalidPlan, validate_plan


def sample_plan(staff, sequential=True):
    return {'steps': [
        {'key': 'research', 'title': '整理用户提供材料', 'agent_id': staff[0]['id'],
         'operation': 'document', 'input': '根据原始材料列出事实和缺失信息',
         'criteria': '逐条标记来源和未核实内容', 'depends_on': []},
        {'key': 'analysis', 'title': '复核并分析材料', 'agent_id': staff[1]['id'],
         'operation': 'analysis', 'input': '复核输入并统计关键数据',
         'criteria': '保留可复核计算与材料交接',
         'depends_on': ['research'] if sequential else []}]}


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    engine = create_engine('sqlite:///' + str(tmp_path / 'workflow.db'))
    Base.metadata.create_all(engine)
    session = sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(runtime, 'Session', session)
    monkeypatch.setattr(files, 'DATA', tmp_path)
    monkeypatch.setattr(runtime, 'notify', lambda *_: None)
    with session.begin() as s:
        org = Organization(name='编排验收公司', settings={
            'daily_limit': 100, 'concurrency': 3, 'max_rounds': 5, 'timeout': 30})
        other = Organization(name='隔离公司')
        s.add_all([org, other]); s.flush()
        agents = [Agent(organization_id=org.id, name=name, role=role,
                        skills=['资料审查'], permissions=permissions)
                  for name, role, permissions in [
                      ('林远', 'AI CEO', ['documents']),
                      ('沈知夏', '市场研究员', ['documents']),
                      ('周予安', '数据分析师', ['documents', 'analysis'])]]
        outsider = Agent(organization_id=other.id, name='其他组织员工', role='分析师',
                         permissions=['documents', 'analysis'])
        s.add_all([*agents, outsider]); s.flush()
        root = Task(organization_id=org.id, title='三人协作目标',
                    input='name,sales\nA,10\nB,20', criteria='汇总真实交接材料',
                    agent_id=agents[0].id, operation='plan', provider='chatgpt_plan',
                    max_calls=6, review_required=1, formats=['md', 'docx'])
        s.add(root); s.flush()
        values = dict(org=org.id, other=other.id, root=root.id,
                      agents=[a.id for a in agents], outsider=outsider.id)
    yield SimpleNamespace(session=session, data=tmp_path, **values)
    engine.dispose()


def install_provider(monkeypatch, plan_factory=sample_plan):
    class FakeProvider:
        calls = []
        last_usage = {}

        def execute(self, context, operation):
            self.calls.append((context, operation))
            self.last_usage = {'model': 'mock-authorized-model', 'input_tokens': 11,
                               'output_tokens': 7, 'total_tokens': 18,
                               'response_id': 'mock-completed-response'}
            if operation == 'plan':
                return json.dumps(plan_factory(context.collaborators), ensure_ascii=False)
            return '# 已完成的模拟模型工作\n\n' + context.source + '\n\n验收：' + context.criteria

    provider = FakeProvider()
    monkeypatch.setitem(job.PROVIDERS, 'chatgpt_plan', provider)

    class InProcessJob:
        """Exercise serialized job input/output without creating a real model process."""
        returncode = 0

        def __init__(self, *args, **kwargs):
            pass

        def communicate(self, payload, timeout):
            assert timeout > 0
            return json.dumps(job.run_job(json.loads(payload)), ensure_ascii=False), ''

    monkeypatch.setattr(runtime.subprocess, 'Popen', InProcessJob)
    return provider


def test_plan_rejects_unsafe_or_incomplete_graphs():
    staff = [{'id': 'one', 'permissions': ['documents']},
             {'id': 'two', 'permissions': ['documents', 'analysis']}]
    valid = sample_plan(staff)
    assert validate_plan(json.dumps(valid), staff) == valid
    invalid = []
    value = copy.deepcopy(valid); value['organization_id'] = 'other'; invalid.append(value)
    value = copy.deepcopy(valid); value['steps'][0]['budget_cents'] = 999; invalid.append(value)
    value = copy.deepcopy(valid); value['steps'][0]['agent_id'] = 'outsider'; invalid.append(value)
    value = copy.deepcopy(valid); value['steps'][0]['operation'] = 'shell'; invalid.append(value)
    value = copy.deepcopy(valid); value['steps'][0]['operation'] = 'analysis'; invalid.append(value)
    value = copy.deepcopy(valid); value['steps'][1]['key'] = 'research'; invalid.append(value)
    value = copy.deepcopy(valid); value['steps'][0]['depends_on'] = ['analysis']; invalid.append(value)
    value = copy.deepcopy(valid); value['steps'][0]['depends_on'] = ['missing']; invalid.append(value)
    value = copy.deepcopy(valid); value['steps'][0]['input'] = ''; invalid.append(value)
    value = copy.deepcopy(valid); value['steps'] = value['steps'][:1]; invalid.append(value)
    value = copy.deepcopy(valid); value['steps'][1].update(agent_id='one', operation='document'); invalid.append(value)
    invalid.append('```json\n' + json.dumps(valid) + '\n```')
    for value in invalid:
        with pytest.raises(InvalidPlan):
            validate_plan(value, staff)


def test_authorized_mock_plan_dag_handoff_final_review_and_usage(workspace, monkeypatch):
    provider = install_provider(monkeypatch)
    planning = runtime.claim()
    assert planning['operation'] == 'plan'
    assert planning['context'].organization_id == workspace.org
    assert {a['id'] for a in planning['context'].collaborators} == set(workspace.agents[1:])
    assert all('skills' in a and 'permissions' in a for a in planning['context'].collaborators)
    runtime.execute(planning)
    with workspace.session() as s:
        root = s.get(Task, workspace.root)
        assert root.status == 'queued' and root.operation == 'document' and root.output == ''
        children = list(s.scalars(select(Task).where(Task.parent_id == root.id)))
        assert len(children) == 2 and all(c.review_required == 0 for c in children)
        assert {root.agent_id, *(c.agent_id for c in children)} == set(workspace.agents)
        assert all(c.organization_id == workspace.org and c.provider == root.provider
                   and c.max_calls == root.max_calls for c in children)
        assert list(s.scalars(select(Approval))) == []
        planning_file = s.scalar(select(Artifact).where(Artifact.task_id == root.id))
        assert '执行计划' in planning_file.name and planning_file.format == 'md'
        assert Path(planning_file.path).read_text().startswith('# 三人协作目标 · 执行计划')
    first = runtime.claim(); assert first['operation'] == 'document'
    assert runtime.claim() is None  # Second child is serial and final CEO is waiting.
    runtime.execute(first)
    second = runtime.claim(); assert second['operation'] == 'analysis'
    assert '[上游任务 整理用户提供材料]' in second['context'].source
    runtime.execute(second)
    final = runtime.claim(); assert final['task_id'] == workspace.root
    assert '你负责最终汇总' in final['context'].role_instructions
    assert '[上游任务 复核并分析材料]' in final['context'].source
    runtime.execute(final)
    with workspace.session() as s:
        root = s.get(Task, workspace.root)
        assert root.status == 'review' and root.attempts == 2
        assert len(list(s.scalars(select(TaskRun)))) == 4
        usage = list(s.scalars(select(UsageRecord)))
        assert len(usage) == 4 and all(u.status == 'succeeded' and u.metrics['total_tokens'] == 18 for u in usage)
        assert sum(u.units for u in usage) == 4 and all(u.cost_cents == 0 for u in usage)
        approvals = list(s.scalars(select(Approval)))
        assert len(approvals) == 1 and approvals[0].run_id == final['run_id']
        root_artifacts = list(s.scalars(select(Artifact).where(Artifact.task_id == root.id)))
        assert len(root_artifacts) == 3  # MD planning record + final MD/DOCX.
        assert all(Path(a.path).is_file() for a in root_artifacts)
        messages = list(s.scalars(select(AgentMessage)))
        assert len(messages) == 3 and all(m.artifact_ids for m in messages)
    assert [operation for _, operation in provider.calls] == ['plan', 'document', 'analysis', 'document']


@pytest.mark.parametrize('exception,state', [
    (AuthorizationRequired('需要用户官方授权'), 'blocked_auth'),
    (QuotaExhausted('计划额度用尽'), 'paused_quota')])
def test_plan_never_fabricates_work_on_auth_or_quota_failure(workspace, monkeypatch, exception, state):
    provider = install_provider(monkeypatch)

    def denied(*_):
        raise exception

    monkeypatch.setattr(provider, 'execute', denied)
    runtime.execute(runtime.claim())
    with workspace.session() as s:
        assert s.get(Task, workspace.root).status == state
        assert len(list(s.scalars(select(Task)))) == 1
        assert list(s.scalars(select(Artifact))) == []
        assert list(s.scalars(select(Approval))) == []
    assert runtime.claim() is None


def test_plan_commit_is_fenced_and_revalidates_employee_permission(workspace, monkeypatch):
    install_provider(monkeypatch)
    old = runtime.claim()
    with workspace.session.begin() as s:
        root = s.get(Task, workspace.root)
        root.status = 'paused'; root.active_run_id = None
    runtime.execute(old)
    with workspace.session() as s:
        assert len(list(s.scalars(select(Task)))) == 1
        assert list(s.scalars(select(Artifact))) == []
    with workspace.session.begin() as s:
        root = s.get(Task, workspace.root); root.status = 'queued'
    current = runtime.claim()
    # An administrator revokes permission after the model request was started.
    with workspace.session.begin() as s:
        s.get(Agent, workspace.agents[2]).permissions = ['documents']
    runtime.execute(current)
    with workspace.session() as s:
        root = s.get(Task, workspace.root)
        assert root.operation == 'plan' and root.status == 'queued'
        assert '权限' in root.error
        assert len(list(s.scalars(select(Task)))) == 1
        assert list(s.scalars(select(Artifact))) == []


def test_plan_children_and_final_share_total_budget(workspace, monkeypatch):
    install_provider(monkeypatch)
    with workspace.session.begin() as s:
        s.get(Task, workspace.root).max_calls = 3
    for _ in range(6):
        claimed = runtime.claim()
        if claimed: runtime.execute(claimed)
    with workspace.session() as s:
        root = s.get(Task, workspace.root)
        assert root.status == 'paused_budget' and '总执行上限' in root.error
        assert len(list(s.scalars(select(UsageRecord)))) == 3
        assert list(s.scalars(select(Approval))) == []


def test_parallel_plan_concurrency_daily_quota_and_crash_recovery(workspace, monkeypatch):
    install_provider(monkeypatch, lambda staff: sample_plan(staff, sequential=False))
    runtime.execute(runtime.claim())
    with workspace.session.begin() as s:
        org = s.get(Organization, workspace.org)
        org.settings = {**org.settings, 'concurrency': 1}
    interrupted = runtime.claim()
    assert runtime.claim() is None
    with workspace.session.begin() as s:
        s.get(Task, interrupted['task_id']).lease_until = time.time() - 1
    recovered = runtime.claim()
    assert recovered['task_id'] == interrupted['task_id'] and recovered['run_id'] != interrupted['run_id']
    runtime.execute(interrupted)  # Late old result cannot create artifacts or complete work.
    runtime.execute(recovered)
    with workspace.session.begin() as s:
        org = s.get(Organization, workspace.org)
        org.settings = {**org.settings, 'daily_limit': 3}
    assert runtime.claim() is None
    with workspace.session() as s:
        assert s.get(TaskRun, interrupted['run_id']).status == 'interrupted'
        assert s.get(Task, workspace.root).status == 'paused_budget'
        assert len(list(s.scalars(select(UsageRecord)))) == 3
        assert list(s.scalars(select(Approval))) == []
