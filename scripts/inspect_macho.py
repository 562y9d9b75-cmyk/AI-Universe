"""Inspect Intel Mac deployment targets; this is not execution on Mac hardware."""
import base64,hashlib,json,struct,subprocess,sys,tarfile,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def inspect(raw):
    if raw[:4]==b'\xca\xfe\xba\xbe':
        count=struct.unpack_from('>I',raw,4)[0]
        for i in range(count):
            cpu,sub,offset,size,align=struct.unpack_from('>IIIII',raw,8+20*i)
            if cpu==0x01000007:return inspect(raw[offset:offset+size])
        raise ValueError('No Intel slice')
    if raw[:4]!=b'\xcf\xfa\xed\xfe':raise ValueError('Expected Mach-O64')
    h=struct.unpack_from('<IiiIIIII',raw)
    if h[1]!=0x01000007:raise ValueError('Not x86_64')
    offset=32;minimum=None
    for _ in range(h[4]):
        cmd,size=struct.unpack_from('<II',raw,offset)
        if cmd==0x32:minimum=struct.unpack_from('<I',raw,offset+12)[0]
        elif cmd==0x24:minimum=struct.unpack_from('<I',raw,offset+8)[0]
        offset+=size
    if minimum is None:raise ValueError('Missing deployment target')
    version=(minimum>>16,(minimum>>8)&255,minimum&255)
    if version>(13,7,8):raise ValueError('Requires macOS '+'.'.join(map(str,version)))
    return {'architecture':'x86_64','minimum_macos':'.'.join(map(str,version)),'compatible_with_reported_macos':'13.7.8'}
def check_npm():
    packages=json.loads((ROOT/'frontend/package-lock.json').read_text())['packages'];results=[]
    with tempfile.TemporaryDirectory(prefix='aiu-mac-addons-') as folder:
        for name,p in packages.items():
            if 'darwin-x64' not in name or not p.get('resolved'):continue
            archive=Path(folder)/p['resolved'].rsplit('/',1)[1]
            subprocess.run(['curl','-fsSL','--max-time','90',p['resolved'],'-o',str(archive)],check=True)
            algorithm,value=p['integrity'].split('-',1)
            if algorithm!='sha512' or base64.b64encode(hashlib.sha512(archive.read_bytes()).digest()).decode()!=value:raise ValueError('npm integrity mismatch: '+name)
            with tarfile.open(archive) as t:
                for m in t:
                    if m.isfile() and m.name.endswith(('.node','.dylib')):results.append({'package':name,'version':p['version'],'file':m.name,'integrity':'sha512 verified',**inspect(t.extractfile(m).read())})
    if len(results)<4:raise RuntimeError('Missing native add-on checks')
    return {'status':'passed','method':'npm SHA512 and Mach-O inspection, not Mac execution','binaries':results}
def check_runtimes(folder):
    results=[]
    for p in sorted(Path(folder).glob('*.tar.gz')):
        with tarfile.open(p) as t:
            for m in t:
                if m.isfile() and m.name.endswith(('/bin/node','/bin/python3.12','/lib/libpython3.12.dylib')):results.append({'archive':p.name,'file':m.name,**inspect(t.extractfile(m).read())})
    if len(results)<2:raise RuntimeError('Missing Python/Node checks')
    return {'status':'passed','method':'Mach-O inspection, not Mac execution','binaries':results}
if __name__=='__main__':print(json.dumps(check_npm() if sys.argv[1]=='--npm' else check_runtimes(sys.argv[1]),indent=2))
