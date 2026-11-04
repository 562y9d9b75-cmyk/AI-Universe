import os,secrets,time,hashlib,threading
from datetime import datetime,timezone
from contextlib import asynccontextmanager
from typing import Annotated
from pathlib import Path
from fastapi import FastAPI,Depends,HTTPException,Request,Response,Body
from fastapi.responses import FileResponse,JSONResponse
from sqlalchemy import select,func,delete,text
from pydantic import ValidationError
from .db import *
from .migrate import migrate
from .schemas import *
from .security import authenticated,password_hash,check_password,token_hash
from .seed import seed
from .providers import connection_status
from .files import MIME
from .runtime import dependencies
from .appearance import appearance_catalog,normalize_appearance,default_appearance,DEFAULT_EMPLOYEES

@asynccontextmanager
async def lifespan(app):migrate();yield
app=FastAPI(title='AI Universe',version='0.1.0',lifespan=lifespan)
Auth=Annotated[dict,Depends(authenticated)]
_auth_lock=threading.Lock();_login_failures={}

@app.middleware('http')
async def boundary(request:Request,call_next):
    if request.method in ['POST','PATCH','PUT','DELETE']:
        if request.headers.get('x-aiu-request')!='1':return JSONResponse({'detail':'缺少同源请求标记'},status_code=403)
        origin=request.headers.get('origin')
        allowed={os.getenv('AIU_ORIGIN','http://localhost:3000'),'http://127.0.0.1:3000'}
        if origin and origin not in allowed:return JSONResponse({'detail':'来源不被允许'},status_code=403)
        try:
            if int(request.headers.get('content-length','0'))>2_000_000:return JSONResponse({'detail':'请求过大'},status_code=413)
        except ValueError:return JSONResponse({'detail':'请求长度无效'},status_code=400)
    r=await call_next(request)
    r.headers['X-Content-Type-Options']='nosniff';r.headers['Cache-Control']='no-store';r.headers['X-Frame-Options']='DENY'
    return r

def owned(s,model,id,org):
    obj=s.get(model,id)
    if not obj or obj.organization_id!=org:raise HTTPException(404,'记录不存在')
    return obj

def reference(s,model,id,org):
    if id:owned(s,model,id,org)

def login_response(s,u):
    token=secrets.token_urlsafe(48)
    s.add(LoginSession(organization_id=u.organization_id,user_id=u.id,token_hash=token_hash(token),expires_at=time.time()+86400*7))
    r=JSONResponse({'username':u.username,'organization_id':u.organization_id})
    r.set_cookie('aiu_session',token,httponly=True,samesite='strict',secure=os.getenv('AIU_SECURE_COOKIE')=='1',max_age=604800)
    return r

@app.get('/api/health')
def health():
    with Session() as s:s.execute(text('SELECT 1'))
    return {'status':'ok','database':engine.dialect.name}
@app.get('/api/auth/status')
def auth_status():
    with Session() as s:return {'initialized':bool(s.scalar(select(User.id).limit(1)))}
@app.post('/api/auth/bootstrap')
def bootstrap(data:Credentials):
    with _auth_lock,Session.begin() as s:
        if engine.dialect.name=='postgresql':s.execute(text('SELECT pg_advisory_xact_lock(19840220)'))
        if s.scalar(select(User.id).limit(1)):raise HTTPException(409,'个人账户已建立，不开放注册')
        org=Organization(name=data.company);s.add(org);s.flush()
        u=User(organization_id=org.id,username=data.username,password_hash=password_hash(data.password));s.add(u);s.flush();seed(s,org.id);audit(s,org.id,'workspace.created')
        return login_response(s,u)
@app.post('/api/auth/login')
def login(data:Credentials,request:Request):
    ip=request.client.host if request.client else 'local';key=(ip,data.username);attempts=[x for x in _login_failures.get(key,[]) if x>time.time()-60]
    if len(attempts)>=5:raise HTTPException(429,'尝试过于频繁，请稍后再试')
    with Session.begin() as s:
        u=s.scalar(select(User).where(User.username==data.username))
        if not u or not check_password(data.password,u.password_hash):_login_failures[key]=attempts+[time.time()];raise HTTPException(401,'用户名或密码错误')
        _login_failures.pop(key,None);return login_response(s,u)
