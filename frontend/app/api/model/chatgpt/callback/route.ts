// Forward the one-shot callback without logging OAuth code/state or requiring cookies.
export const dynamic='force-dynamic';
export async function GET(request:Request){
  const input=new URL(request.url);
  const origin=process.env.AIU_API_ORIGIN||`http://127.0.0.1:${process.env.AIU_PORT||8000}`;
  const target=new URL('/api/model/chatgpt/callback',origin);
  target.search=input.search;
  try{
    const upstream=await fetch(target,{cache:'no-store',redirect:'manual',signal:AbortSignal.timeout(120000)});
    const headers=new Headers();
    for(const name of ['content-type','content-security-policy']){const value=upstream.headers.get(name);if(value)headers.set(name,value)}
    headers.set('Cache-Control','no-store');headers.set('Referrer-Policy','no-referrer');headers.set('X-Content-Type-Options','nosniff');
    return new Response(upstream.body,{status:upstream.status,headers});
  }catch{
    return new Response('连接本机授权服务失败，请返回 AI Universe 模型设置重新连接。',{status:502,headers:{'Content-Type':'text/plain; charset=utf-8','Cache-Control':'no-store','Referrer-Policy':'no-referrer'}});
  }
}
