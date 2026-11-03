"""Create a portable source delivery without credentials, databases or dependency caches."""
from pathlib import Path
import os,zipfile,hashlib,json
ROOT=Path(__file__).resolve().parents[1]
SKIP={'node_modules','.next','.git','.venv','.pytest_cache','__pycache__','.data','.run','test-results','playwright-report'}
files=[ROOT/p for p in ['README.md','LICENSE','.gitignore','.env.example','compose.yaml','compose.desktop.yaml','.dockerignore','启动 AI Universe.command']]
for directory in ['backend','frontend','assets','docs','scripts','docker']:
 for current,dirs,names in os.walk(ROOT/directory):
  dirs[:]=[d for d in dirs if d not in SKIP]
  for name in names:
   p=Path(current)/name
   if name=='.env' or name.endswith(('.pyc','.tsbuildinfo')) or p.is_symlink():continue
   files.append(p)
output=ROOT/'.data/dist/AI-Universe-source.zip';output.parent.mkdir(parents=True,exist_ok=True)
manifest=[]
with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for p in sorted(set(files)):
  name=p.relative_to(ROOT).as_posix();raw=p.read_bytes();z.write(p,'AI-Universe/'+name)
  manifest.append({'path':name,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
 z.writestr('AI-Universe/SOURCE-MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2))
with zipfile.ZipFile(output) as z:
 assert z.testzip() is None
 assert not any(n.endswith('/.env') or '/node_modules/' in n or '/.data/' in n for n in z.namelist())
print(str(output));print(f'{len(manifest)} source/evidence files; {output.stat().st_size/1024/1024:.1f} MiB; no owner credentials or data')
