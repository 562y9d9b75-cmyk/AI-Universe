"""Isolated API + real scheduler/files tests, never touching the owner's database."""
import os,tempfile,time,zipfile
from pathlib import Path
TEST_DIR=os.environ['AIU_DATA_DIR']
from fastapi.testclient import TestClient
from sqlalchemy import select,func
from app.main import app
from app.runtime import claim,execute
from app.db import Session,Task,TaskRun,UsageRecord,Artifact

client=TestClient(app,headers={'X-AIU-Request':'1'})
def ok(r,code=200):assert r.status_code==code,r.text;return r.json()
def drive(limit=30):
    for _ in range(limit):
        j=claim()
        if not j:break
        execute(j)
def task(**kw):return ok(client.post('/api/tasks',json={'title':'验收任务','input':'name,sales\nA,10\nB,20','criteria':'保留输入并可打开文件','review_required':True,**kw}))
def rows(name):return ok(client.get('/api/'+name))

def test_01_auth_and_workspace():
    from app.migrate import migrate
    migrate()
    ok(client.get('/api/agents'),401)
    ok(client.post('/api/auth/bootstrap',json={'username':'owner','password':'strong-test-password','company':'验收公司'}))
    assert len(rows('agents'))==8
    assert len(rows('departments'))==5
    ok(client.post('/api/auth/bootstrap',json={'username':'other','password':'strong-test-password'}),409)
    assert 'password_hash' not in ok(client.get('/api/me'))

def test_02_organization_department_employee_project():
    department=ok(client.post('/api/departments',json={'name':'法律部'}))
    a=ok(client.post('/api/agents/from-description',json={'description':'创建员工 Iris，岗位：法律顾问，负责合同审查'}))
    ok(client.patch('/api/agents/'+a['id'],json={'department_id':department['id'],'goals':'审核合同','permissions':['documents']}))
    ok(client.patch('/api/agents/'+a['id'],json={'manager_id':a['id']}),422)
    ok(client.patch('/api/agents/'+a['id'],json={'permissions':['shell']}),422)
    p=ok(client.post('/api/projects',json={'name':'验收项目'}))
    t=task(project_id=p['id'],agent_id=a['id']);drive()
    assert next(x for x in rows('tasks') if x['id']==t['id'])['status']=='review'

def test_03_parallel_handoff_all_real_formats_review_reject_versions():
    root=task(mode='autonomous',formats=['md','docx','xlsx','pptx','pdf','py','html','zip'])
    j1=claim();j2=claim()
    assert j1 and j2 and j1['task_id']!=j2['task_id']
    assert claim() is None # final depends on two real completed child jobs
    execute(j2);assert claim() is None
    execute(j1);drive()
    detail=ok(client.get('/api/tasks/'+root['id']+'/detail'))
    assert detail['status']=='review'
    assert len(detail['dependencies'])==2
    assert len(detail['messages'])==2
    assert all(m['artifact_ids'] for m in detail['messages'])
    assert len({t['agent_id'] for t in rows('tasks') if t['id']==root['id'] or t['parent_id']==root['id']})==3
    assert len(detail['artifacts'])==8
    for a in detail['artifacts']:
        r=client.get('/api/artifacts/'+a['id']+'/download');assert r.status_code==200
        if a['format']=='pdf':assert r.content.startswith(b'%PDF')
        elif a['format'] in ['docx','xlsx','pptx','zip']:
            import io
            z=zipfile.ZipFile(io.BytesIO(r.content));assert z.testzip() is None
        else:assert len(r.content)>100
    approval=next(a for a in rows('approvals') if a['task_id']==root['id'] and a['status']=='pending')
    ok(client.post('/api/approvals/'+approval['id']+'/review',json={'decision':'reject','feedback':'请保留原始数据并补充修改意见'}))
    drive()
    newer=ok(client.get('/api/tasks/'+root['id']+'/detail'))
    assert len(newer['artifacts'])==16
    assert {a['version'] for a in newer['artifacts']}=={1,2}
    a=next(a for a in rows('approvals') if a['task_id']==root['id'] and a['status']=='pending')
    ok(client.post('/api/approvals/'+a['id']+'/review',json={'decision':'approve'}))
    ok(client.post('/api/approvals/'+a['id']+'/review',json={'decision':'approve'}),409)

