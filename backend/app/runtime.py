"""Durable DAG scheduler: DB locks, leases, bounded retries, fenced commits.
One local worker per installation; PostgreSQL also serializes per-org admission.
"""
import os,time,logging,signal,threading,subprocess,sys,json
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import select,func,or_
from .db import *
from .providers import PROVIDERS,Context,AuthorizationRequired,QuotaExhausted
from .files import generate
log=logging.getLogger('aiu.runtime')
stop=threading.Event()

def notify(org,action):
    try:
        import redis
        redis.Redis.from_url(os.getenv('AIU_REDIS_URL','redis://127.0.0.1:56379/0'),socket_connect_timeout=.3,socket_timeout=.3).publish('aiu:'+org,action)
    except Exception:log.debug('Redis unavailable; SQL remains authoritative')

def locked(s,model,id):return s.scalar(select(model).where(model.id==id).with_for_update())
def dependencies(s,t):
    ids=list(s.scalars(select(TaskDependency.depends_on_id).where(TaskDependency.task_id==t.id)))
    return list(s.scalars(select(Task).where(Task.id.in_(ids)))) if ids else []
def claim():
    with Session.begin() as s:
        # Lock organizations first: serialize budget admission, not expensive execution.
        orgs=list(s.scalars(select(Organization).order_by(Organization.id).with_for_update(skip_locked=True)))
        for org in orgs:
            cfg=org.settings
            expired=list(s.scalars(select(Task).where(Task.organization_id==org.id,Task.status=='running',Task.lease_until<time.time()).with_for_update()))
            for t in expired:
                run=s.get(TaskRun,t.active_run_id)
                if run:run.status='interrupted';run.finished_at=now()
                for u in s.scalars(select(UsageRecord).where(UsageRecord.task_id==t.id,UsageRecord.status=='reserved')):u.status='interrupted'
                t.status='queued';t.active_run_id=None;t.error='工作进程中断；租约过期后恢复'
                audit(s,org.id,'task.recovered',t.id)
            running=s.scalar(select(func.count()).select_from(Task).where(Task.organization_id==org.id,Task.status=='running'))
            if running>=min(8,cfg.get('concurrency',3)):continue
            tasks=list(s.scalars(select(Task).where(Task.organization_id==org.id,Task.status=='queued').order_by(Task.created_at).limit(100).with_for_update(skip_locked=True)))
            for t in tasks:
                deps=dependencies(s,t)
                if any(d.status!='completed' for d in deps):continue
                reason=''
                if t.deadline and t.deadline<now():reason='已超过截止时间'
                if t.attempts>=min(t.max_calls,cfg.get('max_rounds',5)):reason='单任务调用上限 / 最大执行轮次已用尽'
                root=s.get(Task,t.parent_id) if t.parent_id else t
                group_used=s.scalar(select(func.coalesce(func.sum(Task.attempts),0)).where(or_(Task.id==root.id,Task.parent_id==root.id)))
                if group_used>=root.max_calls:reason='协作目标总执行上限已用尽'
                if t.parent_id and root.status in ['paused','cancelled'] :continue
                used=s.scalar(select(func.coalesce(func.sum(UsageRecord.units),0)).where(UsageRecord.organization_id==org.id,UsageRecord.created_at>=now()[:10]))
                if used>=cfg.get('daily_limit',100):reason='单日调用额度已用尽'
                if reason:
                    t.status='paused_budget';t.error=reason;audit(s,org.id,'task.budget_paused',t.id,reason);continue
                agent=s.get(Agent,t.agent_id) if t.agent_id else None
                permission='analysis' if t.operation=='analysis' else 'documents'
                if not agent or permission not in agent.permissions:
                    t.status='failed';t.error='员工未获得所需工具权限：'+permission;continue
                source=t.input
                for d in deps:
                    arts=list(s.scalars(select(Artifact).where(Artifact.task_id==d.id,Artifact.run_id==d.active_run_id)))
                    handoff=f'\n\n[上游任务 {d.title}]\n{d.output}'
                    source+=handoff
                    s.add(AgentMessage(organization_id=org.id,task_id=t.id,from_agent_id=d.agent_id,to_agent_id=t.agent_id,content=handoff[:85000],artifact_ids=[a.id for a in arts]))
                for m in s.scalars(select(Memory).where(Memory.organization_id==org.id,Memory.verified==1)):
                    if m.scope=='company' or (m.scope=='employee' and m.scope_id==t.agent_id) or (m.scope=='project' and m.scope_id==t.project_id) or (m.scope=='department' and m.scope_id==agent.department_id):source+=f'\n[已核实记忆；来源 {m.source}] {m.content}'
                run=TaskRun(organization_id=org.id,task_id=t.id,agent_id=t.agent_id,input=source[:180000]);s.add(run);s.flush()
                t.attempts+=1;t.status='running';t.active_run_id=run.id;t.lease_until=time.time()+cfg.get('timeout',120);t.error=''
                if t.deadline:t.lease_until=min(t.lease_until,datetime.fromisoformat(t.deadline).timestamp())
                s.add(UsageRecord(organization_id=org.id,task_id=t.id,agent_id=t.agent_id,provider=t.provider,status='reserved'))
                audit(s,org.id,'task.started',t.id,'执行轮次 '+str(t.attempts))
                return {'task_id':t.id,'run_id':run.id,'provider':t.provider,'operation':t.operation,'formats':t.formats,'org':org.id,'lease':t.lease_until,'context':Context(t.title,source[:180000],t.criteria,agent.role,t.feedback)}
    return None

