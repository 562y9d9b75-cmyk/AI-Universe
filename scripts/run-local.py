"""Docker-free process supervisor; only manages processes it starts."""
import fcntl,json,os,signal,socket,subprocess,sys,time,urllib.request,webbrowser
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    home=Path(os.environ['AIU_LOCAL_HOME']).resolve();(home/'run').mkdir(parents=True,exist_ok=True);os.umask(0o077)
    guard=(home/'run/launcher.lock').open('a')
    try:fcntl.flock(guard,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:print('个人本地版已在运行，请使用已有窗口。',flush=True);return 1
    api_port=int(os.getenv('AIU_PORT','8000'));web_port=int(os.getenv('AIU_WEB_PORT','3000'))
    for port in [api_port,web_port]:
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
            try:probe.bind(('127.0.0.1',port))
            except OSError:print(f'端口 {port} 已被占用，请先关闭之前的 AI Universe 启动窗口。',flush=True);return 1
    data=home/'data';data.mkdir(exist_ok=True)
    env=os.environ.copy();env.update(AIU_DATA_DIR=str(data),AIU_DATABASE_URL='sqlite:///'+str(data/'company.sqlite3'),AIU_REDIS_URL='',AIU_ORIGIN=f'http://localhost:{web_port}',NEXT_TELEMETRY_DISABLED='1')
    processes=[];logs=[];ids={};stopped=False
    def handle_signal(*_):
        nonlocal stopped
        stopped=True
    signal.signal(signal.SIGTERM,handle_signal);signal.signal(signal.SIGINT,handle_signal)
    def start(args,cwd,name):
        log=(home/'run'/f'{name}.log').open('a');logs.append(log)
        p=subprocess.Popen(args,cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        processes.append(p);ids[name]=p.pid;(home/'run/processes.json').write_text(json.dumps({'launcher':os.getpid(),'source':str(ROOT),'children':ids}))
    def show_logs():
        for name in ['api','worker','web']:
            p=home/'run'/f'{name}.log'
            if p.exists():print(f'\n{name} 最近日志：\n'+'\n'.join(p.read_text(errors='replace').splitlines()[-20:]),flush=True)
    try:
        subprocess.run([sys.executable,'-m','app.migrate'],cwd=ROOT/'backend',env=env,check=True)
        start([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(api_port)],ROOT/'backend','api')
        start([sys.executable,'-m','app.runtime'],ROOT/'backend','worker')
        start([str(Path(env['AIU_NODE_HOME'])/'bin/node'),'node_modules/next/dist/bin/next','start','--hostname','127.0.0.1','--port',str(web_port)],ROOT/'frontend','web')
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}));ready=False;deadline=time.monotonic()+90
        while not stopped and time.monotonic()<deadline:
            if any(p.poll() is not None for p in processes):show_logs();raise RuntimeError('必要服务启动失败，数据已保留')
            try:
                with opener.open(f'http://127.0.0.1:{web_port}/api/health',timeout=1) as r:health=json.load(r)
                if health.get('status')=='ok' and health.get('database')=='sqlite':ready=True;break
            except (OSError,ValueError):pass
            time.sleep(.25)
        if stopped:return 0
        if not ready:show_logs();raise RuntimeError('未通过启动检查，数据已保留')
        print(f'\nAI Universe 已就绪：http://localhost:{web_port}\n免 Docker 个人本地版（SQLite）\n首次使用请创建个人账户。保持终端开启，按 Ctrl+C 停止。\n数据：{data}\n日志：{home}/run\n',flush=True)
        if sys.platform=='darwin':webbrowser.open(f'http://localhost:{web_port}')
        while not stopped:
            for p in processes:
                if p.poll() is not None:show_logs();raise RuntimeError(f'必要服务退出，退出码 {p.returncode}')
            time.sleep(.25)
        return 0
    except (OSError,RuntimeError,subprocess.CalledProcessError) as e:print(str(e),file=sys.stderr,flush=True);return 1
    finally:
        for p in processes:
            if p.poll() is None:os.killpg(p.pid,signal.SIGTERM)
        for p in processes:
            try:p.wait(timeout=10)
            except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
        for log in logs:log.close()
        (home/'run/processes.json').unlink(missing_ok=True);guard.close()
if __name__=='__main__':sys.exit(main())