def test_04_permissions_budget_auth_and_daily_pause():
    t=task(max_calls=0);drive()
    assert next(x for x in rows('tasks') if x['id']==t['id'])['status']=='paused_budget'
    t=task(provider='chatgpt_plan');drive()
    assert next(x for x in rows('tasks') if x['id']==t['id'])['status']=='blocked_auth'
    assert all(u['cost_cents']==0 for u in rows('usage_records'))
    ok(client.patch('/api/organization',json={'settings':{'daily_limit':0}}))
    t=task();drive();assert next(x for x in rows('tasks') if x['id']==t['id'])['status']=='paused_budget'
    ok(client.patch('/api/organization',json={'settings':{'daily_limit':1000}}))
    ok(client.post('/api/tasks/'+t['id']+'/resume'));drive()
    assert next(x for x in rows('tasks') if x['id']==t['id'])['status']=='review'

def test_05_pause_fencing_crash_recovery_and_timeout():
    t=task(review_required=False)
    old=claim();assert old['task_id']==t['id']
    ok(client.post('/api/tasks/'+t['id']+'/pause'))
    execute(old)
    assert not [a for a in rows('artifacts') if a['task_id']==t['id']]
    ok(client.post('/api/tasks/'+t['id']+'/resume'))
    new=claim()
    with Session.begin() as s:s.get(Task,t['id']).lease_until=time.time()-1
    recovered=claim();assert recovered['task_id']==t['id'] and recovered['run_id']!=new['run_id']
    execute(new);execute(recovered)
    details=ok(client.get('/api/tasks/'+t['id']+'/detail'))
    assert details['status']=='completed'
    assert any(r['status']=='interrupted' for r in details['runs'])
    assert len(details['artifacts'])==1

def test_06_memory_scope_delete_and_organization_isolation():
    marker='Verified private source 82731'
    memory=ok(client.post('/api/memories',json={'scope':'company','content':marker,'source':'用户验收材料','verified':True}))
    unverified=ok(client.post('/api/memories',json={'scope':'company','content':'UNVERIFIED 6733','source':'推断','verified':False}))
    t=task();drive();details=ok(client.get('/api/tasks/'+t['id']+'/detail'))
    assert marker in details['runs'][0]['input'] and 'UNVERIFIED 6733' not in details['runs'][0]['input']
    ok(client.delete('/api/memories/'+memory['id']))
    old_agent=rows('agents')[0];old_task=t['id']
    ok(client.post('/api/organizations',json={'name':'隔离公司'}))
    assert rows('tasks')==[]
    ok(client.get('/api/tasks/'+old_task+'/detail'),404)
    ok(client.post('/api/tasks',json={'title':'非法引用','agent_id':old_agent['id']}),404)
    ok(client.patch('/api/agents/'+old_agent['id'],json={'name':'不能改'}),404)
    ok(client.post('/api/tasks',json={'title':'无效提供方','provider':'paid_api'}),422)
    ok(client.post('/api/memories',json={'scope':'employee','content':'x','source':'x'}),422)
    ok(client.patch('/api/organization',json={'settings':{'concurrency':999}}),422)

def test_07_security_boundaries():
    ok(client.post('/api/departments',json={'name':'CSRF'},headers={'X-AIU-Request':'0'}),403)
    ok(client.post('/api/departments',json={'name':'CSRF'},headers={'Origin':'https://evil.example'}),403)
    ok(client.patch('/api/agents/'+rows('agents')[0]['id'],json={'organization_id':'injection'}),422)
    assert client.get('/api/agents').headers['x-content-type-options']=='nosniff'

def test_08_hard_timeout_and_concurrency():
    ok(client.patch('/api/organization',json={'settings':{'concurrency':1}}))
    a=task(title='超时执行',max_calls=1,review_required=False)
    b=task(title='并发限额',review_required=False)
    job=claim();assert job['task_id']==a['id']
    assert claim() is None
    # Exhaust an actual lease before a Python tool subprocess can complete startup.
    with Session.begin() as s:s.get(Task,a['id']).lease_until=time.time()+.01
    job['lease']=time.time()+.01
    execute(job)
    details=ok(client.get('/api/tasks/'+a['id']+'/detail'))
    assert details['status']=='failed' and '超时' in details['error']
    assert details['artifacts']==[]
    drive();assert ok(client.get('/api/tasks/'+b['id']+'/detail'))['status']=='completed'

