"""Disposable bounded local-tool subprocess. No arbitrary shell/code execution."""
import sys,json
from .providers import PROVIDERS,Context,AuthorizationRequired,QuotaExhausted
from .files import generate

def main():
 j=json.loads(sys.stdin.read());files=[]
 try:
  output=PROVIDERS[j['provider']].execute(Context(**j['context']),j['operation'])
  for fmt in dict.fromkeys(j['formats']):
   path,digest,size=generate(j['org'],j['task_id'],j['run_id'],fmt,output);files.append((fmt,path,digest,size))
  if not files:raise ValueError('未产生任何交付文件')
  result={'state':'succeeded','output':output,'files':files}
 except AuthorizationRequired as e:result={'state':'blocked_auth','error':str(e)}
 except QuotaExhausted as e:result={'state':'paused_quota','error':str(e)}
 except Exception as e:result={'state':'failed','error':type(e).__name__+': '+str(e)[:400]}
 sys.stdout.write(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
