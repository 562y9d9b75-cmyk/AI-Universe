"""Exercise the shipped launcher twice without creating an owner account."""
import os,subprocess,time,json,signal
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1];os.chdir(ROOT);(ROOT/'.run').mkdir(exist_ok=True)
results=[]
for attempt in range(2):
 log=open(ROOT/'.run'/f'launcher-check-{attempt+1}.log','w')
 p=subprocess.Popen(['bash','scripts/start.sh'],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 try:
  with httpx.Client(trust_env=False) as c:
   for _ in range(90):
    if p.poll() is not None:raise RuntimeError('Launcher exited; see .run/launcher-check logs')
    try:
     r=c.get('http://127.0.0.1:3000/api/health')
     if r.status_code==200:
      auth=c.get('http://127.0.0.1:3000/api/auth/status').json()
      # The installation used for delivery must remain uninitialized for the owner.
      assert auth['initialized'] is False
      results.append({'attempt':attempt+1,'database':r.json()['database'],'owner_database_uninitialized':True});break
    except httpx.HTTPError:pass
    time.sleep(.5)
   else:raise RuntimeError('Launcher readiness failed')
 finally:
  if p.poll() is None:os.kill(p.pid,signal.SIGTERM)
  try:p.wait(timeout=15)
  except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
  log.close()
 for _ in range(20):
  if not (ROOT/'.run/launcher.pid').exists():break
  time.sleep(.1)
(ROOT/'docs/evidence/startup.json').write_text(json.dumps({'status':'passed','launcher':'scripts/start.sh','runs':results},indent=2))
print('Shipped launcher start/stop/restart: passed; owner database remains uninitialized')