def test_09_collaboration_parent_pause_and_resume():
    ok(client.patch('/api/organization',json={'settings':{'concurrency':3}}))
    root=task(title='协作暂停恢复',mode='autonomous',review_required=False)
    job=claim();assert job
    ok(client.post('/api/tasks/'+root['id']+'/pause'))
    execute(job)
    group=[t for t in rows('tasks') if t['parent_id']==root['id'] or t['id']==root['id']]
    assert all(t['status']=='paused' for t in group)
    assert claim() is None
    ok(client.post('/api/tasks/'+root['id']+'/resume'));drive()
    assert ok(client.get('/api/tasks/'+root['id']+'/detail'))['status']=='completed'

def test_10_sqlite_worker_lock_prevents_duplicate_processes():
    import subprocess,sys
    from app.db import ROOT
    from app.runtime import acquire_worker_lock
    lock=acquire_worker_lock()
    try:
        r=subprocess.run([sys.executable,'-c','from app.runtime import acquire_worker_lock; lock=acquire_worker_lock()'],cwd=ROOT/'backend',capture_output=True,text=True)
        assert r.returncode!=0 and '已有工作进程' in r.stderr
    finally:lock.close()
    r=subprocess.run([sys.executable,'-c','from app.runtime import acquire_worker_lock; lock=acquire_worker_lock()'],cwd=ROOT/'backend',capture_output=True,text=True)
    assert r.returncode==0,r.stderr

def test_11_editable_names_portraits_and_appearance_api_boundaries():
    from app.appearance import DEFAULT_EMPLOYEES
    from app.main import app
    from app.migrate import migrate
    catalog=ok(client.get('/api/appearance/catalog'))
    assert len(catalog['portraits'])==10
    assert {p['character_profile']['nationality'] for p in catalog['portraits']}=={'CN','GB','FR'}
    anon=TestClient(app,headers={'X-AIU-Request':'1'})
    assert anon.get('/api/appearance/catalog').status_code==401
    employees=rows('agents')
    assert {a['name'] for a in employees}=={p['name'] for p in DEFAULT_EMPLOYEES}
    assert len({a['appearance']['avatar_url'] for a in employees})==8
    employee=next(a for a in employees if a['role']=='AI CEO')
    changed=ok(client.patch('/api/agents/'+employee['id'],json={'name':'  自定义老板  '}))
    assert changed['name']=='自定义老板' and changed['appearance']==employee['appearance']
    # A second startup must not restore the original name or visual profile.
    migrate()
    assert next(a for a in rows('agents') if a['id']==employee['id'])['name']=='自定义老板'
    foreign=ok(client.patch('/api/agents/'+employee['id'],json={'appearance':{'portrait_id':'olivia-morgan'}}))
    assert foreign['appearance']['avatar_url']=='/assets/portraits/olivia-morgan.png'
    assert foreign['appearance']['character_profile']['nationality']=='GB'
    assert foreign['skills']==employee['skills'] and foreign['permissions']==employee['permissions']
    partial=ok(client.patch('/api/agents/'+employee['id'],json={'appearance':{'character_profile':{'description':'自主配置的虚拟人物档案'}}}))
    assert partial['appearance']['portrait_id']=='olivia-morgan'
    assert partial['appearance']['character_profile']['nationality']=='GB'
    assert partial['appearance']['index']==employee['appearance']['index']
    for bad in [{'avatar_url':'https://evil.example/track.png'},
                {'portrait_id':'olivia-morgan','character_profile':{'nationality':'CN'}},
                {'character_profile':{'permissions':['shell']}},
                {'portrait_id':'lin-yuan','avatar_url':'/assets/portraits/olivia-morgan.png'}]:
        ok(client.patch('/api/agents/'+employee['id'],json={'appearance':bad}),422)
    assert next(a for a in rows('agents') if a['id']==employee['id'])['appearance']==partial['appearance']
    ok(client.patch('/api/agents/'+employee['id'],json={'manager_id':{'invalid':'id'}}),422)
    ok(client.patch('/api/agents/'+employee['id'],json={'name':'名'*101}),422)
    created=ok(client.post('/api/agents',json={'name':'新同事','role':'研究员'}))
    assert created['appearance']['character_profile']['nationality']=='CN'
    explicit=ok(client.post('/api/agents',json={'name':'外籍形象同事','role':'产品顾问','appearance':{'portrait_id':'lucas-martin'}}))
    assert explicit['appearance']['character_profile']['nationality']=='FR'
