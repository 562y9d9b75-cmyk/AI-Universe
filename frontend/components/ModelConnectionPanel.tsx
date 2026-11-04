'use client';
import {useEffect,useState} from 'react';
import {AlertCircle,ArrowUpRight,Check,ExternalLink,Link2,LoaderCircle,RefreshCw,ShieldCheck,Unplug} from 'lucide-react';
type Row=Record<string,any>;
type Api=(path:string,method?:string,body?:unknown)=>Promise<any>;
type ModelOption={slug:string;display_name:string};
export default function ModelConnectionPanel({status,api,onRefresh,onError}:{status:Row;api:Api;onRefresh:()=>Promise<void>;onError:(message:string)=>void}){
 const plan=status.chatgpt_plan||{};
 const identityConnected=plan.identity_connected===true||['connected','plan_permission_required'].includes(plan.status);
 const usageApproved=plan.plan_usage_approved===true||(plan.status==='connected'&&plan.plan_permission===true);
 const inferenceVerified=plan.inference_verified===true;
 const [consent,setConsent]=useState(false),[action,setAction]=useState(''),[authorizationUrl,setAuthorizationUrl]=useState(''),[models,setModels]=useState<ModelOption[]>([]),[selectedModel,setSelectedModel]=useState(plan.selected_model||''),[confirmDisconnect,setConfirmDisconnect]=useState(false);
 useEffect(()=>{setSelectedModel(plan.selected_model||'')},[plan.selected_model]);
 async function readModels(){setAction('models');onError('');try{const r=await api('/model/chatgpt/models');setModels((r.models||[]).map((m:Row)=>({slug:m.slug,display_name:m.display_name||m.slug})));if(r.selected_model)setSelectedModel(r.selected_model)}catch(e){onError((e as Error).message)}finally{setAction('')}}
 useEffect(()=>{if(usageApproved)void readModels();else setModels([])},[usageApproved]);
 async function startAuthorization(){
  if(!consent)return;
  setAction('authorization');onError('');setAuthorizationUrl('');
  // Open synchronously from the click, then navigate after the server prepares PKCE.
  const popup=window.open('about:blank','ai-universe-chatgpt-authorization','popup,width=620,height=780');
  if(popup){popup.opener=null;try{popup.document.title='正在准备 ChatGPT 授权';popup.document.body.textContent='正在通过官方流程准备授权，请稍候…'}catch{}}
  try{
   const r=await api('/model/chatgpt/start','POST',{enable_plan:true});const url=new URL(r.authorization_url);
   if(url.origin!=='https://auth.openai.com'||url.pathname!=='/api/accounts/authorize')throw new Error('服务端返回了无效的官方授权地址');
   setAuthorizationUrl(url.toString());
   if(popup)popup.location.href=url.toString();
   await onRefresh();
  }catch(e){popup?.close();onError((e as Error).message)}finally{setAction('')}
 }
 async function selectModel(slug:string){setAction('select');onError('');try{await api('/model/chatgpt/select','POST',{model:slug});setSelectedModel(slug);await onRefresh()}catch(e){onError((e as Error).message)}finally{setAction('')}}
 async function disconnect(){setAction('disconnect');onError('');try{const result=await api('/model/chatgpt/disconnect','POST');if(result.remote_revocation_confirmed===false)onError(result.message||'本地已退出，请到 ChatGPT 设置确认远程连接已撤销。');setConfirmDisconnect(false);setAuthorizationUrl('');setConsent(false);setModels([]);await onRefresh()}catch(e){onError((e as Error).message)}finally{setAction('')}}
 const busy=!!action;
 return <section className="panel model-panel connection-panel">
  <div className="section-heading"><div><h2>ChatGPT 计划接入</h2><p>通过官方授权流程连接你自己的账户</p></div><span className={'connection-state '+(usageApproved?'approved':identityConnected?'identity':'pending')}><i/>{usageApproved?(inferenceVerified?'已完成真实推理':'计划已授权 · 推理待验证'):identityConnected?'身份已连接 · 计划待批准':'尚未完成授权'}</span></div>
  <div className="connection-checks"><div><span>账户身份</span><strong>{identityConnected?<><Check size={14}/>已连接</>:<>未连接</>}</strong></div><div><span>计划用量授权</span><strong>{usageApproved?<><ShieldCheck size={14}/>已批准</>:<>尚未批准</>}</strong></div><div><span>后续任务模型</span><strong>{plan.selected_model||selectedModel||'待选择'}</strong></div><div><span>真实推理验证</span><strong>{inferenceVerified?'已验证':'尚未验证'}</strong></div></div>
  {plan.account&&(plan.account.name||plan.account.email)&&<div className="connected-account"><ShieldCheck size={15}/><span>当前授权账户：{plan.account.name||plan.account.email}{plan.account.name&&plan.account.email?<small>{plan.account.email}</small>:null}</span></div>}
  <p className="connection-message">{plan.message||'连接身份与获得计划调用授权是两个步骤。只有计划调用授权确认后，任务才会使用真实模型；未获授权会保持暂停。'}</p>
  {!usageApproved&&<div className="authorization-consent"><label className="check"><input type="checkbox" checked={consent} onChange={e=>setConsent(e.target.checked)}/><span>我同意通过官方流程使用我的 ChatGPT 计划用量（具体限额由 ChatGPT 设置管理）；应用不会购买额度或切换独立付费 API。</span></label><button className="primary" disabled={!consent||busy} onClick={startAuthorization}>{action==='authorization'?<LoaderCircle className="spinning" size={16}/>:<Link2 size={16}/>}Continue with ChatGPT<ArrowUpRight size={15}/></button>{authorizationUrl&&<a className="authorization-link" href={authorizationUrl} target="_blank" rel="noreferrer">继续打开官方授权页面<ExternalLink size={14}/></a>}<p>授权页面将在新窗口打开。完成后回到本页，连接状态会自动刷新。</p></div>}
  {usageApproved&&<div className="model-selection"><label className="field"><span>选择当前账户可用模型</span><select aria-label="ChatGPT 可用模型" value={selectedModel} disabled={busy||!models.length} onChange={e=>selectModel(e.target.value)}><option value="">请选择已授权模型</option>{models.map(m=><option key={m.slug} value={m.slug}>{m.display_name}</option>)}</select></label><button className="secondary" disabled={busy} onClick={readModels}><RefreshCw size={15}/>{action==='models'?'读取中…':'刷新可用模型'}</button></div>}
  {typeof plan.manage_usage_url==='string'&&plan.manage_usage_url.startsWith('https://chatgpt.com/')&&<a className="text-button official-usage-link" href={plan.manage_usage_url} target="_blank" rel="noreferrer">查看官方计划用量<ExternalLink size={14}/></a>}
  <div className="connection-footnote"><AlertCircle size={15}/><span>剩余额度以官方账户为准。这里展示后台实际取得的连接与调用信息；身份验证成功不会被当作计划调用已获批准。付费 API 自动回退始终关闭。</span></div>
  {(identityConnected||usageApproved)&&<div className="disconnect-row">{confirmDisconnect?<><span>断开后，新模型任务会等待重新授权。</span><button className="text-button" onClick={()=>setConfirmDisconnect(false)} disabled={busy}>取消</button><button className="text-button danger" onClick={disconnect} disabled={busy}>{action==='disconnect'?'断开中…':'确认断开'}</button></>:<button className="text-button danger" onClick={()=>setConfirmDisconnect(true)} disabled={busy}><Unplug size={14}/>断开 ChatGPT 连接</button>}</div>}
  {Array.isArray(plan.documentation)&&<details className="connection-docs"><summary>官方集成说明</summary>{plan.documentation.map((url:string)=><a className="external-link" target="_blank" rel="noreferrer" href={url} key={url}>{url}<ArrowUpRight size={13}/></a>)}</details>}
  <div className="notice local-mode-note">本地规则工具保持可用：用于材料整理、基础统计和文件生成，不调用语言模型，也不消耗模型额度。</div>
 </section>
}