@app.post('/api/auth/logout')
def logout(auth:Auth):
    with Session.begin() as s:s.delete(s.get(LoginSession,auth['session_id']))
    r=JSONResponse({'ok':True});r.delete_cookie('aiu_session');return r
@app.get('/api/me')
def me(auth:Auth):return auth
@app.get('/api/model/status')
def model_status(auth:Auth):return connection_status(auth['organization_id'])
@app.get('/api/appearance/catalog')
def get_appearance_catalog(auth:Auth):return appearance_catalog()
@app.get('/api/organizations')
def orgs(auth:Auth):
    # Personal installation has one owner and no public signup.
    with Session() as s:return [serialize(o) for o in s.scalars(select(Organization).order_by(Organization.created_at))]
@app.post('/api/organizations')
def new_org(auth:Auth,data:dict=Body(...)):
    name=str(data.get('name','')).strip()
    if not name or len(name)>200:raise HTTPException(422,'公司名称为必填，最多200字')
    with Session.begin() as s:
        org=Organization(name=name,description=str(data.get('description',''))[:4000]);s.add(org);s.flush();seed(s,org.id)
        s.get(LoginSession,auth['session_id']).organization_id=org.id
        audit(s,org.id,'organization.created',org.id);return serialize(org)
@app.post('/api/organizations/{id}/switch')
def switch_org(id:str,auth:Auth):
    with Session.begin() as s:
        org=s.get(Organization,id)
        if not org:raise HTTPException(404,'公司不存在')
        s.get(LoginSession,auth['session_id']).organization_id=id
    return {'ok':True}
@app.patch('/api/organization')
def update_org(auth:Auth,data:dict=Body(...)):
    with Session.begin() as s:
        org=s.scalar(select(Organization).where(Organization.id==auth['organization_id']).with_for_update())
        if 'name' in data:
            if not isinstance(data['name'],str) or not 1<=len(data['name'].strip())<=200:raise HTTPException(422,'公司名称无效')
            org.name=data['name'].strip()
        if 'description' in data:org.description=str(data['description'])[:4000]
        if 'settings' in data:
            cfg=data['settings'];limits={'daily_limit':(0,100000),'concurrency':(1,8),'max_rounds':(1,20),'timeout':(1,600)}
            if not isinstance(cfg,dict) or set(cfg)-set(limits):raise HTTPException(422,'额度配置无效')
            for k,v in cfg.items():
                if type(v)!=int or not limits[k][0]<=v<=limits[k][1]:raise HTTPException(422,'额度范围无效：'+k)
            org.settings={**org.settings,**cfg}
        audit(s,org.id,'organization.updated',org.id);return serialize(org)

@app.post('/api/agents/from-description')
def employee_from_text(auth:Auth,data:dict=Body(...)):
    description=str(data.get('description','')).strip()
    if not 2<=len(description)<=2000:raise HTTPException(422,'请输入姓名和岗位，例如：创建员工 Iris，岗位：法律顾问')
    import re
    name=re.search(r'(?:员工|名叫|姓名[：:]?)\s*([\w\u4e00-\u9fa5]+)',description)
    role=re.search(r'(?:岗位|担任|职位)[：:]?\s*([^，。\n]+)',description)
    if not name or not role:raise HTTPException(422,'本地解析需要明确姓名与岗位，例如：创建员工 Iris，岗位：法律顾问；自由语义理解等待模型授权')
    return create_resource('agents',auth,{'name':name.group(1),'role':role.group(1),'responsibilities':description,'permissions':['documents'],'skills':['文档整理']})