def execute(job):
    error='';state='failed';output='';files=[]
    try:
        # Isolate the tool process so timeouts stop CPU/file work, not only status updates.
        payload={**{k:v for k,v in job.items() if k!='context'},'context':vars(job['context'])}
        process=subprocess.Popen([sys.executable,'-m','app.job'],cwd=str(ROOT/'backend'),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            raw,stderr=process.communicate(json.dumps(payload),timeout=max(.1,job['lease']-time.time()))
        except subprocess.TimeoutExpired:
            process.kill();process.communicate();raise TimeoutError('工具执行超过超时限制，子进程已终止')
        if process.returncode:raise RuntimeError('工具进程异常退出')
        result=json.loads(raw);state=result['state'];error=result.get('error','');output=result.get('output','');files=result.get('files',[])

    except AuthorizationRequired as e:state='blocked_auth';error=str(e)
    except QuotaExhausted as e:state='paused_quota';error=str(e)
    except Exception as e:log.exception('Task execution failed');error=type(e).__name__+': '+str(e)[:400]
    with Session.begin() as s:
        t=locked(s,Task,job['task_id']);run=s.get(TaskRun,job['run_id'])
        if not t or t.active_run_id!=job['run_id'] or t.status!='running':return
        if time.time()>t.lease_until:state='failed';error='任务超时，结果未提交'
        run.finished_at=now();run.status=state;run.output=output if state=='succeeded' else error
        records=list(s.scalars(select(UsageRecord).where(UsageRecord.task_id==t.id,UsageRecord.status=='reserved')))
        for record in records:record.status=state
        if state=='succeeded':
            t.output=output
            for fmt,path,digest,size in files:s.add(Artifact(organization_id=t.organization_id,task_id=t.id,run_id=run.id,name=t.title[:120]+'.'+fmt,format=fmt,path=path,sha256=digest,size=size,preview=output,version=t.attempts))
            t.status='review' if t.review_required else 'completed'
            if t.review_required:s.add(Approval(organization_id=t.organization_id,task_id=t.id,run_id=run.id))
        else:
            t.error=error;t.status=state
            if state=='failed' and t.attempts<min(3,t.max_calls,s.get(Organization,t.organization_id).settings.get('max_rounds',5)):t.status='queued'
        audit(s,t.organization_id,'task.'+t.status,t.id,error)
    notify(job['org'],'task.updated')

def main():
    from .migrate import migrate
    migrate();logging.basicConfig(level=logging.INFO)
    signal.signal(signal.SIGTERM,lambda *_:stop.set());signal.signal(signal.SIGINT,lambda *_:stop.set())
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures=set()
        while not stop.is_set():
            futures={f for f in futures if not f.done()}
            try:
                job=claim() if len(futures)<8 else None
                if job:futures.add(pool.submit(execute,job))
                else:stop.wait(.25)
            except Exception:log.exception('Scheduler failure');stop.wait(1)
if __name__=='__main__':main()
