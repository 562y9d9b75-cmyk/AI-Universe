"""Runs real API/worker/Next processes against a disposable, unique PostgreSQL DB.
Does not initialize or alter the owner's workspace. Only created processes/DB are removed.
"""
import os,sys,time,subprocess,socket,uuid,signal,secrets,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];os.chdir(ROOT)
for line in (ROOT/'.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:
  k,v=line.split('=',1);os.environ[k]=v
from sqlalchemy.engine import make_url
import psycopg,httpx
for port in [8000,3000]:
 with socket.socket() as s:
  s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
  try:s.bind(('127.0.0.1',port))
  except OSError:sys.exit(f'Test port {port} is in use. Stop the development launcher before running this test.')
url=make_url(os.environ['AIU_DATABASE_URL']);db='aiu_e2e_'+uuid.uuid4().hex[:12]
admin=psycopg.connect(host=url.host,port=url.port,user=url.username,password=url.password,dbname=url.database,autocommit=True)
admin.execute('CREATE DATABASE '+db)
env=os.environ.copy();env.update(AIU_DATABASE_URL=url.set(database=db).render_as_string(hide_password=False),AIU_DATA_DIR=str(ROOT/'.data'/db),AIU_ORIGIN='http://127.0.0.1:3000',AIU_PORT='8000',NEXT_TELEMETRY_DISABLED='1',AIU_E2E_PASSWORD=secrets.token_urlsafe(32))
logs=ROOT/'.run'/db;logs.mkdir(parents=True,exist_ok=True)
processes=[];handles=[]
def start(args,cwd,name):
 h=open(logs/(name+'.log'),'w');handles.append(h)
 p=subprocess.Popen(args,cwd=cwd,env=env,stdout=h,stderr=subprocess.STDOUT,start_new_session=True);processes.append(p);return p
try:
 py=str(ROOT/'.venv/bin/python')
 start([py,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000'],ROOT/'backend','api')
 worker=start([py,'-m','app.runtime'],ROOT/'backend','worker')
 start(['node','node_modules/next/dist/bin/next','start','--hostname','127.0.0.1','--port','3000'],ROOT/'frontend','web')
 with httpx.Client(trust_env=False) as c:
  for i in range(90):
   if any(p.poll() is not None for p in processes):raise RuntimeError('Process failed; inspect '+str(logs))
   try:
    if c.get('http://127.0.0.1:3000/api/health').status_code==200:break
   except httpx.HTTPError:pass
   time.sleep(.5)
  else:raise RuntimeError('Readiness check timed out')
 result=subprocess.run(['npm','run','test:e2e'],cwd=ROOT/'frontend',env=env)
 if result.returncode==0:
  # Exercise actual process death and recovery, rather than only editing a DB fixture.
  with httpx.Client(base_url='http://127.0.0.1:8000',headers={'X-AIU-Request':'1'},trust_env=False) as c:
   r=c.post('/api/auth/login',json={'username':'acceptance-owner','password':env['AIU_E2E_PASSWORD']});r.raise_for_status()
   c.post('/api/organizations',json={'name':'进程中断恢复验收'}).raise_for_status()
   c.patch('/api/organization',json={'settings':{'timeout':3,'concurrency':1}}).raise_for_status()
   r=c.post('/api/tasks',json={'title':'真实进程中断恢复','input':'恢复验收原始材料 '*1000,'formats':['md','docx','xlsx','pptx','pdf'],'review_required':False});r.raise_for_status();task=r.json()
   end=time.monotonic()+8
   while time.monotonic()<end:
    r=c.get('/api/tasks/'+task['id']+'/detail');r.raise_for_status()
    if r.json()['status']=='running':break
    time.sleep(.01)
   else:raise RuntimeError('Recovery test did not observe a running task')
   os.killpg(worker.pid,signal.SIGKILL);worker.wait()
   start([py,'-m','app.runtime'],ROOT/'backend','worker-restarted')
   end=time.monotonic()+20
   while time.monotonic()<end:
    detail=c.get('/api/tasks/'+task['id']+'/detail').json()
    if detail['status']=='completed':break
    time.sleep(.1)
   else:raise RuntimeError('Recovery failed: '+detail.get('error','unknown'))
   assert detail['attempts']>=2 and any(r['status']=='interrupted' for r in detail['runs'])
   assert len(detail['artifacts'])==5
   (ROOT/'docs/evidence/process-recovery.json').write_text(json.dumps({'status':'passed','method':'SIGKILL worker process group; restart independent worker; wait for expired lease','attempts':detail['attempts'],'run_states':[r['status'] for r in detail['runs']],'artifacts':len(detail['artifacts'])},indent=2))
   print('Actual worker SIGKILL/restart recovery: passed',flush=True)
 sys.exit(result.returncode)
finally:
 for p in processes:
  if p.poll() is None:os.killpg(p.pid,signal.SIGTERM)
 for p in processes:
  try:p.wait(timeout=10)
  except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
 for h in handles:h.close()
 admin.execute('DROP DATABASE '+db+' WITH (FORCE)');admin.close()