@app.post('/api/tasks')
def create_task(data:TaskInput,auth:Auth):
    org=auth['organization_id']
    with Session.begin() as s:
        reference(s,Agent,data.agent_id,org);reference(s,Project,data.project_id,org)
        if data.deadline:
            try:
                dt=datetime.fromisoformat(data.deadline)
                if not dt.tzinfo:raise ValueError('timezone required')
                data.deadline=dt.astimezone(timezone.utc).isoformat()
            except ValueError:raise HTTPException(422,'截止时间必须包含时区')
        for d in set(data.dependencies):owned(s,Task,d,org)
        fields={'organization_id':org,**data.model_dump(exclude={'mode','dependencies'})}
        if not fields['agent_id']:fields['agent_id']=s.scalar(select(Agent.id).where(Agent.organization_id==org).order_by(Agent.created_at))
        # Autonomous local mode is a disclosed deterministic 3-person DAG, not model planning.
        if data.mode=='autonomous' and data.provider=='chatgpt_plan':fields['operation']='plan'
        if data.mode=='autonomous' and data.provider=='local':
            agents=list(s.scalars(select(Agent).where(Agent.organization_id==org).order_by(Agent.created_at)))
            if len(agents)<3:raise HTTPException(422,'协作需要至少三名员工')
            chosen=[]
            for role in ['市场研究员','数据分析师','AI CEO']:
                a=next((a for a in agents if a.role==role and a.id not in chosen and 'documents' in a.permissions),None)
                if not a:a=next((a for a in agents if a.id not in chosen and 'documents' in a.permissions),None)
                if not a:raise HTTPException(422,'需要三名具有文档权限的员工')
                chosen.append(a.id)
            first=Task(**{**fields,'title':'材料整理 · '+data.title,'agent_id':chosen[0],'formats':['md'],'review_required':0,'operation':'document'})
            second=Task(**{**fields,'title':'材料复核 · '+data.title,'agent_id':chosen[1],'formats':['md'],'review_required':0,'operation':'analysis'})
            root=Task(**{**fields,'agent_id':chosen[2]})
            s.add_all([first,second,root]);s.flush();first.parent_id=root.id;second.parent_id=root.id
            # First two steps can run concurrently, final waits for both handoffs.
            s.add_all([TaskDependency(organization_id=org,task_id=root.id,depends_on_id=first.id),TaskDependency(organization_id=org,task_id=root.id,depends_on_id=second.id)])
            targets=[first,second]
        else:root=Task(**fields);s.add(root);s.flush();targets=[root]
        for t in targets:
            for d in set(data.dependencies):s.add(TaskDependency(organization_id=org,task_id=t.id,depends_on_id=d))
        audit(s,org,'task.created',root.id,'本地模板协作' if data.mode=='autonomous' and data.provider=='local' else data.mode)
        return serialize(root)

@app.post('/api/tasks/{id}/{action}')
def task_action(id:str,action:str,auth:Auth):
    with Session.begin() as s:
        t=s.scalar(select(Task).where(Task.id==id,Task.organization_id==auth['organization_id']).with_for_update())
        if not t:raise HTTPException(404,'任务不存在')
        if action not in ['pause','resume','retry','cancel']:raise HTTPException(404,'操作不存在')
        if action in ['resume','retry']:
            if t.status not in ['paused','paused_budget','paused_quota','blocked_auth','failed','cancelled']:raise HTTPException(409,'当前状态不能恢复或重试')
            t.status='queued';t.error=''
        else:
            if t.status in ['completed','cancelled']:raise HTTPException(409,'任务已结束')
            t.status='paused' if action=='pause' else 'cancelled'
            if t.active_run_id:
                run=s.get(TaskRun,t.active_run_id)
                if run and run.status=='running':run.status='interrupted';run.finished_at=now()
            for a in s.scalars(select(Approval).where(Approval.task_id==t.id,Approval.status=='pending')):a.status='superseded'
            t.active_run_id=None
        if not t.parent_id:
            children=list(s.scalars(select(Task).where(Task.parent_id==t.id).with_for_update()))
            for child in children:
                if action in ['resume','retry']:
                    if child.status in ['paused','cancelled','paused_budget','paused_quota','blocked_auth','failed'] :child.status='queued';child.error=''
                elif child.status not in ['completed','cancelled']:
                    child.status='paused' if action=='pause' else 'cancelled'
                    if child.active_run_id:
                        run=s.get(TaskRun,child.active_run_id)
                        if run and run.status=='running':run.status='interrupted';run.finished_at=now()
                    child.active_run_id=None
                    for approval in s.scalars(select(Approval).where(Approval.task_id==child.id,Approval.status=='pending')):approval.status='superseded'
                    audit(s,t.organization_id,'task.'+action,child.id,'由父任务控制')
        audit(s,t.organization_id,'task.'+action,t.id)
        return serialize(t)

