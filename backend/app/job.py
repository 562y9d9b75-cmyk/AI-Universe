"""Disposable bounded local-tool subprocess. No arbitrary shell/code execution."""
import sys,json
from .providers import PROVIDERS,Context,AuthorizationRequired,QuotaExhausted
from .files import generate
from .workflow import validate_plan,plan_markdown

def run_job(j):
 files=[];provider=None
 try:
  provider=PROVIDERS[j['provider']]
  context=Context(**j['context'])
  output=provider.execute(context,j['operation'])
  plan=None
  if j['operation']=='plan':
   plan=validate_plan(output,context.collaborators)
   output=plan_markdown(context.title,plan,context.collaborators)
  for fmt in (['md'] if plan else dict.fromkeys(j['formats'])):
   path,digest,size=generate(j['org'],j['task_id'],j['run_id'],fmt,output);files.append((fmt,path,digest,size))
  if not files:raise ValueError('未产生任何交付文件')
  result={'state':'succeeded','output':output,'files':files}
  if plan:result['plan']=plan
 except AuthorizationRequired as e:result={'state':'blocked_auth','error':str(e)}
 except QuotaExhausted as e:result={'state':'paused_quota','error':str(e)}
 except Exception as e:result={'state':'failed','error':type(e).__name__+': '+str(e)[:400]}
 result['metrics']=getattr(provider,'last_usage',{})
 return result

def main():
 result=run_job(json.loads(sys.stdin.read()))
 sys.stdout.write(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
