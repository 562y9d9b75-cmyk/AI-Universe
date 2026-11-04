"""Validate model-authored plans before they can become durable task graphs.

The model may describe work, but organization, provider and spending controls
always come from the existing root task and are never accepted from its output.
"""
import json
import re


class InvalidPlan(ValueError):
    pass


def collaborators(agents, planner_id=None):
    """Only disclose the current organization's permitted, non-planner staff."""
    return [
        {'id': agent.id, 'name': agent.name, 'role': agent.role,
         'skills': list(agent.skills or []),
         'permissions': [p for p in (agent.permissions or []) if p in ('documents', 'analysis')],
         'responsibilities': agent.responsibilities, 'goals': agent.goals}
        for agent in agents
        if agent.id != planner_id and set(agent.permissions or []) & {'documents', 'analysis'}
    ]


def _text(value, label, limit):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise InvalidPlan(f'{label} 必须是非空文本，且不超过 {limit} 字符')
    return value.strip()


def validate_plan(value, available):
    """Return a normalized 2–3-step DAG, with a closed, permission-checked schema."""
    if isinstance(value, str):
        if len(value) > 180000:
            raise InvalidPlan('规划结果超过大小限制')
        try:
            value = json.loads(value)
        except (ValueError, TypeError) as exc:
            raise InvalidPlan('规划必须是严格 JSON，不能包含 Markdown 或附加说明') from exc
    if not isinstance(value, dict) or set(value) != {'steps'}:
        raise InvalidPlan('规划顶层仅允许 steps；不能修改组织、预算或模型提供方')
    steps = value['steps']
    if not isinstance(steps, list) or not 2 <= len(steps) <= 3:
        raise InvalidPlan('规划必须包含 2–3 个子任务')
    staff = {a['id']: a for a in available}
    normalized = []
    keys = set()
    required = {'key', 'title', 'agent_id', 'operation', 'input', 'criteria', 'depends_on'}
    for index, step in enumerate(steps, 1):
        if not isinstance(step, dict) or set(step) != required:
            raise InvalidPlan(f'第 {index} 步字段不完整，或包含未经允许的字段')
        key = _text(step['key'], '步骤 key', 40)
        if not re.fullmatch(r'[a-z][a-z0-9_-]*', key) or key in keys:
            raise InvalidPlan('步骤 key 必须唯一，并使用小写字母、数字、下划线或连字符')
        keys.add(key)
        agent_id = step['agent_id']
        if not isinstance(agent_id, str) or agent_id not in staff:
            raise InvalidPlan('子任务只能交给提供名单中的同组织员工，不能交回规划者')
        operation = step['operation']
        if operation not in ('document', 'analysis'):
            raise InvalidPlan('子任务仅允许 document 或 analysis 操作')
        permission = 'analysis' if operation == 'analysis' else 'documents'
        if permission not in staff[agent_id]['permissions']:
            raise InvalidPlan(f'员工未获得所需工具权限：{permission}')
        deps = step['depends_on']
        if (not isinstance(deps, list) or len(deps) > 2 or
                any(not isinstance(d, str) for d in deps) or len(set(deps)) != len(deps)):
            raise InvalidPlan('depends_on 必须是无重复步骤 key 的数组')
        normalized.append({'key': key, 'title': _text(step['title'], '任务标题', 300),
                           'agent_id': agent_id, 'operation': operation,
                           'input': _text(step['input'], '任务输入', 60000),
                           'criteria': _text(step['criteria'], '验收标准', 20000),
                           'depends_on': list(deps)})
    if len({step['agent_id'] for step in normalized}) < 2:
        raise InvalidPlan('规划需要至少两名不同员工协作，再由 CEO 汇总')
    for step in normalized:
        if step['key'] in step['depends_on'] or any(d not in keys for d in step['depends_on']):
            raise InvalidPlan('任务依赖只能引用其他已定义步骤')
    remaining = {step['key']: set(step['depends_on']) for step in normalized}
    while remaining:
        ready = {key for key, deps in remaining.items() if not deps}
        if not ready:
            raise InvalidPlan('规划中的任务依赖形成循环')
        remaining = {key: deps - ready for key, deps in remaining.items() if key not in ready}
    return {'steps': normalized}


def plan_markdown(title, plan, available):
    names = {a['id']: a['name'] for a in available}
    parts = [f'# {title} · 执行计划',
             '> 这是模型生成并通过结构、员工权限及依赖检查的规划记录；不是最终成果。',
             '子任务完成后，CEO 将读取真实交接记录并生成最终交付，最终成果再进入审批。']
    for step in plan['steps']:
        parts.extend([f"## {step['key']} · {step['title']}",
                      f"员工：{names[step['agent_id']]}；操作：{step['operation']}",
                      '依赖：' + ('、'.join(step['depends_on']) or '无，可并行执行'),
                      '### 输入', step['input'], '### 验收标准', step['criteria']])
    return '\n\n'.join(parts) + '\n'