@app.post('/api/approvals/{id}/review')
def review(id:str,data:ReviewInput,auth:Auth):
    with Session.begin() as s:
        # Same task-first lock order as runtime/control endpoints.
        initial=owned(s,Approval,id,auth['organization_id'])
        t=s.scalar(select(Task).where(Task.id==initial.task_id).with_for_update())
        a=s.scalar(select(Approval).where(Approval.id==id).with_for_update())
        if a.status!='pending' or t.status!='review' or a.run_id!=t.active_run_id:raise HTTPException(409,'审批已处理或成果已更新')
        if data.decision=='reject' and not data.feedback.strip():raise HTTPException(422,'退回时请说明修改要求')
        a.status='approved' if data.decision=='approve' else 'rejected';a.feedback=data.feedback;t.feedback=data.feedback
        t.status='completed' if data.decision=='approve' else 'queued';audit(s,t.organization_id,'review.'+a.status,t.id,data.feedback)
        return serialize(t)

WRITABLE={'departments':{'name','description'},'agents':{'name','role','department_id','manager_id','responsibilities','goals','skills','permissions','appearance'},'projects':{'name','description'},'memories':{'scope','scope_id','content','source','confidence','verified'},'knowledge_items':{'title','content','source'}}
def validate_fields(s,resource,data,org,id=None):
    if not isinstance(data,dict) or not data or set(data)-WRITABLE[resource]:raise HTTPException(422,'字段不被允许')
    for k,v in data.items():
        if isinstance(v,str) and len(v)>20000:raise HTTPException(422,'字段过长')
    if resource in ['departments','agents','projects']:
        for k in ['name','role'] if resource=='agents' else ['name']:
            max_length=100 if resource=='agents' and k=='name' else 200
            if k in data and (not isinstance(data[k],str) or not 1<=len(data[k].strip())<=max_length):raise HTTPException(422,'名称或岗位为空、过长')
            if not id and k not in data:raise HTTPException(422,'缺少必填字段 '+k)
            if k in data:data[k]=data[k].strip()
        if 'description' in data and not isinstance(data['description'],str):raise HTTPException(422,'说明必须是文本')
    if resource=='agents':
        for k in ['department_id','manager_id']:
            if k in data and data[k] is not None and (not isinstance(data[k],str) or not 1<=len(data[k])<=36):raise HTTPException(422,'关联记录ID格式无效')
        reference(s,Department,data.get('department_id'),org);reference(s,Agent,data.get('manager_id'),org)
        manager=data.get('manager_id');seen={id} if id else set()
        while manager:
            if manager in seen:raise HTTPException(422,'汇报关系不能成环')
            seen.add(manager);manager=owned(s,Agent,manager,org).manager_id
        for k in ['responsibilities','goals']:
            if k in data and not isinstance(data[k],str):raise HTTPException(422,k+'必须是文本')
        for k in ['skills','permissions']:
            if k in data and (not isinstance(data[k],list) or len(data[k])>100 or any(not isinstance(v,str) or len(v)>100 for v in data[k])):raise HTTPException(422,k+'格式无效')
        if 'permissions' in data and set(data['permissions'])-{'documents','analysis'}:raise HTTPException(422,'工具尚未实现，不能授予此权限')
        if 'appearance' in data:
            current=owned(s,Agent,id,org).appearance if id else None
            try:data['appearance']=normalize_appearance(data['appearance'],current)
            except (ValidationError,ValueError):raise HTTPException(422,'形象配置无效：请选择匹配地区的本地人物模板，字段须符合形象目录')
        elif not id:
            # Prefer an unused Chinese character for new employees; the owner can
            # explicitly choose either Chinese or foreign portraits in the editor.
            used={a.appearance.get('portrait_id') for a in s.scalars(select(Agent).where(Agent.organization_id==org)) if isinstance(a.appearance,dict)}
            portrait_id=next((p['portrait_id'] for p in DEFAULT_EMPLOYEES if p['portrait_id'] not in used),'lin-yuan')
            data['appearance']=default_appearance(portrait_id)
    if resource=='memories':
        current=serialize(owned(s,Memory,id,org)) if id else {}
        try:m=MemoryInput.model_validate({**{k:v for k,v in current.items() if k in WRITABLE[resource]},**data})
        except ValidationError:raise HTTPException(422,'记忆内容、来源和范围必须有效')
        models={'employee':Agent,'department':Department,'project':Project}
        if m.scope!='company':
            if not m.scope_id:raise HTTPException(422,'请选择记忆适用对象')
            owned(s,models[m.scope],m.scope_id,org)
        elif m.scope_id:raise HTTPException(422,'公司级记忆不需要对象ID')
        data.clear();data.update(m.model_dump())
    if resource=='knowledge_items':
        for k in ['title','content','source']:
            if (not id or k in data) and (not isinstance(data.get(k),str) or not data[k].strip()):raise HTTPException(422,'知识条目需要标题、内容、来源')

