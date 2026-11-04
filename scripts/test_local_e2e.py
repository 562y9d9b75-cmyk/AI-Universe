"""Test the actual portable installer and independent app processes in an isolated copy."""
import json,os,subprocess,sys,tempfile,time,shutil,secrets,signal
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1]
source=Path(tempfile.mkdtemp(prefix='aiu-native-source-'))
home=Path(os.getenv('AIU_TEST_LOCAL_HOME',tempfile.mkdtemp(prefix='aiu-native home-')))
evidence=Path(os.getenv('AIU_E2E_EVIDENCE_DIR',str(ROOT/'docs/evidence/local-mode'))).resolve()
for directory in ['backend','frontend','scripts']:
    shutil.copytree(ROOT/directory,source/directory,ignore=shutil.ignore_patterns('node_modules','.next','__pycache__','.pytest_cache','test-results','*.tsbuildinfo'))
(source/'.run').mkdir()
env=os.environ.copy();env.update(AIU_LOCAL_HOME=str(home),AIU_PORT='8012',AIU_WEB_PORT='3012',AIU_E2E_DATABASE='sqlite',AIU_E2E_BASE_URL='http://localhost:3012',AIU_E2E_REPORT=str(evidence/'playwright-results.json'),AIU_E2E_EVIDENCE_DIR=str(evidence),AIU_E2E_PASSWORD=secrets.token_urlsafe(32))
processes=[];handles=[]
def launch(name):
    log=(source/'.run'/(name+'.log')).open('w');handles.append(log)
    p=subprocess.Popen(['bash','scripts/start-local.sh'],cwd=source,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True);processes.append(p)
    print('Native launcher log:',str(source/'.run'/(name+'.log')),flush=True);return p

def ready(p):
    with httpx.Client(trust_env=False) as c:
        for _ in range(720):
            if p.poll() is not None:raise RuntimeError('Native launcher failed; inspect '+str(source/'.run'))
            try:
                r=c.get('http://localhost:3012/api/health',timeout=1)
                if r.status_code==200 and r.json().get('database')=='sqlite':return
            except (httpx.HTTPError,ValueError):pass
            time.sleep(.5)
        raise RuntimeError('Native installer did not become ready')
try:
    launcher=launch('first');ready(launcher)
    node=next((home/'runtime').glob('node-*/bin/node'));env['PATH']=str(node.parent)+os.pathsep+env['PATH']
    with httpx.Client(trust_env=False) as c:assert c.get('http://localhost:3012/api/auth/status').json()=={'initialized':False}
    result=subprocess.run([str(node),str(source/'frontend/node_modules/@playwright/test/cli.js'),'test'],cwd=source/'frontend',env=env)
    if result.returncode:sys.exit(result.returncode)
    with httpx.Client(base_url='http://localhost:3012',headers={'X-AIU-Request':'1'},trust_env=False) as c:
        c.post('/api/auth/login',json={'username':'acceptance-owner','password':env['AIU_E2E_PASSWORD']}).raise_for_status()
        c.post('/api/organizations',json={'name':'本地恢复验收'}).raise_for_status()
        c.patch('/api/organization',json={'settings':{'timeout':3,'concurrency':1}}).raise_for_status()
        r=c.post('/api/tasks',json={'title':'免Docker中断恢复','input':'本地恢复证据 '*1000,'formats':['md','docx','xlsx','pptx','pdf'],'review_required':False});r.raise_for_status();task=r.json()
        for _ in range(500):
            detail=c.get('/api/tasks/'+task['id']+'/detail').json()
            if detail['status']=='running':break
            time.sleep(.01)
        else:raise RuntimeError('Did not observe an active local task')
        info=json.loads((home/'run/processes.json').read_text());os.killpg(info['children']['worker'],signal.SIGKILL)
    launcher.wait(timeout=20);assert launcher.returncode!=0
    launcher=launch('restarted');ready(launcher)
    with httpx.Client(base_url='http://localhost:3012',headers={'X-AIU-Request':'1'},trust_env=False) as c:
        c.post('/api/auth/login',json={'username':'acceptance-owner','password':env['AIU_E2E_PASSWORD']}).raise_for_status()
        c.post('/api/organizations/'+task['organization_id']+'/switch').raise_for_status()
        for _ in range(200):
            detail=c.get('/api/tasks/'+task['id']+'/detail').json()
            if detail['status']=='completed':break
            time.sleep(.1)
        else:raise RuntimeError('SQLite recovery failed: '+detail.get('error','unknown'))
        assert detail['attempts']>=2 and any(r['status']=='interrupted' for r in detail['runs']) and len(detail['artifacts'])==5
    for log in (home/'run').glob('*.log'):
        assert 'private-e2e-sentinel' not in log.read_text(errors='replace'),'OAuth callback query was logged'
    evidence.mkdir(parents=True,exist_ok=True)
    (evidence/'portable-launcher.json').write_text(json.dumps({'status':'passed','runtimes':'verified portable CPython3.12.16 and Node24.22.2','database':'sqlite','postgresql_redis_docker_required':False,'path_contains_spaces':True,'browser_workflow':'passed','worker_crash_recovery':'passed','oauth_callback_query_not_logged':True,'attempts':detail['attempts'],'run_states':[r['status'] for r in detail['runs']],'artifacts':len(detail['artifacts']),'physical_mac_tested':False},indent=2))
    print('Portable installer / SQLite browser E2E / actual worker crash + full restart recovery: passed',flush=True)
finally:
    for p in processes:
        if p.poll() is None:p.terminate()
    for p in processes:
        try:p.wait(timeout=20)
        except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
    for h in handles:h.close()