def sync_agent(s,a):
    for model,values in [(AgentSkill,a.skills),(AgentPermission,a.permissions)]:
        s.execute(delete(model).where(model.agent_id==a.id))
        for name in set(values):s.add(model(organization_id=a.organization_id,agent_id=a.id,name=name))

@app.get('/api/{resource}')
def list_resource(resource:str,auth:Auth,limit:int=300):
    if resource not in RESOURCES:raise HTTPException(404,'模块不存在')
    with Session() as s:
        model=RESOURCES[resource]
        return [serialize(x) for x in s.scalars(select(model).where(model.organization_id==auth['organization_id']).order_by(model.created_at.desc()).limit(max(1,min(limit,1000))))]
@app.post('/api/{resource}')
def create_resource(resource:str,auth:Auth,data:dict=Body(...)):
    if resource not in WRITABLE:raise HTTPException(405,'此模块只能通过业务操作创建')
    with Session.begin() as s:
        validate_fields(s,resource,data,auth['organization_id']);obj=RESOURCES[resource](organization_id=auth['organization_id'],**data);s.add(obj);s.flush()
        if resource=='agents':sync_agent(s,obj);s.add(EmployeeAnimation(organization_id=obj.organization_id,agent_id=obj.id))
        audit(s,auth['organization_id'],resource+'.created',obj.id);return serialize(obj)
@app.patch('/api/{resource}/{id}')
def update_resource(resource:str,id:str,auth:Auth,data:dict=Body(...)):
    if resource not in WRITABLE:raise HTTPException(405,'字段只能通过业务操作修改')
    with Session.begin() as s:
        obj=owned(s,RESOURCES[resource],id,auth['organization_id']);validate_fields(s,resource,data,auth['organization_id'],id)
        for k,v in data.items():setattr(obj,k,v)
        if resource=='agents':sync_agent(s,obj)
        audit(s,auth['organization_id'],resource+'.updated',id);return serialize(obj)
@app.delete('/api/{resource}/{id}')
def remove_resource(resource:str,id:str,auth:Auth):
    if resource not in ['memories','knowledge_items']:raise HTTPException(405,'仅记忆和知识可直接删除，避免破坏任务历史')
    with Session.begin() as s:
        obj=owned(s,RESOURCES[resource],id,auth['organization_id']);s.delete(obj);audit(s,auth['organization_id'],resource+'.deleted',id)
    return {'ok':True}
@app.get('/api/tasks/{id}/detail')
def task_detail(id:str,auth:Auth):
    with Session() as s:
        t=owned(s,Task,id,auth['organization_id']);result=serialize(t)
        for key,model in [('runs',TaskRun),('artifacts',Artifact),('messages',AgentMessage)]:result[key]=[serialize(x) for x in s.scalars(select(model).where(model.task_id==id).order_by(model.created_at))]
        result['dependencies']=[serialize(d) for d in dependencies(s,t)]
        return result
@app.get('/api/artifacts/{id}/download')
def download(id:str,auth:Auth):
    with Session() as s:
        a=owned(s,Artifact,id,auth['organization_id']);p=Path(a.path).resolve()
        if not p.is_relative_to(DATA/'artifacts') or not p.is_file():raise HTTPException(404,'文件不存在')
        if hashlib.sha256(p.read_bytes()).hexdigest()!=a.sha256:raise HTTPException(409,'文件完整性校验失败')
        return FileResponse(p,media_type=MIME[a.format],filename=a.name,headers={'Content-Security-Policy':"sandbox; default-src 'none'"})
@app.post('/api/office/animations/{agent_id}')
def animation(agent_id:str,auth:Auth,data:dict=Body(...)):
    if data.get('state') not in ['idle','typing','coffee','walking','reading','meeting','whiteboard','resting','returning']:raise HTTPException(422,'动画状态无效')
    with Session.begin() as s:
        owned(s,Agent,agent_id,auth['organization_id'])
        a=s.scalar(select(EmployeeAnimation).where(EmployeeAnimation.agent_id==agent_id));a.state=data['state'];a.changed_at=now();return serialize(a)

# OAuth control routes have their own owner checks; callback uses single-use state.
from .model_routes import router as model_router
app.include_router(model_router)
